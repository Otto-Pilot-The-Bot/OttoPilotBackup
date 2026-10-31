"""Gifts: pictures and 3D models your human drops in. Everything here treats uploads as DATA ONLY: nothing is ever run or imported.
Pictures are decoded and RE-ENCODED from pixels (all metadata dropped). Models (.glb) are parsed strictly and must be fully self-contained.
The real file type is checked by content, never by extension; scriptable formats (SVG etc.) are rejected."""
import io
import json
import re
import struct
import time
import uuid
from pathlib import Path

from PIL import Image

from . import assets, config

GIFT_DIR = config.ROOT / "data" / "gifts"
TERMS_FILE = config.ROOT / "data" / "gift_terms.txt"
MAX_IMAGE, MAX_MODEL, MAX_GIFTS = 10_000_000, 20_000_000, 40
MAX_SIDE, MAX_PIXELS = 2048, 40_000_000
MAX_TRIS, MAX_TEX, MAX_IMAGES, MAX_NODES, MAX_MESHES = 60_000, 2048, 8, 2000, 500
EXT = {".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image", ".glb": "model"}
OK_EXT_REQUIRED = {"KHR_materials_unlit", "KHR_texture_transform", "KHR_materials_emissive_strength", "KHR_materials_specular", "KHR_materials_ior", "KHR_mesh_quantization"}
CSIZE = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


class GiftError(Exception):
    """Message is safe to show the human."""


def sniff(b):
    if b[:8] == b"\x89PNG\r\n\x1a\n": return "png"
    if b[:3] == b"\xff\xd8\xff": return "jpeg"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP": return "webp"
    if b[:4] == b"glTF": return "glb"
    return None


def _image(data):
    """-> (clean bytes, ext, w, h). Rebuilt from pixels only, so EXIF/GPS/ICC/text chunks cannot survive."""
    Image.MAX_IMAGE_PIXELS = None                                              # we do our own (stricter) size check on the header before decoding
    try:
        im = Image.open(io.BytesIO(data)); im.verify()
        im = Image.open(io.BytesIO(data))
        if im.format not in ("PNG", "JPEG", "WEBP"):
            raise GiftError("That file is not a PNG, JPEG or WebP picture.")
        if im.size[0] * im.size[1] > MAX_PIXELS or min(im.size) < 1:
            raise GiftError(f"The picture is too large ({im.size[0]}x{im.size[1]}). The limit is about 40 megapixels.")
        im.seek(0); im.load()
    except GiftError:
        raise
    except Exception:
        raise GiftError("That picture could not be read; it may be damaged.")
    src = im.format
    alpha = im.mode in ("RGBA", "LA", "P") and ("transparency" in im.info or im.mode in ("RGBA", "LA"))
    im = im.convert("RGBA" if alpha else "RGB")
    im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    clean = Image.new(im.mode, im.size); clean.paste(im)                           # fresh image: no info dict, no exif, no profile
    out = io.BytesIO()
    if alpha or src == "PNG": clean.save(out, "PNG", optimize=True); ext = "png"
    else: clean.save(out, "JPEG", quality=90, optimize=True); ext = "jpg"
    return out.getvalue(), ext, clean.size[0], clean.size[1]


