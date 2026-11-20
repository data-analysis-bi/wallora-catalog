"""Builds the Wallora catalog: collect → filter → thumbnails → paged JSON for GitHub Pages."""
import datetime as dt
import json
import os
import random
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from sources import aic, met, nasa  # noqa: E402

SOURCES = {"met": met, "aic": aic, "nasa": nasa}
PAGE_SIZE = 40

# Same ids the apps use, plus "art" (new: paintings and museum pieces).
CATEGORIES = [
    ("minimalist", "Minimalist"), ("amoled", "AMOLED"), ("nature", "Nature"), ("mountains", "Mountains"),
    ("space", "Space"), ("abstract", "Abstract"), ("architecture", "Architecture"), ("cars", "Cars"),
    ("anime", "Anime"), ("technology", "Technology"), ("dark", "Dark Aesthetic"), ("gradients", "Gradients"),
    ("uhd", "4K & Ultra HD"), ("seasonal", "Seasonal"), ("art", "Art"),
]
CREDITS = [
    "The Metropolitan Museum of Art — Open Access (CC0)",
    "Art Institute of Chicago — public domain (CC0)",
    "NASA Image and Video Library — NASA media usage guidelines apply",
]


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def site_base() -> str:
    if os.environ.get("SITE_BASE"):
        return os.environ["SITE_BASE"].rstrip("/") + "/"
    repo = os.environ.get("GITHUB_REPOSITORY", "user/wallora-catalog")
    owner, name = repo.split("/", 1)
    owner = owner.lower()
    return f"https://{owner}.github.io/" + ("" if name.lower() == f"{owner}.github.io" else f"{name}/")


def dims_ok(w, h, max_aspect, f, original=False) -> bool:
    if not w or not h:
        return False
    aspect = w / h
    if not (f["min_aspect"] <= aspect <= max_aspect):
        return False
    if original and min(w, h) < f["min_short_side_original"]:
        return False
    return True


