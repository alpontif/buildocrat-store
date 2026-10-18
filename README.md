# buildocrat.store — Buildocrat materials web app

Buy, stockpile, sell and source building materials across Nigeria, and control project risk. Every journey ends in a prefilled WhatsApp chat with Buildocrat on +234 701 802 4292, carrying a reference number (BDC-B/S/L/V/Q/R-YYMMDD-XXXX). Nothing is charged on the site; payment is agreed and invoiced in the chat.

| Journey | Page | WhatsApp message |
|---|---|---|
| Buy | `/buy/` + 777 material pages under `/materials/` | Order: items, quantities, state prices, delivery address, payment preference |
| Stockpile | `/stockpile/` (Special offers tab) | Bundle reservation with chosen plan (pay in full / 3-month / 6-month) |
| Stockpile | `/stockpile/#lock` (Price Lock tab) | Price Lock request: locked unit prices, deposit, monthly draw-down |
| Sell | `/sell/` | Supplier listing: business, CAC, delivery, credit terms, products and prices |
| Source | `/source/` | Sourcing request / RFQ with lines, deadline, certificates, imports |
| Risk control | `/risk-control/` | Risk review: budget, price exposure, selected risks mapped to services |

Visitors' sent requests are kept on their device at `/requests/` so they can reopen the chat.

## Where things live

| Path | What it is |
|---|---|
| `store-config.json` | **Business settings**: margin, state uplifts, bundles, plans, Price Lock deposits and spreads, risk assumptions, contacts. |
| `pipeline/build.py` | Builds everything in `docs/` from the Rate Book data and the config. |
| `pipeline/rate-data.json` | Copy of the Rate Book's data used for the last build. |
| `docs/assets/app.css`, `docs/assets/app.js` | Hand-written front end (never generated). |
| `docs/` | The published site (GitHub Pages, custom domain `buildocrat.store`). |
| `.github/workflows/refresh.yml` | Mondays 16:37 Nigeria time (+ Wed/Fri catch-up): fetch the Rate Book's latest `rate-data.json`, rebuild, sanity-check, commit, ping IndexNow. |

## Prices

Selling price = Rate Book market price (Abuja) × (1 + `buyMargin`) × the state's factor. States use the nearest Rate Book city factor (Abuja, Lagos, Port Harcourt, Ibadan, Osogbo, Kano, Kaduna, Enugu, Benin, Uyo, Jos) plus `stateExtra` for remote states. Delivery is always quoted on WhatsApp.

## Changing things

Edit `store-config.json`, then run `python3 pipeline/build.py` (or trigger the workflow from the Actions tab) and push. To rebuild with the newest Rate Book data locally: `python3 pipeline/build.py --fetch`.
