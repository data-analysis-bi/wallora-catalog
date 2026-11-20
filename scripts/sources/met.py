"""The Metropolitan Museum of Art: Open Access API. No key. Only isPublicDomain (CC0) objects."""
import common

BASE = "https://collectionapi.metmuseum.org/public/collection/v1"


def candidates(qc, seen, rng):
    params = {"q": qc["q"], "hasImages": "true", "isPublicDomain": "true"}
    params.update(qc.get("extra", {}))
    data = common.get_json(f"{BASE}/search", params)
    ids = list((data or {}).get("objectIDs") or [])
    rng.shuffle(ids)  # a different sample each run
    for oid in ids:
        cid = f"met-{oid}"
        if cid in seen:
            continue
        obj = common.get_json(f"{BASE}/objects/{oid}")
        common.pause(0.05)  # the Met asks for at most 80 requests per second
        if not obj or not obj.get("isPublicDomain") or not obj.get("primaryImageSmall"):
            yield {"id": cid, "reject": True}
            continue
        artist = (obj.get("artistDisplayName") or "").strip() or "Unknown artist"
        tags = " ".join(t.get("term", "") for t in (obj.get("tags") or []))
        yield {
            "id": cid,
            "title": (obj.get("title") or "Untitled").strip(),
            "credit": f"{artist} · The Met (CC0)",
            "license": "CC0",
            "source": "met",
            "sourceUrl": obj.get("objectURL") or "https://www.metmuseum.org/art/collection",
            "thumb_src": obj["primaryImageSmall"],
            "url": obj["primaryImageSmall"],
            "hires": obj.get("primaryImage") or None,
            "text": " ".join([obj.get("objectName") or "", obj.get("classification") or "", tags]),
        }
