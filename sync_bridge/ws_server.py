"""Minimal, dependency-free WebSocket server (RFC 6455) for the EMtools ⇄
EMStudio live-sync bridge (ADR-002, phase 1: selection/focus).

Blender's bundled Python has no ``websockets`` package, so this is a tiny
hand-rolled server built on the stdlib only (socket + threading + select +
hashlib + base64 + struct). It is intentionally PLAIN PYTHON with no ``bpy``
import, so it can be unit-tested outside Blender and never touches Blender
state from a worker thread.

Threading model (bpy is NOT thread-safe):
  * the accept/read loop runs on a daemon thread;
  * inbound text messages are pushed onto ``inbox`` (a queue.Queue) — the
    Blender side drains it on the MAIN thread (a bpy.app timer);
  * ``broadcast(text)`` may be called from the main thread and fans the
    message out to every connected client.

Only text frames (JSON) are used. Ping/close are handled; binary/continuation
frames are ignored (the protocol is small JSON messages).
"""

from __future__ import annotations

import base64
import hashlib
import queue
import select
import socket
import struct
import threading

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _accept_key(client_key: str) -> str:
    digest = hashlib.sha1((client_key + _WS_GUID).encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def _handshake(conn: socket.socket) -> bool:
    """Read the HTTP upgrade request and reply with the 101 switch. Returns
    True on a successful WebSocket handshake."""
    data = b""
    conn.settimeout(5.0)
    try:
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(1024)
            if not chunk:
                return False
            data += chunk
            if len(data) > 16384:
                return False
    except OSError:
        return False
    finally:
        conn.settimeout(None)

    headers = {}
    for line in data.split(b"\r\n")[1:]:
        if b":" in line:
            k, _, v = line.partition(b":")
            headers[k.strip().lower().decode("latin1")] = v.strip().decode("latin1")
    key = headers.get("sec-websocket-key")
    if not key:
        return False
    resp = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {_accept_key(key)}\r\n\r\n"
    )
    try:
        conn.sendall(resp.encode("latin1"))
    except OSError:
        return False
    return True


def _encode_text(text: str) -> bytes:
    payload = text.encode("utf-8")
    n = len(payload)
    header = bytearray([0x81])  # FIN + text opcode
    if n < 126:
        header.append(n)
    elif n < 65536:
        header.append(126)
        header += struct.pack(">H", n)
    else:
        header.append(127)
        header += struct.pack(">Q", n)
    return bytes(header) + payload


class _Client:
    """One connected peer: buffers partial frames off the wire."""

    def __init__(self, conn: socket.socket):
        self.conn = conn
        self.buf = bytearray()

    def feed(self, data: bytes):
        self.buf += data

    def frames(self):
        """Yield ('text', str) / ('close', None) / ('ping', bytes) for every
        complete frame currently buffered."""
        while True:
            if len(self.buf) < 2:
                return
            b0, b1 = self.buf[0], self.buf[1]
            opcode = b0 & 0x0F
            masked = b1 & 0x80
            ln = b1 & 0x7F
            off = 2
            if ln == 126:
                if len(self.buf) < off + 2:
                    return
                ln = struct.unpack(">H", self.buf[off:off + 2])[0]
                off += 2
            elif ln == 127:
                if len(self.buf) < off + 8:
                    return
                ln = struct.unpack(">Q", self.buf[off:off + 8])[0]
                off += 8
            mask = b""
            if masked:
                if len(self.buf) < off + 4:
                    return
                mask = self.buf[off:off + 4]
                off += 4
            if len(self.buf) < off + ln:
                return
            payload = bytes(self.buf[off:off + ln])
            del self.buf[:off + ln]
            if masked:
                payload = bytes(payload[i] ^ mask[i % 4] for i in range(len(payload)))
            if opcode == 0x8:
                yield ("close", None)
            elif opcode == 0x9:
                yield ("ping", payload)
            elif opcode == 0x1:
                try:
                    yield ("text", payload.decode("utf-8"))
                except UnicodeDecodeError:
                    pass
            # 0x0/0x2/0xA ignored


class WsServer:
    """A minimal broadcast WebSocket server.

    Args:
        host, port: bind address (default localhost:8788).
        on_message: optional callable(str) invoked from the SERVER thread for
            every inbound text message. Prefer draining ``inbox`` on the main
            thread instead when running inside Blender.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8788, on_message=None):
        self.host = host
        self.port = port
        self.on_message = on_message
        self.inbox: "queue.Queue[str]" = queue.Queue()
        self._clients: list[_Client] = []
        self._lock = threading.Lock()
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # ---- lifecycle -----------------------------------------------------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(8)
        srv.setblocking(False)
        self._sock = srv
        self._thread = threading.Thread(target=self._run, name="em-ws", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        with self._lock:
            for c in self._clients:
                try:
                    c.conn.close()
                except OSError:
                    pass
            self._clients.clear()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    # ---- send ----------------------------------------------------------
    def broadcast(self, text: str):
        frame = _encode_text(text)
        with self._lock:
            dead = []
            for c in self._clients:
                try:
                    c.conn.sendall(frame)
                except OSError:
                    dead.append(c)
            for c in dead:
                self._clients.remove(c)

    # ---- loop ----------------------------------------------------------
    def _run(self):
        while not self._stop.is_set():
            with self._lock:
                socks = [self._sock] + [c.conn for c in self._clients]
            try:
                readable, _, _ = select.select(socks, [], [], 0.2)
            except (OSError, ValueError):
                continue
            for s in readable:
                if s is self._sock:
                    self._accept()
                else:
                    self._read(s)

    def _accept(self):
        try:
            conn, _ = self._sock.accept()
        except OSError:
            return
        if _handshake(conn):
            conn.setblocking(False)
            with self._lock:
                self._clients.append(_Client(conn))
        else:
            try:
                conn.close()
            except OSError:
                pass

    def _read(self, conn: socket.socket):
        client = None
        with self._lock:
            for c in self._clients:
                if c.conn is conn:
                    client = c
                    break
        if client is None:
            return
        try:
            data = conn.recv(4096)
        except OSError:
            data = b""
        if not data:
            self._drop(client)
            return
        client.feed(data)
        for kind, payload in client.frames():
            if kind == "text":
                self.inbox.put(payload)
                if self.on_message:
                    try:
                        self.on_message(payload)
                    except Exception:
                        pass
            elif kind == "ping":
                try:
                    conn.sendall(bytes([0x8A, len(payload)]) + payload)  # pong
                except OSError:
                    pass
            elif kind == "close":
                self._drop(client)
                return

    def _drop(self, client: _Client):
        with self._lock:
            if client in self._clients:
                self._clients.remove(client)
        try:
            client.conn.close()
        except OSError:
            pass
