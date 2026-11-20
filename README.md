# Wallora catalog

Builds a catalog of free-to-use wallpapers (public domain / CC0) and publishes it as static JSON on GitHub Pages.
The Wallora apps read it; no server, no API keys in the apps.

Sources: The Met (CC0), Art Institute of Chicago (CC0), NASA Image and Video Library.
Thumbnails are stored here; full images load from the original museum/NASA servers.

## One-time setup
1. Create a **public** repo named `wallora-catalog` and upload everything in this folder (use GitHub Desktop so `.github/` is included).
2. Repo → **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Repo → **Actions → Build catalog → Run workflow**. The first run takes about 10–25 minutes.
4. When it's green, open `https://<your-github-name>.github.io/wallora-catalog/` — you should see the stats page.
   `…/index.json` is the address the apps will use.

It then runs by itself every day and adds up to 120 new wallpapers per run (up to 6000).

## Tuning
- `config/queries.json` — what to search for, per category; `max_aspect` controls how wide an image may be
  (1.0 = portrait or square only; space images allow wider because they crop well).
- `config/blocklist.json` — add ids (like `"met-12345"`) to remove an image for good.

## Catalog format
- `index.json` — totals, categories (with page counts), credits.
- `all/<n>.json` — mixed feed, 40 per page. `c/<category>/<n>.json` — per category.
- Each item: id, title, category, source, credit, license, sourceUrl, thumb, url, hires, aspect, color, tone, added.
