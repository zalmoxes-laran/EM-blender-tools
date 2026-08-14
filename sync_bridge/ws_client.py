"""Minimal, dependency-free WebSocket CLIENT (RFC 6455) — the other direction.

`ws_server.py` let EMStudio connect TO Blender. This lets Blender connect OUT,
to a room (em-server): the same wire, the same hand-rolled framing, the opposite
role. Blender's bundled Python still has no `websockets` package and a Blender
addon cannot ask a user to `pip install`, so this is stdlib only — socket,
threading, base64, hashlib, struct.

Two differences from the server side, both required by the RFC and both easy to
get silently wrong:

* **A client MASKS every frame it sends.** An unmasked client frame is a
  protocol error and a compliant server (uvicorn is one) closes the connection —
  which looks exactly like the room rejecting you.
* **The handshake is verified.** The 101 and the `Sec-WebSocket-Accept` are
  checked against the key we sent, so a proxy or a captive portal answering 200
  with an HTML page fails loudly here instead of producing a socket that reads
  gibberish forever.

Same threading contract as the server: the read loop is a daemon thread that
touches nothing but the socket and a `queue.Queue`; every `bpy` access happens on
the main thread, later, when the queue is drained.

TLS: `wss://` is wrapped with `ssl.create_default_context()` — certificate
verification ON. A client that skipped verification would make the token it
carries interceptable, which is the one thing a token must never be.
"""

from __future__ import annotations

import base64
import hashlib
import os
import queue
import socket
import ssl
import struct
import threading
import urllib.parse
from typing import Dict, Iterator, Optional, Tuple

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WsClientError(RuntimeError):
    """The room could not be joined, with a sentence a person can act on."""


def _expected_accept(key: str) -> str:
    return base64.b64encode(
        hashlib.sha1((key + _WS_GUID).encode("utf-8")).digest()).decode("ascii")


def _encode_masked_text(text: str) -> bytes:
    """One masked text frame. The mask is what makes it a CLIENT frame."""
    payload = text.encode("utf-8")
    n = len(payload)
    header = bytearray([0x81])                      # FIN + text
    if n < 126:
        header.append(0x80 | n)
    elif n < 65536:
        header.append(0x80 | 126)
        header += struct.pack(">H", n)
    else:
        header.append(0x80 | 127)
        header += struct.pack(">Q", n)
    mask = os.urandom(4)
    masked = bytes(payload[i] ^ mask[i % 4] for i in range(n))
    return bytes(header) + mask + masked


def _frames(buf: bytearray) -> Iterator[Tuple[str, object]]:
    """Yield complete frames out of the buffer (server→client: unmasked)."""
    while True:
        if len(buf) < 2:
            return
        b0, b1 = buf[0], buf[1]
        opcode = b0 & 0x0F
        masked = b1 & 0x80
        length = b1 & 0x7F
        off = 2
        if length == 126:
            if len(buf) < off + 2:
                return
            length = struct.unpack(">H", buf[off:off + 2])[0]
            off += 2
        elif length == 127:
            if len(buf) < off + 8:
                return
            length = struct.unpack(">Q", buf[off:off + 8])[0]
            off += 8
        mask = b""
        if masked:
            if len(buf) < off + 4:
                return
            mask = buf[off:off + 4]
            off += 4
        if len(buf) < off + length:
            return
        payload = bytes(buf[off:off + length])
        del buf[:off + length]
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
        # 0x0 / 0x2 / 0xA ignored: the wire is small JSON text messages


