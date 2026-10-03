"""P3 · the resource inventory, the store-backed resource, the seed — and the
ONE upload function against a real node.

The inventory is pure (`sync_manager/inventory.py`): four groups, the batch as
one line, the choices, the path kept as a second address. The upload
(`sync_manager/asset_upload.py`) is measured against StratiGraph Server from the
sibling checkout in dev mode: HEAD first, a streamed PUT, the resumable door in
pieces, a resume after a refused offset, and a second upload that sends nothing.
"""

import hashlib
import importlib.util
import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import types
import urllib.error
import urllib.request

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
_SERVER = _REPO.parent / "stratigraph-server"
_SERVER_PY = _SERVER / ".venv" / "bin" / "python"
if _S3D.is_dir() and str(_S3D) not in sys.path:
    sys.path.insert(0, str(_S3D))


def _load():
    pkg = types.ModuleType("_p3_pkg")
    pkg.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_p3_pkg"] = pkg
    for name in ("room", "asset_upload", "inventory", "exif_lite"):
        spec = importlib.util.spec_from_file_location(
            f"_p3_pkg.{name}", _REPO / "sync_manager" / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return sys.modules["_p3_pkg.inventory"], sys.modules["_p3_pkg.asset_upload"]


inv, up = _load()

from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.dtc_acquisition_node import DTCAcquisitionNode  # noqa: E402
from s3dgraphy.nodes.resource_node import ResourceNode  # noqa: E402


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture()
def study(tmp_path):
    """A graph with one resource of every kind, and two raw photos in a batch."""
    (tmp_path / "docs").mkdir()
    model = tmp_path / "docs" / "model.glb"
    model.write_bytes(b"glTF-model-bytes")
    pdf = tmp_path / "docs" / "report.pdf"
    pdf.write_bytes(b"%PDF the report")
    photos = []
    for i in range(2):
        p = tmp_path / "raw" / f"IMG_{i}.JPG"
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(f"raw photo {i}".encode())
        photos.append(p)
    stored_bytes = b"already in the room"

    g = Graph("study")
    g.add_node(ResourceNode("r-model", name="model.glb", url="docs/model.glb"))
    g.add_node(ResourceNode("r-pdf", name="report", url=str(pdf)))
    g.add_node(ResourceNode("r-web", name="web page", url="https://example.org/page"))
    g.add_node(ResourceNode("r-nas", name="nas", url="\\\\nas\\scans\\big.tif"))
    g.add_node(ResourceNode("r-gone", name="gone", url="docs/not-here.obj"))
    g.add_node(ResourceNode("r-stored", name="stored", url="x",
                            checksum=f"sha256:{_sha(stored_bytes)}",
                            residency="resident"))
    g.add_node(DTCAcquisitionNode("acq-1", name="Volo 2026-03",
                                  dtc_kind="local_import"))
    for i, p in enumerate(photos):
        g.add_node(ResourceNode(f"r-photo-{i}", name=p.name, url=str(p)))
        g.add_edge(f"e-acq-{i}", "acq-1", f"r-photo-{i}", "dtc_had_output")
    return {"graph": g, "base": str(tmp_path), "stored": _sha(stored_bytes),
            "pdf": str(pdf), "model": str(model)}


def _hasher(path):
    return up.sha256_of_file(path)


def test_four_groups_and_the_batch_is_one_line(study):
    rows = inv.classify(inv.resource_entries(study["graph"]),
                        base_dirs=[study["base"]],
                        has_asset=lambda hexd: hexd == study["stored"],
                        hasher=_hasher)
    by_id = {r["id"]: r for r in rows}
    assert by_id["r-model"]["group"] == "found"           # relative, resolved
    assert by_id["r-model"]["path"] == study["model"]
    assert by_id["r-pdf"]["group"] == "found"
    assert by_id["r-web"]["group"] == "external"
    assert by_id["r-nas"]["group"] == "external"
    assert by_id["r-gone"]["group"] == "missing"
    assert by_id["r-stored"]["group"] == "stored"
    assert by_id["r-photo-0"]["batch_id"] == "acq-1"
    s = inv.summarise(rows)
    assert s["groups"]["found"]["count"] == 4                # model, pdf, 2 photos
    assert s["groups"]["external"]["count"] == 2
    assert s["groups"]["missing"]["count"] == 1
    assert s["groups"]["stored"]["count"] == 1
    assert len(s["batches"]) == 1 and s["batches"][0]["count"] == 2
    lines = inv.sentences(s)
    assert any(line.startswith("batch «Volo 2026-03»: 2 file(s)") for line in lines)
    assert s["upload"]["count"] == 4                          # upload is the default


def test_a_file_the_room_already_has_is_stored_not_found(study):
    pdf_hex = up.sha256_of_file(study["pdf"])
    rows = inv.classify(inv.resource_entries(study["graph"]),
                        base_dirs=[study["base"]],
                        has_asset=lambda hexd: hexd in (pdf_hex, study["stored"]),
                        hasher=_hasher)
    assert {r["id"]: r["group"] for r in rows}["r-pdf"] == "stored"


def test_choices_item_beats_batch_beats_group(study):
    rows = inv.classify(inv.resource_entries(study["graph"]),
                        base_dirs=[study["base"]], has_asset=lambda h: False,
                        hasher=_hasher)
    inv.apply_choices(rows, per_group={"found": "reference"},
                      per_batch={"acq-1": "upload"},
                      per_item={"r-photo-1": "skip"})
    choice = {r["id"]: r["choice"] for r in rows}
    assert choice["r-model"] == "reference"
    assert choice["r-photo-0"] == "upload"
    assert choice["r-photo-1"] == "skip"
    # a choice of upload on a group with nothing on this disk is ignored
    inv.apply_choices(rows, per_item={"r-web": "upload"})
    assert {r["id"]: r["choice"] for r in rows}["r-web"] == "reference"


def test_store_backed_keeps_the_original_path(study):
    g = study["graph"]
    node = g.find_node_by_id("r-pdf")
    hexd = up.sha256_of_file(study["pdf"])
    url = up.asset_url("https://em.localhost:8443/em", "scavo-2026", hexd)
    addresses = inv.make_store_backed(node, url=url, sha256=hexd)
    assert node.data["url"] == url
    assert node.data["checksum"] == f"sha256:{hexd}"
    assert node.data["residency"] == "resident"
    assert [a["locator"] for a in addresses] == [url, study["pdf"]]
    assert node.data["addresses"][1]["locator"] == study["pdf"]
    # …and a second time changes nothing
    assert len(inv.make_store_backed(node, url=url, sha256=hexd)) == 2


def test_the_seed_is_nodes_then_edges_with_a_language(study):
    from s3dgraphy.exporter.emjson_exporter import build_emjson
    section = build_emjson(study["graph"])["graph"]
    ops = inv.seed_ops(study["graph"], section)
    kinds = [o["op"] for o in ops]
    assert kinds.index("add_edge") == kinds.count("add_node")
    assert kinds.count("add_node") == len(study["graph"].nodes)
    edge = next(o for o in ops if o["op"] == "add_edge")
    assert edge["source"] == "acq-1" and edge["edge_type"] == "dtc_had_output"
    from s3dgraphy.crdt import is_text_node
    for op in ops:
        if op["op"] == "add_node" and is_text_node(op["node"]):
            assert op["node"]["data"]["lang"]


def test_locators_are_read_by_kind():
    assert inv.locator_kind("https://x/y") == "url"
    assert inv.locator_kind("smb://nas/x") == "url"
    assert inv.locator_kind("\\\\nas\\x") == "share"
    assert inv.locator_kind("C:\\scans\\a.tif") == "path"
    assert inv.locator_kind("file:///tmp/a") == "file"
    assert inv.locator_kind("") == ""
    assert inv.locator_kind("blend://scene.blend#Object/M") == "blend"
    assert inv.media_type_for("A.GLB") == "model/gltf-binary"


# ── the ONE upload function, against a real node ─────────────────────────────

def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def node(tmp_path_factory):
    if not _SERVER_PY.is_file() or not _S3D.is_dir():
        pytest.skip("the StratiGraph Server checkout (with its venv) is not beside this repo")
    port = _free_port()
    assets = tmp_path_factory.mktemp("p3-assets")
    uploads = tmp_path_factory.mktemp("p3-uploads")
    env = dict(os.environ, PYTHONPATH=str(_S3D), EM_ASSET_DIR=str(assets),
               EM_UPLOAD_DIR=str(uploads))
    env.pop("EM_ASSET_STORE", None)
    process = subprocess.Popen(
        [str(_SERVER_PY), "-m", "uvicorn", "app.main:app", "--port", str(port),
         "--log-level", "warning"],
        cwd=str(_SERVER), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 25
    while time.time() < deadline:
        if process.poll() is not None:
            pytest.skip(f"StratiGraph Server did not start: "
                        f"{process.stderr.read().decode()[-300:]}")
        try:
            with urllib.request.urlopen(base + "/v1/health", timeout=1) as answer:
                if answer.status == 200:
                    break
        except (urllib.error.URLError, OSError):
            time.sleep(0.25)
    else:  # pragma: no cover
        process.kill()
        pytest.skip("StratiGraph Server did not become healthy in time")
    # does this checkout have the resumable door (1a1bbf8)?
    probe = urllib.request.Request(f"{base}/v1/rooms/p3/uploads", method="POST",
                                   data=b'{"size": 1}',
                                   headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(probe, timeout=5).read()
    except urllib.error.HTTPError as exc:  # pragma: no cover
        process.terminate()
        pytest.skip(f"this StratiGraph Server has no resumable uploads ({exc.code})")
    try:
        yield base
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            process.kill()


def test_head_put_and_the_second_time_nothing_is_sent(node, tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(os.urandom(300_000))
    seen = []
    first = up.upload_asset(node, "p3", str(f), None, "application/octet-stream",
                            None, lambda a, b: seen.append((a, b)))
    assert first["already"] is False
    assert first["ref"] == f"sha256:{up.sha256_of_file(str(f))}"
    assert seen[-1] == (300_000, 300_000)
    assert up.has_asset(node, "p3", first["sha256"], None)
    second = up.upload_asset(node, "p3", str(f), first["sha256"],
                             "application/octet-stream", None)
    assert second["already"] is True


def test_the_resumable_door_in_pieces(node, tmp_path):
    f = tmp_path / "big.bin"
    f.write_bytes(os.urandom(2_500_000))
    info = up.upload_asset(node, "p3", str(f), None, "application/octet-stream",
                           None, single_shot_max=1_000_000, piece=700_000)
    assert info["already"] is False
    assert info["ref"] == f"sha256:{up.sha256_of_file(str(f))}"
    with urllib.request.urlopen(f"{node}/v1/rooms/p3/asset/{info['ref']}") as answer:
        assert answer.read() == f.read_bytes()


def test_a_cut_resumes_from_the_nodes_offset(node, tmp_path, monkeypatch):
    """The second PATCH dies on the way: the client asks the node where it is
    and goes on from there — the file arrives whole."""
    f = tmp_path / "cut.bin"
    f.write_bytes(os.urandom(2_100_000))
    real = up._json_call
    calls = {"patch": 0}

    def flaky(request, timeout):
        if request.get_method() == "PATCH":
            calls["patch"] += 1
            if calls["patch"] == 2:
                raise urllib.error.URLError("connection reset (simulated)")
        return real(request, timeout)

    monkeypatch.setattr(up, "_json_call", flaky)
    info = up.upload_asset(node, "p3", str(f), None, "application/octet-stream",
                           None, single_shot_max=500_000, piece=800_000)
    assert info["ref"] == f"sha256:{up.sha256_of_file(str(f))}"
    assert calls["patch"] >= 4                     # 3 pieces + the one that was cut


def test_a_wrong_declared_digest_is_refused_and_nothing_stored(node, tmp_path):
    f = tmp_path / "liar.bin"
    f.write_bytes(b"these bytes")
    with pytest.raises(up.RoomError) as caught:
        up.upload_asset(node, "p3", str(f), "0" * 64, "text/plain", None)
    assert caught.value.status == 422


# ── F1 · a file lives in ONE room: «Move here» ───────────────────────────────

def test_f1_bytes_at_home_elsewhere_are_their_own_group(study):
    """HEAD 200 with `X-EM-Home-Room: tempio-a` while bringing into tempio-b:
    not «stored» (they are not this room's), «elsewhere», proposal «move»."""
    pdf_hex = up.sha256_of_file(study["pdf"])
    homes = {pdf_hex: "tempio-a", study["stored"]: "tempio-b"}
    rows = inv.classify(inv.resource_entries(study["graph"]),
                        base_dirs=[study["base"]], hasher=_hasher, room_id="tempio-b",
                        asset_home=lambda hexd: (hexd in homes, homes.get(hexd)))
    by_id = {r["id"]: r for r in rows}
    assert by_id["r-pdf"]["group"] == "elsewhere"
    assert by_id["r-pdf"]["home"] == "tempio-a" and by_id["r-pdf"]["choice"] == "move"
    assert by_id["r-stored"]["group"] == "stored", "at home HERE is simply stored"
    assert inv.summarise(rows)["upload"]["count"] == 3, "a file kept elsewhere is never re-sent"
    inv.apply_choices(rows, per_item={"r-pdf": "upload"})
    assert by_id["r-pdf"]["choice"] == "move", "it cannot be «uploaded»"
    inv.apply_choices(rows, per_group={"elsewhere": "reference"})
    assert by_id["r-pdf"]["choice"] == "reference"


def test_f1_the_plan_lists_before_the_yes():
    rows = [{"id": "podio", "name": "podio.glb", "group": "elsewhere", "choice": "move"},
            {"id": "pianta", "name": "pianta.pdf", "group": "elsewhere", "choice": "move"},
            {"id": "x", "name": "x", "group": "found", "choice": "upload"}]
    plan = inv.move_plan(rows, {
        "podio": {"home": "tempio-a", "references": ["tempio-a", "tempio-c"], "can_move": True},
        "pianta": {"home": "tempio-a", "can_move": False, "why_not": "only its owner may move it out"}})
    assert [r["id"] for r in plan["movable"]] == ["podio"]
    assert [(b["row"]["id"], b["why"]) for b in plan["blocked"]] == [
        ("pianta", "only its owner may move it out")]
    assert plan["leave"] == ["tempio-a"] and plan["references"] == ["tempio-a", "tempio-c"]
    assert len(inv.move_plan(rows, {"podio": {"error": "403"}})["blocked"]) == 2


def test_f1_head_names_the_home_and_move_here_moves_it(node, tmp_path):
    """Against the node: uploaded through `f1-a`, asked through `f1-b` — HEAD
    names `f1-a`; the view lists `f1-b` as destination; the move makes `f1-b`
    the ONLY home, and a second move is a no-op (dev mode: anybody may)."""
    f = tmp_path / "podio.glb"
    f.write_bytes(os.urandom(4096))
    info = up.upload_asset(node, "f1-a", str(f), None, "model/gltf-binary", None)
    assert info.get("home") == "f1-a"
    present, home = up.asset_head(node, "f1-b", info["sha256"], None)
    if home is None:
        pytest.skip("this StratiGraph Server does not name the home yet (F1)")
    assert present and home == "f1-a"
    view = up.asset_home_view(node, "f1-b", info["sha256"], None)
    assert view["home"] == "f1-a" and view["can_move"] is True
    moved = up.move_asset_home(node, "f1-b", info["sha256"], "f1-a", None)
    assert moved["moved"] is True and moved["home"] == "f1-b"
    assert up.asset_head(node, "f1-a", info["sha256"], None) == (True, "f1-b")
    with pytest.raises(up.RoomError) as stale:
        up.move_asset_home(node, "f1-c", info["sha256"], "f1-a", None)
    assert stale.value.status == 409, "a move against a stale home is refused"


# ── L1 · the lot rule (the same cases as EMStudio check-room-inventory part 6) ─

@pytest.mark.parametrize("name", ["D.01", "D.1.jpg", "D.12.jpg", "D.01.01.jpeg",
                                  "D.07 Maison Carree Nimes.png", "D.11_scan.tif",
                                  "D.3-bis.jpg"])
def test_l1_an_em_document_name(name):
    assert inv.is_em_document_name(name)


@pytest.mark.parametrize("name", ["DSC_0001.JPG", "D.jpg", "DJI_0001.JPG", "D.01a.jpg",
                                  "IMG_D.01.jpg", "d.01.jpg"])
def test_l1_not_an_em_document_name(name):
    assert not inv.is_em_document_name(name)


def test_l1_the_dosco():
    assert inv.in_dosco("/a/DosCo/x.jpg") and inv.in_dosco("/a/dosco/sub/x.jpg")
    assert not inv.in_dosco("/a/DosCoX/x.jpg")
    assert inv.in_dosco("/b/docs/x.jpg", ["/b/docs"])
    assert not inv.in_dosco("/b/docs2/x.jpg", ["/b/docs"])


_T0 = 1790762400   # 2026-09-30 10:00:00 UTC


def _at(seconds):
    return time.strftime("%Y:%m:%d %H:%M:%S", time.gmtime(_T0 + seconds))


_CANON = "Canon EOS R5 #012345"


def _shots():
    out = [{"id": f"s{i}", "path": f"/f/session/IMG_{i}.JPG",
            "exif": {"camera": _CANON, "taken_at": _at(15 * i)}} for i in range(12)]
    out.append({"id": "tif", "path": "/f/session/IMG_0200.tif",
                "exif": {"camera": _CANON, "taken_at": _at(200)}})
    out.append({"id": "doc-out", "path": "/f/session/D.20.jpg",
                "exif": {"camera": _CANON, "taken_at": _at(100)}})
    out += [{"id": f"late{i}", "path": f"/f/session/IMG_10{i}.JPG",
             "exif": {"camera": _CANON, "taken_at": _at(7200 + 10 * i)}} for i in range(2)]
    out += [{"id": f"px{i}", "path": f"/f/session/PXL_{i}.jpg",
             "exif": {"camera": "Google Pixel 8", "taken_at": _at(20 * i)}} for i in range(3)]
    out += [{"id": f"dosco{i}", "path": f"/f/DosCo/D.07.0{i}.jpg",
             "exif": {"camera": _CANON, "taken_at": _at(5 * i)}} for i in range(1, 6)]
    out += [{"id": f"ddir{i}", "path": f"/f/docs/scan_{i}.jpg",
             "exif": {"camera": _CANON, "taken_at": _at(6 * i)}} for i in range(1, 6)]
    out += [{"id": f"nx{i}", "path": f"/f/noexif/foto_{i}.jpg", "exif": None} for i in range(8)]
    out.append({"id": "pdf", "path": "/f/session/report.pdf",
                "exif": {"camera": _CANON, "taken_at": _at(30)}})
    return out


def test_l1_one_session_and_nothing_else():
    assert _at(0) == "2026:09:30 10:00:00"
    lots = inv.session_lots(_shots(), dosco_dirs=["/f/docs"])
    assert [(l["camera"], len(l["ids"]), l["from"], l["to"]) for l in lots] == [
        (_CANON, 13, _at(0), _at(200))]


def test_l1_the_gap_is_inclusive():
    five = lambda step, tag: [{"id": f"{tag}{i}", "path": f"/g/{i}.jpg",
                               "exif": {"camera": "X", "taken_at": _at(step * i)}}
                              for i in range(5)]
    assert len(inv.session_lots(five(1800, "g"))) == 1
    assert len(inv.session_lots(five(1801, "h"))) == 0


def test_l1_two_bodies_of_one_model_are_two_sessions():
    shots = [{"id": f"b{b}-{i}", "path": f"/k/{b}_{i}.jpg",
              "exif": {"camera": f"Nikon Z7 #{b}", "taken_at": _at(10 * i + b)}}
             for b in (0, 1) for i in range(6)]
    assert sorted(len(l["ids"]) for l in inv.session_lots(shots)) == [6, 6]


def test_l1_templu_mare_dosco_is_never_a_lot():
    """T-L1 on the real copy: the DosCo of Templu Mare (/tmp/micro-asset-versioni)
    read with the real EXIF reader — no lot. Its D.nn files carry no EXIF, so
    the rule is also tried with the fixture's EXIF-bearing D.07.0x (below)."""
    dosco = pathlib.Path("/tmp/micro-asset-versioni/DosCo")
    if not dosco.is_dir():
        pytest.skip("the working copy of Templu Mare's DosCo is not in /tmp")
    rows = [{"id": p.name, "path": str(p), "group": "found"}
            for p in sorted(dosco.iterdir()) if p.is_file() and not p.name.startswith(".")]
    assert len(rows) >= 18
    lots = inv.propose_sessions(rows, exif_of=sys.modules["_p3_pkg.exif_lite"].photo_exif,
                                dosco_dirs=[str(dosco)])
    assert lots == [] and not any(r.get("batch_id") for r in rows)
    # …and even if every photo there were one camera, one minute: no lot
    shots = [{"id": f"d{i}", "path": str(dosco / f"D.07.0{i}.jpg"),
              "exif": {"camera": _CANON, "taken_at": _at(i)}} for i in range(1, 6)]
    assert inv.session_lots(shots) == []


def test_l1_a_session_with_real_exif_is_proposed_not_applied(tmp_path):
    """Photos whose EXIF Pillow wrote: the reader finds camera and time, the
    session is PROPOSED (unconfirmed), the D.nn among them and the DosCo stay out."""
    PIL = pytest.importorskip("PIL.Image")
    exif_lite = sys.modules["_p3_pkg.exif_lite"]

    def shot(path, seconds, camera=("Canon", "Canon EOS R5", "012345"), fmt="JPEG"):
        im = PIL.new("RGB", (16, 12))
        ex = PIL.Exif()
        ex[0x010F], ex[0x0110] = camera[0], camera[1]
        sub = ex.get_ifd(0x8769)
        sub[0x9003] = _at(seconds)
        sub[0xA431] = camera[2]
        path.parent.mkdir(parents=True, exist_ok=True)
        im.save(path, fmt, exif=ex.tobytes())

    for i in range(6):
        shot(tmp_path / "session" / f"IMG_{i:04d}.JPG", 20 * i)
    shot(tmp_path / "session" / "IMG_0099.tif", 130, fmt="TIFF")
    shot(tmp_path / "session" / "D.09.jpg", 50)
    for i in range(1, 6):
        shot(tmp_path / "DosCo" / f"D.07.0{i}.jpg", 5 * i)
    assert exif_lite.photo_exif(str(tmp_path / "session" / "IMG_0099.tif")) == {
        "camera": _CANON, "taken_at": _at(130)}
    assert exif_lite.photo_exif(str(tmp_path / "session" / "nope.pdf")) is None
    rows = [{"id": p.name, "path": str(p), "group": "found", "choice": "upload"}
            for p in sorted(tmp_path.rglob("*")) if p.is_file()]
    lots = inv.propose_sessions(rows, exif_of=exif_lite.photo_exif)
    assert len(lots) == 1 and lots[0]["confirmed"] is False
    assert sorted(lots[0]["ids"]) == sorted([f"IMG_{i:04d}.JPG" for i in range(6)] + ["IMG_0099.tif"])
    s = inv.summarise(rows)
    assert s["batches"][0]["proposed"] is True
    assert any(line.startswith("proposed lot «") for line in inv.sentences(s))
