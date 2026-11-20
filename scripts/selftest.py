"""Offline check of the whole pipeline with fake API responses (runs in CI before the real build)."""
import datetime as dt
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ["WALLORA_NO_SLEEP"] = "1"
os.environ["SITE_BASE"] = "https://example.github.io/wallora-catalog/"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_catalog  # noqa: E402
import common  # noqa: E402
from PIL import Image  # noqa: E402


def fake_image(portrait: bool) -> bytes:
    im = Image.new("RGB", (800, 1200) if portrait else (1200, 800), (200, 90, 40))
    for x in range(0, im.width, 7):
        for y in range(0, im.height, 50):
            im.putpixel((x, y), (20, 40, 120))
    buf = io.BytesIO()
    im.save(buf, "JPEG")
    return buf.getvalue()


def fake_json(url, params=None, retries=3):
    if "collectionapi.metmuseum.org" in url and url.endswith("/search"):
        return {"total": 4, "objectIDs": [1, 2, 3, 4]}
    if "collectionapi.metmuseum.org" in url and "/objects/" in url:
        oid = int(url.rsplit("/", 1)[1])
        return {"objectID": oid, "isPublicDomain": oid != 3, "primaryImageSmall": f"https://img/met/{oid}-{'p' if oid % 2 else 'l'}.jpg",
                "primaryImage": f"https://img/met/{oid}-big.jpg", "title": f"Met work {oid}", "artistDisplayName": "A. Painter",
                "objectURL": f"https://met/{oid}", "objectName": "Painting", "classification": "Paintings", "tags": [{"term": "Landscapes"}]}
    if "api.artic.edu" in url:
        return {"config": {"iiif_url": "https://www.artic.edu/iiif/2"}, "data": [
            {"id": 10, "title": "AIC portrait-ish", "artist_title": "B. Artist", "image_id": "abc", "is_public_domain": True,
             "thumbnail": {"width": 2000, "height": 2600}, "classification_title": "painting"},
            {"id": 11, "title": "AIC wide", "image_id": "def", "is_public_domain": True, "thumbnail": {"width": 3000, "height": 1500}},
            {"id": 12, "title": "AIC not PD", "image_id": "ghi", "is_public_domain": False, "thumbnail": {"width": 2000, "height": 2600}}]}
    if "images-api.nasa.gov/search" in url:
        return {"collection": {"items": [
            {"data": [{"nasa_id": "n1", "title": "Pillars", "description": "nebula", "keywords": ["hubble"], "photographer": "Jane"}],
             "href": "https://assets/n1/collection.json"},
            {"data": [{"nasa_id": "n2", "title": "NASA logo meatball", "description": "logo"}], "href": "https://assets/n2/collection.json"}]}}
    if url.startswith("https://assets/"):
        nid = url.split("/")[-2]
        return [f"http://images-assets.nasa.gov/image/{nid}/{nid}~orig.jpg", f"http://images-assets.nasa.gov/image/{nid}/{nid}~large.jpg",
                f"http://images-assets.nasa.gov/image/{nid}/{nid}~small.jpg", f"http://images-assets.nasa.gov/image/{nid}/{nid}~thumb.jpg"]
    return None


def fake_bytes(url, retries=3, max_bytes=0):
    return fake_image(portrait=("-p" in url) or ("abc" in url) or ("n1" in url))


def main():
    common.get_json, common.get_bytes = fake_json, fake_bytes
    root = Path(tempfile.mkdtemp())
    (root / "config").mkdir()
    (root / "data").mkdir()
    cfg = json.loads((Path(__file__).resolve().parent.parent / "config" / "queries.json").read_text())
    cfg["queries"] = {"met": [{"q": "x", "category": "nature"}], "aic": [{"q": "x", "category": "art"}],
                      "nasa": [{"q": "x", "category": "space", "max_aspect": 1.8}]}
    cfg["filters"]["min_short_side_original"] = 1000
    (root / "config" / "queries.json").write_text(json.dumps(cfg))
    (root / "config" / "blocklist.json").write_text("[]")
    today = dt.date(2026, 11, 20)
    build_catalog.run(root, today)
    index = json.loads((root / "site" / "index.json").read_text())
    ids = {i["id"] for c in index["categories"] if c["count"] for i in json.loads((root / "site" / "c" / c["id"] / "1.json").read_text())["items"]}
    print("accepted:", sorted(ids))
    # Met 1 (portrait, PD) ok; Met 2 (landscape) rejected; Met 3 not PD; Met 4 landscape; AIC 10 ok; AIC 11 wide; AIC 12 not PD; NASA n1 ok; n2 logo
    assert ids == {"met-1", "aic-10", "nasa-n1"}, ids
    assert (root / "site" / "all" / "1.json").exists() and index["total"] == 3
    first = json.loads((root / "site" / "all" / "1.json").read_text())["items"][0]
    assert first["thumb"].startswith("https://example.github.io/wallora-catalog/thumbs/"), first["thumb"]
    build_catalog.run(root, today)  # second run must add nothing new
    assert json.loads((root / "site" / "index.json").read_text())["total"] == 3
    shutil.rmtree(root)
    print("SELFTEST OK")


if __name__ == "__main__":
    main()