def collect(root: Path, data_dir: Path, today: dt.date, time_budget_s: int):
    cfg = load_json(root / "config" / "queries.json", {})
    f = cfg["filters"]
    items = load_json(data_dir / "items.json", [])
    by_id = {i["id"]: i for i in items}
    rejected = set(load_json(data_dir / "rejected.json", []))
    blocked = set(load_json(root / "config" / "blocklist.json", []))
    rng = random.Random(today.toordinal())
    (data_dir / "thumbs").mkdir(parents=True, exist_ok=True)
    start = time.time()
    added_total = 0
    stats = defaultdict(int)

    def out_of_budget() -> bool:
        return (added_total >= f["max_new_per_run"] or len(by_id) >= f["max_items"]
                or time.time() - start > time_budget_s)

    for source_id, queries in cfg["queries"].items():
        mod = SOURCES.get(source_id)
        if not mod:
            continue
        for qc in queries:
            if out_of_budget():
                break
            seen = set(by_id) | rejected | blocked
            max_aspect = qc.get("max_aspect", f["max_aspect"])
            want = qc.get("per_query", f["per_query"])
            got = tries = 0
            for cand in mod.candidates(qc, seen, rng):
                tries += 1
                if tries > f["max_tries_per_query"] or out_of_budget():
                    break
                cid = cand["id"]
                seen.add(cid)
                if cand.get("reject"):
                    rejected.add(cid)
                    continue
                text = f"{cand.get('title', '')} {cand.get('text', '')}".lower()
                if any(k in text for k in f["block_keywords"]):
                    rejected.add(cid)
                    continue
                pre = cand.get("pre_dims")
                if pre and not dims_ok(pre[0], pre[1], max_aspect, f, original=True):
                    rejected.add(cid)
                    continue
                raw = common.get_bytes(cand["thumb_src"])
                if not raw:
                    continue  # network hiccup: try again on a later run
                info = common.analyze(raw)
                if not info:
                    rejected.add(cid)
                    continue
                w, h = pre or (info["width"], info["height"])
                if not pre and max(info["width"], info["height"]) < f["min_long_side_analysis"]:
                    rejected.add(cid)
                    continue
                if not dims_ok(w, h, max_aspect, f):
                    rejected.add(cid)
                    continue
                (data_dir / "thumbs" / f"{cid}.jpg").write_bytes(info["thumb"])
                by_id[cid] = {
                    "id": cid, "title": cand["title"], "category": qc["category"], "source": cand["source"],
                    "credit": cand["credit"], "license": cand["license"], "sourceUrl": cand["sourceUrl"],
                    "url": cand["url"], "hires": cand.get("hires"),
                    "aspect": round(w / h, 3), "color": info["color"], "tone": info["tone"],
                    "added": today.isoformat(),
                }
                got += 1
                added_total += 1
                stats[cand["source"]] += 1
                if got >= want:
                    break

    items = sorted(by_id.values(), key=lambda i: (i["added"], i["id"]), reverse=True)
    (data_dir / "items.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    (data_dir / "rejected.json").write_text(json.dumps(sorted(rejected)[-60000:]), encoding="utf-8")
    print(f"Added {added_total} new items {dict(stats)}; catalog now has {len(items)}; rejected {len(rejected)}.")
    return items


def write_pages(folder: Path, lst, base: str) -> int:
    if not lst:
        return 0
    folder.mkdir(parents=True, exist_ok=True)
    pages = (len(lst) + PAGE_SIZE - 1) // PAGE_SIZE
    for p in range(pages):
        chunk = []
        for it in lst[p * PAGE_SIZE:(p + 1) * PAGE_SIZE]:
            out = dict(it)
            out["thumb"] = f"{base}thumbs/{it['id']}.jpg"
            chunk.append(out)
        (folder / f"{p + 1}.json").write_text(
            json.dumps({"page": p + 1, "pages": pages, "items": chunk}, ensure_ascii=False), encoding="utf-8")
    return pages


def round_robin(lists):
    out, i = [], 0
    while any(i < len(l) for l in lists):
        for l in lists:
            if i < len(l):
                out.append(l[i])
        i += 1
    return out


def build_site(items, data_dir: Path, site_dir: Path, base: str, today: dt.date):
    if site_dir.exists():
        shutil.rmtree(site_dir)
    (site_dir / "thumbs").mkdir(parents=True)
    kept = []
    for it in items:
        src = data_dir / "thumbs" / f"{it['id']}.jpg"
        if src.exists():
            shutil.copy(src, site_dir / "thumbs" / src.name)
            kept.append(it)
    by_cat = defaultdict(list)
    for it in kept:
        by_cat[it["category"]].append(it)
    cats = []
    for cid, title in CATEGORIES:
        lst = by_cat.get(cid, [])
        cats.append({"id": cid, "title": title, "count": len(lst), "pages": write_pages(site_dir / "c" / cid, lst, base)})
    mixed = round_robin([by_cat[c] for c, _ in CATEGORIES if by_cat.get(c)])
    all_pages = write_pages(site_dir / "all", mixed, base)
    index = {
        "version": 1, "generated": today.isoformat(), "base": base, "pageSize": PAGE_SIZE,
        "total": len(kept), "all": {"pages": all_pages}, "categories": cats, "credits": CREDITS,
        "note": "Images are linked from their original museum/NASA servers; thumbnails are hosted here.",
    }
    (site_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    rows = "".join(f"<li>{c['title']}: {c['count']}</li>" for c in cats if c["count"])
    credits = "".join(f"<li>{c}</li>" for c in CREDITS)
    (site_dir / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><title>Wallora catalog</title>"
        f"<h1>Wallora catalog</h1><p>{len(kept)} wallpapers · updated {today}</p><ul>{rows}</ul>"
        f"<h2>Sources &amp; licences</h2><ul>{credits}</ul><p><a href='index.json'>index.json</a></p>",
        encoding="utf-8")
    size_mb = sum(p.stat().st_size for p in site_dir.rglob("*") if p.is_file()) / 1e6
    print(f"Site built: {len(kept)} items, {size_mb:.1f} MB (GitHub Pages limit is 1000 MB).")
    if size_mb > 800:
        print("WARNING: site is getting close to the 1 GB Pages limit; lower max_items in config/queries.json.")


def run(root: Path, today: dt.date | None = None, time_budget_s: int = 1500):
    today = today or dt.date.today()
    data_dir, site_dir = root / "data", root / "site"
    items = collect(root, data_dir, today, time_budget_s)
    build_site(items, data_dir, site_dir, site_base(), today)


if __name__ == "__main__":
    run(Path(__file__).resolve().parent.parent)