def _glb(data):
    """Strict structural validation of a self-contained .glb. Returns the parsed JSON. Nothing is executed."""
    if len(data) < 28:
        raise GiftError("That 3D model file is too small to be valid.")
    magic, ver, total = struct.unpack("<4sII", data[:12])
    if ver != 2 or total != len(data):
        raise GiftError("That 3D model is not a valid binary glTF 2.0 (.glb) file.")
    off, chunks = 12, []
    while off < len(data):
        if off + 8 > len(data): raise GiftError("The 3D model file is truncated or malformed.")
        clen, ctype = struct.unpack("<I4s", data[off:off + 8]); off += 8
        if off + clen > len(data): raise GiftError("The 3D model file is truncated or malformed.")
        chunks.append((ctype, data[off:off + clen])); off += clen
    if not chunks or chunks[0][0] != b"JSON" or len(chunks[0][1]) > 4_000_000 or len(chunks) > 2 or (len(chunks) == 2 and chunks[1][0] != b"BIN\x00"):
        raise GiftError("The 3D model has an unexpected layout.")
    try:
        j = json.loads(chunks[0][1].rstrip(b" \x00").decode("utf-8"))
    except Exception:
        raise GiftError("The 3D model's description could not be read.")
    binb = chunks[1][1] if len(chunks) == 2 else b""
    if not isinstance(j, dict) or str(j.get("asset", {}).get("version")) != "2.0":
        raise GiftError("Only glTF 2.0 models are accepted.")
    for k in ("buffers", "images"):
        for item in j.get(k, []):
            if "uri" in item:
                raise GiftError("That 3D model refers to an external file or web address. Only fully self-contained models are accepted.")
    req, used = set(j.get("extensionsRequired", [])), set(j.get("extensionsUsed", []))
    if req - OK_EXT_REQUIRED or used & assets.FORBIDDEN_EXT:
        raise GiftError("That 3D model uses compression or extensions that are not supported.")
    if len(j.get("nodes", [])) > MAX_NODES or len(j.get("meshes", [])) > MAX_MESHES or len(j.get("images", [])) > MAX_IMAGES or len(j.get("animations", [])) > 20:
        raise GiftError("That 3D model is too complex (too many parts, textures or animations).")
    bvs = j.get("bufferViews", [])
    for bv in bvs:
        if bv.get("buffer", 0) != 0 or bv.get("byteOffset", 0) < 0 or bv.get("byteOffset", 0) + bv.get("byteLength", 0) > len(binb):
            raise GiftError("The 3D model's data is damaged (out-of-range data).")
    acc = j.get("accessors", [])
    for a in acc:
        if a.get("count", 0) > 5_000_000 or a.get("count", 0) < 0:
            raise GiftError("The 3D model's data is damaged (impossible size).")
        if "bufferView" in a:
            if not isinstance(a["bufferView"], int) or not 0 <= a["bufferView"] < len(bvs): raise GiftError("The 3D model's data is damaged.")
            bv = bvs[a["bufferView"]]
            elem = CSIZE.get(a.get("componentType"), 4) * NCOMP.get(a.get("type"), 1)
            stride = bv.get("byteStride") or elem
            need = a.get("byteOffset", 0) + (max(a.get("count", 0) - 1, 0) * stride + elem if a.get("count", 0) else 0)
            if need > bv["byteLength"]:
                raise GiftError("The 3D model's data is damaged (a data block is larger than its space).")
    tris = 0
    for m in j.get("meshes", []):
        for pr in m.get("primitives", []):
            if pr.get("mode", 4) not in (4, 5, 6):
                continue
            try:
                cnt = acc[pr["indices"]]["count"] if "indices" in pr else acc[pr["attributes"]["POSITION"]]["count"]
            except (KeyError, IndexError, TypeError):
                raise GiftError("The 3D model has a damaged mesh.")
            tris += cnt // 3
    if tris > MAX_TRIS:
        raise GiftError(f"That 3D model is too detailed ({tris:,} triangles). The limit is {MAX_TRIS:,}.")
    for im in j.get("images", []):
        if "bufferView" not in im or im.get("mimeType") not in ("image/png", "image/jpeg"):
            raise GiftError("The 3D model's textures must be embedded PNG or JPEG pictures.")
        bv = bvs[im["bufferView"]]
        raw = binb[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
        if sniff(raw) not in ("png", "jpeg"):
            raise GiftError("A texture inside the 3D model is not a real PNG or JPEG.")
        try:
            t = Image.open(io.BytesIO(raw)); t.verify()
        except Exception:
            raise GiftError("A texture inside the 3D model is damaged.")
        if max(t.size) > MAX_TEX:
            raise GiftError(f"A texture inside the 3D model is too large ({t.size[0]}x{t.size[1]}; the limit is {MAX_TEX}).")
    return j, tris


def prepare(filename, data):
    """Pure validation and cleaning (safe to run in a worker thread). -> dict ready to store."""
    ext = Path(str(filename or "")).suffix.lower()
    if ext not in EXT:
        raise GiftError("Only .png, .jpg/.jpeg, .webp pictures and .glb 3D models can be given as gifts.")
    kind = EXT[ext]
    if len(data) > (MAX_IMAGE if kind == "image" else MAX_MODEL):
        raise GiftError(f"That file is too big (limit {MAX_IMAGE // 1_000_000} MB for pictures, {MAX_MODEL // 1_000_000} MB for 3D models).")
    real = sniff(data[:16])
    if (kind == "image" and real not in ("png", "jpeg", "webp")) or (kind == "model" and real != "glb"):
        raise GiftError("The file is not really what its name says. (Scriptable formats such as SVG are not accepted.)")
    if kind == "image":
        out, e, w, h = _image(data)
        return {"kind": "picture", "bytes": out, "ext": e, "w": w, "h": h, "mime": "image/png" if e == "png" else "image/jpeg", "tris": 0, "size3": (0, 0, 0), "fit": 1.0}
    j, tris = _glb(data)
    return {"kind": "model", "bytes": data, "ext": "glb", "w": 0, "h": 0, "mime": "model/gltf-binary", "tris": tris, "size3": None, "fit": 1.0}


def store(db, p, name, note, orig, tick):
    """Write the file (random name, data/gifts/) and record it. Only called from the event loop thread."""
    if db.one("SELECT COUNT(*) n FROM gifts")["n"] >= MAX_GIFTS:
        raise GiftError(f"The gift box is full ({MAX_GIFTS} gifts). Remove one first.")
    GIFT_DIR.mkdir(parents=True, exist_ok=True)
    fn = uuid.uuid4().hex + "." + p["ext"]
    path = GIFT_DIR / fn
    path.write_bytes(p["bytes"]); path.chmod(0o600)
    sx = sy = sz = 0.0; fit = 1.0
    if p["kind"] == "model":
        try:
            meta = assets.inspect(path)
        except Exception:
            path.unlink(missing_ok=True)
            raise GiftError("That 3D model could not be measured; it may be damaged.")
        sx, sy, sz = meta["size"]
        nat = max(sx, sy, sz) or 1.0
        lo, hi = config.ASSET_KEEP_RANGE
        fit = 1.0 if lo <= nat <= hi else max(config.ASSET_FIT_MIN, min(config.ASSET_FIT_MAX, nat)) / nat
    stem = re.sub(r"[^\w .'-]", "", Path(orig or "gift").stem).strip()[:40] or "gift"
    nm = re.sub(r"[^\w .'-]", "", str(name or "")).strip()[:40] or stem.replace("_", " ").replace("-", " ").title()
    note = re.sub(r"[\x00-\x1f]+", " ", str(note or "")).strip()[:300]
    gid = db.x("INSERT INTO gifts(ts,tick,name,kind,note,size,file,mime,w,h,tris,sx,sy,sz,fit,status,orig,giver) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'new',?,?)",
               time.time(), tick, nm, p["kind"], note, len(p["bytes"]), fn, p["mime"], p["w"], p["h"], p["tris"], sx, sy, sz, fit, stem, "your human")
    write_terms(db)
    return gid


def delete(db, gid):
    row = db.one("SELECT file,obj_id FROM gifts WHERE id=?", gid)
    if not row:
        return False
    (GIFT_DIR / row["file"]).unlink(missing_ok=True)
    if row["obj_id"]:
        db.x("DELETE FROM objects WHERE id=?", row["obj_id"])
    for o in db.q("SELECT id,meta FROM objects WHERE kind IN ('gift_model','creation') AND meta LIKE ?", f'%"gf": {gid},%'):   # builds that used this model
        pass
    db.x("DELETE FROM gifts WHERE id=?", gid)
    write_terms(db)
    return True


def write_terms(db):
    """Gift names and file names are PRIVATE: the page checker refuses any page that mentions them (see sanitize.check_privacy)."""
    terms = set()
    for r in db.q("SELECT name,orig FROM gifts"):
        for t in (r["name"], r["orig"]):
            if t and (len(t) >= 6 or " " in t.strip()):                  # distinctive names only (a gift called "Walk" must not block every page that says walk)
                terms.add(t.lower())
    TERMS_FILE.parent.mkdir(exist_ok=True)
    TERMS_FILE.write_text("# generated: names of gifts; never published\n" + "\n".join(sorted(terms)) + "\n")
