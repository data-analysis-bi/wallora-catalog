"""NASA Image and Video Library API. No key. Credit NASA; logos/insignia are filtered out by keyword."""
import common

SEARCH = "https://images-api.nasa.gov/search"


def _quote(u: str) -> str:
    return u.replace(" ", "%20").replace("http://", "https://")


def _pick(urls, markers):
    for m in markers:
        for u in urls:
            if m in u.lower() and u.lower().endswith((".jpg", ".jpeg")):
                return _quote(u)
    return None


def candidates(qc, seen, rng):
    params = {"q": qc["q"], "media_type": "image", "page_size": 100, "page": rng.randint(1, 3)}
    data = common.get_json(SEARCH, params)
    items = list(((data or {}).get("collection") or {}).get("items") or [])
    rng.shuffle(items)
    for it in items:
        d = (it.get("data") or [{}])[0]
        nid = d.get("nasa_id")
        if not nid:
            continue
        cid = f"nasa-{nid}"
        if cid in seen:
            continue
        manifest = common.get_json(_quote(it.get("href", ""))) if it.get("href") else None
        common.pause(0.1)
        urls = [u for u in (manifest or []) if isinstance(u, str)]
        small = _pick(urls, ["~small.", "~medium."])
        big = _pick(urls, ["~large.", "~medium."])
        if not small or not big:
            yield {"id": cid, "reject": True}
            continue
        who = (d.get("photographer") or d.get("secondary_creator") or "").strip()
        keywords = " ".join(d.get("keywords") or [])
        yield {
            "id": cid,
            "title": (d.get("title") or "NASA image").strip()[:90],
            "credit": "NASA" + (f" / {who}" if who else ""),
            "license": "NASA media usage guidelines",
            "source": "nasa",
            "sourceUrl": f"https://images.nasa.gov/details/{nid}",
            "thumb_src": small,
            "url": big,
            "hires": _pick(urls, ["~orig."]),
            "text": f"{d.get('description') or ''} {keywords}",
        }
