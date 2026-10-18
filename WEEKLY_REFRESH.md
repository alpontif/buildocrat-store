# Weekly refresh — buildocrat.store

Buildocrat's materials web app at https://buildocrat.store, owned by Engr. Akolade Maruf Ibrahim (Kola), Abuja. Repo alpontif/buildocrat-store is the source of truth; GitHub Pages serves `/docs`.

## Normal week (automatic)
The GitHub Action **Refresh prices from the Rate Book** runs Monday 16:37 Nigeria time, with catch-up runs Wednesday and Friday. It:
1. downloads the Rate Book's latest `rate-data.json` (alpontif/buildocrat-rate-book, refreshed by hand each Monday morning);
2. runs `python3 pipeline/build.py --fetch` (catalogue, 815+ pages, sitemap, feed, open data, llms files, service worker);
3. checks cement and rebar prices are in a sane range;
4. commits and pushes, then pings IndexNow.

It needs Settings → Actions → General → Workflow permissions = **Read and write**.

## Fallback: run it from a chat
Use this if the Action fails or Kola asks for a manual refresh.
1. Attach the repo with add_repo (owner `alpontif`, repo `buildocrat-store`, access `push`) and clone it.
2. Get the Rate Book data: clone https://github.com/alpontif/buildocrat-rate-book (read access is enough) and copy its `rate-data.json` to `pipeline/rate-data.json`. If the Rate Book itself hasn't been refreshed this week, do that first using its own WEEKLY_REFRESH.md.
3. Run `python3 pipeline/build.py`. It should report about 815 indexable pages and ~777 materials.
4. Spot-check: `docs/data/catalog.json` cement M-CEM-01 between ₦5,000 and ₦40,000 a bag; rebar M-STL-01 between ₦400,000 and ₦4,000,000 a tonne.
5. `git add -A docs pipeline`, commit "Price refresh from Rate Book <date>" (author Claude <noreply@anthropic.com>), `git pull --rebase origin main`, `git push origin main`.
6. Run `python3 pipeline/indexnow.py` (or let the next Action do it).
7. Summary for Kola in under 6 lines: prices date used, biggest moves, anything odd.

## Rules
- Never hand-edit prices in this repo: they come only from the Rate Book. Business numbers (margin, bundles, plans, Price Lock, risk defaults) live in `store-config.json`; search-console and analytics IDs in `site-config.json`.
- `docs/CNAME` must stay `buildocrat.store` (the build writes it from `store-config.json` → `site`).
- Don't edit generated pages; edit `pipeline/build.py` or `docs/assets/*` and rebuild.