class WsClient:
    """One outbound WebSocket connection, read on a daemon thread.

    Inbound text lands on `inbox` (a `queue.Queue` of str). Nothing here knows
    what the messages mean — that is the room session's job, on the main thread.
    """

    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None,
                 on_message=None, on_close=None) -> None:
        self.url = url
        self.headers = dict(headers or {})
        self.inbox: "queue.Queue[str]" = queue.Queue()
        self._on_message = on_message
        self._on_close = on_close
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._send_lock = threading.Lock()
        self._closing = False
        self.error: Optional[str] = None

    # ── connection ───────────────────────────────────────────────────────────

    def connect(self, timeout: float = 10.0) -> None:
        parsed = urllib.parse.urlsplit(self.url)
        if parsed.scheme not in ("ws", "wss"):
            raise WsClientError(f"not a WebSocket address: {self.url}")
        secure = parsed.scheme == "wss"
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if secure else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            if secure:
                sock = ssl.create_default_context().wrap_socket(
                    sock, server_hostname=host)
        except OSError as exc:
            raise WsClientError(f"could not reach {host}:{port} — {exc}") from exc

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}:{port}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13",
        ]
        request += [f"{name}: {value}" for name, value in self.headers.items()]
        sock.sendall(("\r\n".join(request) + "\r\n\r\n").encode("utf-8"))

        raw = b""
        sock.settimeout(timeout)
        try:
            while b"\r\n\r\n" not in raw:
                chunk = sock.recv(4096)
                if not chunk:
                    raise WsClientError("the room closed the connection during "
                                        "the handshake")
                raw += chunk
                if len(raw) > 65536:
                    raise WsClientError("the handshake answer is not a handshake")
        except socket.timeout as exc:
            sock.close()
            raise WsClientError("the room did not answer the handshake") from exc
        except WsClientError:
            sock.close()
            raise
        finally:
            sock.settimeout(None)

        head, _, rest = raw.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        status = lines[0] if lines else ""
        if "101" not in status:
            sock.close()
            # the status line is the useful half of the answer: 401 means the
            # token, 404 means the room id, 200 means something in between is
            # not a room at all
            raise WsClientError(f"the room refused the connection: {status.strip()}")
        received = {}
        for line in lines[1:]:
            name, _, value = line.partition(":")
            received[name.strip().lower()] = value.strip()
        if received.get("sec-websocket-accept") != _expected_accept(key):
            sock.close()
            raise WsClientError("the handshake answer does not match the key we "
                                "sent — this is not the room, or something is "
                                "in the middle")

        self._sock = sock
        self._closing = False
        self.error = None
        self._thread = threading.Thread(target=self._read_loop, args=(bytearray(rest),),
                                        daemon=True, name="em-room-client")
        self._thread.start()

    @property
    def connected(self) -> bool:
        return self._sock is not None and not self._closing

    # ── traffic ──────────────────────────────────────────────────────────────

    def send(self, text: str) -> bool:
        """Send one text frame. False when the socket is gone — a caller that
        must know may check, one that does not is not surprised by an exception
        from a background failure it did not cause."""
        sock = self._sock
        if sock is None or self._closing:
            return False
        try:
            with self._send_lock:
                sock.sendall(_encode_masked_text(text))
            return True
        except OSError as exc:
            self.error = str(exc)
            self.close()
            return False

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                with self._send_lock:
                    sock.sendall(b"\x88\x80" + os.urandom(4))   # masked close
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        if self._on_close is not None:
            try:
                self._on_close()
            except Exception:  # noqa: BLE001 — a callback must not break closing
                pass

    # ── the reader ───────────────────────────────────────────────────────────

    def _read_loop(self, buf: bytearray) -> None:
        sock = self._sock
        try:
            for kind, payload in _frames(buf):        # anything already buffered
                self._dispatch(kind, payload)
            while sock is not None and not self._closing:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
                for kind, payload in _frames(buf):
                    self._dispatch(kind, payload)
        except OSError as exc:
            if not self._closing:
                self.error = str(exc)
        finally:
            self.close()

    def _dispatch(self, kind: str, payload: object) -> None:
        if kind == "text":
            self.inbox.put(str(payload))
            if self._on_message is not None:
                try:
                    self._on_message(str(payload))
                except Exception:  # noqa: BLE001 — never kill the reader thread
                    pass
        elif kind == "ping":
            sock = self._sock
            if sock is not None:
                data = payload if isinstance(payload, bytes) else b""
                mask = os.urandom(4)
                masked = bytes(data[i] ^ mask[i % 4] for i in range(len(data)))
                try:
                    with self._send_lock:
                        sock.sendall(bytes([0x8A, 0x80 | len(data)]) + mask + masked)
                except OSError:
                    pass
        elif kind == "close":
            self.close()
