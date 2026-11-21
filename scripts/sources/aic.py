"""Art Institute of Chicago API. No key. Only is_public_domain (CC0) artworks, images via IIIF."""
import common

API = "https://api.artic.edu/api/v1/artworks/search"
FIELDS = "id,title,artist_title,image_id,thumbnail,is_public_domain,classification_title"


def candidates(qc, seen, rng):
    params = {
        "q": qc["q"],
        "fields": FIELDS,
        "limit": 100,
        "page": rng.randint(1, 3),
    }
    data = common.get_json(API, params)
    if not data:
        return
    iiif = (data.get("config") or {}).get("iiif_url") or "https://www.artic.edu/iiif/2"
    rows = list(data.get("data") or [])
    rng.shuffle(rows)
    for a in rows:
        cid = f"aic-{a.get('id')}"
        if cid in seen:
            continue
        iid = a.get("image_id")
        th = a.get("thumbnail") or {}
        w, h = th.get("width"), th.get("height")
        if not a.get("is_public_domain") or not iid or not w or not h:
            yield {"id": cid, "reject": True}
            continue
        artist = (a.get("artist_title") or "").strip() or "Unknown artist"
        yield {
            "id": cid,
            "title": (a.get("title") or "Untitled").strip(),
            "credit": f"{artist} · Art Institute of Chicago (CC0)",
            "license": "CC0",
            "source": "aic",
            "sourceUrl": f"https://www.artic.edu/artworks/{a.get('id')}",
            "thumb_src": f"{iiif}/{iid}/full/{common.THUMB_WIDTH},/0/default.jpg",
            "url": f"{iiif}/{iid}/full/843,/0/default.jpg",
            "hires": f"{iiif}/{iid}/full/1686,/0/default.jpg" if w >= 1686 else None,
            "pre_dims": (w, h),
            "text": a.get("classification_title") or "",
        }
