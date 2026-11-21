"""HTTP + image helpers shared by every source."""
import io
import os
import time

import requests
from PIL import Image

REPO = os.environ.get("GITHUB_REPOSITORY", "wallora-catalog")
UA = f"WalloraCatalog/1.0 (+https://github.com/{REPO})"

_session = requests.Session()
_session.headers.update({
    "User-Agent": UA,
    "AIC-User-Agent": UA,  # the Art Institute of Chicago asks API users to identify themselves
    "Accept": "application/json, image/*;q=0.8, */*;q=0.5",
})

THUMB_WIDTH = 400


def pause(seconds: float) -> None:
    if not os.environ.get("WALLORA_NO_SLEEP"):
        time.sleep(seconds)


def get_json(url, params=None, retries=3):
    """Returns parsed JSON, or None for 400/404 and after repeated failures."""
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            print(f"  HTTP {r.status_code} for {url} {params or ''}"[:300])
            if r.status_code in (400, 404):
                return None
            pause(2 * (attempt + 1))  # 403/429/5xx: back off and retry
        except (requests.RequestException, ValueError) as e:
            print(f"  request error for {url}: {e}"[:300])
            pause(1 + attempt)
    return None


def get_bytes(url, retries=3, max_bytes=20_000_000):
    for attempt in range(retries):
        try:
            r = _session.get(url, timeout=60)
            if r.status_code == 200 and len(r.content) <= max_bytes:
                return r.content
            if r.status_code in (400, 404):
                return None
            pause(2 * (attempt + 1))
        except requests.RequestException:
            pause(1 + attempt)
    return None


def analyze(raw: bytes):
    """Reads an image: size, dominant colour, light/dark, and a small JPEG thumbnail."""
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
        im = im.convert("RGB")
    except Exception:
        return None
    w, h = im.size
    if w < 2 or h < 2:
        return None
    small = im.resize((48, max(1, round(48 * h / w))))
    q = small.quantize(colors=6)
    palette = q.getpalette() or []
    counts = q.getcolors() or []
    if counts and palette:
        _, idx = max(counts)
        r, g, b = palette[idx * 3: idx * 3 + 3]
    else:
        r, g, b = 128, 128, 128
    avg = small.resize((1, 1)).getpixel((0, 0))
    luma = 0.299 * avg[0] + 0.587 * avg[1] + 0.114 * avg[2]
    tw = min(THUMB_WIDTH, w)
    th = max(1, round(h * tw / w))
    thumb = im.resize((tw, th), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    thumb.save(buf, "JPEG", quality=72, optimize=True, progressive=True)
    return {
        "width": w, "height": h,
        "color": f"{r:02X}{g:02X}{b:02X}",
        "tone": "dark" if luma < 110 else "light",
        "thumb": buf.getvalue(),
    }
