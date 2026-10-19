#!/usr/bin/env python3
"""Build buildocrat.store from the Nigeria Construction Rate Book data.

Usage:
  python3 pipeline/build.py                 # uses pipeline/rate-data.json (download it first)
  python3 pipeline/build.py --fetch         # downloads the latest rate-data.json, then builds
  python3 pipeline/build.py --data PATH     # builds from a local copy

Writes everything the site needs into docs/: catalogue JSON, every static page,
sitemap, llms.txt, manifest, service worker. Hand-written assets live in
docs/assets/ (app.css, app.js) and are never generated.
"""
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
PIPE = os.path.join(ROOT, "pipeline")
CFG = json.load(open(os.path.join(ROOT, "store-config.json"), encoding="utf-8"))
SCFG = json.load(open(os.path.join(ROOT, "site-config.json"), encoding="utf-8"))
SITE = CFG["site"].rstrip("/")
e = html.escape

# ---------------------------------------------------------------- groups ---
# rate-book group name -> (slug, display name, section)
GROUPS = [
    ("Cement, Binders & Admixtures", "cement", "Cement, binders & admixtures", "building"),
    ("Reinforcement & Steel", "reinforcement-steel", "Iron rods, steel & mesh", "building"),
    ("Blocks, Bricks & Precast", "blocks-bricks-precast", "Blocks, bricks & precast", "building"),
    ("Aggregates, Fill & Soils (Delivered Abuja)", "aggregates", "Sand, granite & fill", "building"),
    ("Roofing, Cladding & Rainwater", "roofing", "Roofing, cladding & gutters", "building"),
    ("Timber & Boards", "timber", "Timber & boards", "building"),
    ("Concrete Supply & Site Sundries", "concrete", "Ready-mix concrete & site sundries", "building"),
    ("Waterproofing & Dpc", "waterproofing", "Waterproofing & DPC", "building"),
    ("Doors, Windows, Joinery & Ironmongery", "doors-windows", "Doors, windows & ironmongery", "building"),
    ("Plumbing, Sanitary & Water", "plumbing", "Plumbing & sanitary ware", "building"),
    ("Floor & Wall Finishes", "tiles-floor-finishes", "Tiles & floor finishes", "building"),
    ("Paints & Coatings", "paint", "Paints & coatings", "building"),
    ("Ceilings, Partitions & Glass", "ceilings-glass", "Ceilings, POP, partitions & glass", "building"),
    ("Architectural Finishes (Additional)", "architectural-finishes", "Architectural finishes", "building"),
    ("Electrical", "electrical", "Electrical", "building"),
    ("HVAC, Lifts & ICT", "hvac-ict", "Air-conditioning, lifts & ICT", "building"),
    ("Fire Protection", "fire-protection", "Fire protection", "building"),
    ("Hand Tools & Small Equipment", "tools", "Tools & small equipment", "building"),
    ("Safety & PPE (Additional)", "safety-ppe", "Safety & PPE", "building"),
    ("Utilities", "site-water", "Site water", "building"),
    ("Roads & External Works", "roads", "Roads & external works", "infrastructure"),
    ("Roads & Highways (Additional)", "roads", "Roads & external works", "infrastructure"),
    ("Water Supply & Sewerage", "water-supply-sewerage", "Water supply & sewerage", "infrastructure"),
    ("Geosynthetics & Erosion Control", "geosynthetics", "Geosynthetics & erosion control", "infrastructure"),
    ("Piling & Ground Engineering", "piling", "Piling & ground engineering", "infrastructure"),
    ("Power Transmission & Distribution", "power", "Power transmission & distribution", "infrastructure"),
    ("Bridges & Heavy Structures", "bridges", "Bridges & heavy structures", "infrastructure"),
    ("Marine, Ports & Reclamation", "marine", "Marine, ports & reclamation", "infrastructure"),
    ("Railways", "railways", "Railway materials", "infrastructure"),
    ("Industrial Buildings", "industrial", "Industrial buildings", "infrastructure"),
    ("Oil & Gas: Line Pipe, Fittings & Valves", "oil-gas", "Oil & gas pipe, fittings & valves", "infrastructure"),
    ("Oil & Gas: Coating, Cathodic Protection & Welding", "oil-gas", "Oil & gas pipe, fittings & valves", "infrastructure"),
    ("Oil & Gas: Fuel Stations & Storage", "oil-gas", "Oil & gas pipe, fittings & valves", "infrastructure"),
]
GMAP = {g[0]: g for g in GROUPS}
GROUP_INTRO = {
    "cement": "Dangote, BUA and HBM cement by the bag or trailer, plus tile adhesive, POP, putty and admixtures.",
    "reinforcement-steel": "High-yield iron rods (8–32 mm) by the length or tonne, binding wire, BRC mesh, sections and nails.",
    "blocks-bricks-precast": "Sandcrete blocks, interlocking paving, kerbs, lintels, drains and culverts.",
    "aggregates": "Sharp sand, plaster sand, granite, laterite and stone base by the tipper load or tonne.",
    "roofing": "Longspan aluminium, stone-coated tiles, ridges, screws, fascia, gutters and insulation.",
    "timber": "Hardwood lengths, planks, marine board, plywood, MDF and props.",
}

STATES = {
    # state: hub city in the rate book
    "FCT (Abuja)": "Abuja (FCT)", "Niger": "Abuja (FCT)", "Nasarawa": "Abuja (FCT)", "Kogi": "Abuja (FCT)",
    "Lagos": "Lagos", "Ogun": "Lagos",
    "Oyo": "Ibadan",
    "Osun": "Osogbo (Osun)", "Ekiti": "Osogbo (Osun)", "Ondo": "Osogbo (Osun)", "Kwara": "Osogbo (Osun)",
    "Kano": "Kano", "Jigawa": "Kano", "Katsina": "Kano", "Bauchi": "Kano", "Gombe": "Kano", "Yobe": "Kano",
    "Borno": "Kano", "Sokoto": "Kano", "Kebbi": "Kano", "Zamfara": "Kano",
    "Kaduna": "Kaduna",
    "Enugu": "Enugu", "Anambra": "Enugu", "Ebonyi": "Enugu", "Imo": "Enugu", "Abia": "Enugu",
    "Edo": "Benin City", "Delta": "Benin City",
    "Rivers": "Port Harcourt", "Bayelsa": "Port Harcourt",
    "Akwa Ibom": "Uyo", "Cross River": "Uyo",
    "Plateau": "Jos", "Benue": "Jos", "Taraba": "Jos", "Adamawa": "Jos",
}

# ----------------------------------------------------------------- utils ---
def nice(x):
    """Round a naira price to a sensible step (mirrors app.js)."""
    if x is None:
        return None
    step = 10 if x < 1000 else 50 if x < 100000 else 100 if x < 1000000 else 1000
    return int(round(x / step) * step)


def naira(x):
    return "₦" + format(int(round(x)), ",")


def slugify(s):
    s = s.lower().replace("&", " and ").replace('"', " inch ").replace("½", "half").replace("¼", "quarter")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:70].rstrip("-")


def write(path, text):
    full = os.path.join(DOCS, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(text)


def fdate(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


UNIT_WORD = {"nr": "each", "bag": "bag", "t": "tonne", "load": "load", "m2": "m²", "m3": "m³", "m": "metre",
             "length": "length", "L": "litre", "kg": "kg", "roll": "roll", "pail": "pail", "tin": "tin",
             "sheet": "sheet", "set": "set", "pair": "pair", "pack": "pack", "coil": "coil"}


def unit_word(u):
    return UNIT_WORD.get(u, u)


# ------------------------------------------------------------------ data ---
def load_rate_data(argv):
    path = os.path.join(PIPE, "rate-data.json")
    if "--data" in argv:
        path = argv[argv.index("--data") + 1]
    elif "--fetch" in argv:
        req = urllib.request.Request(CFG["rateDataUrl"], headers={"User-Agent": "buildocrat-store-build"})
        raw = urllib.request.urlopen(req, timeout=60).read()
        json.loads(raw)  # validate before overwriting
        with open(path, "wb") as f:
            f.write(raw)
    return json.load(open(path, encoding="utf-8"))


NAME_FIX = {
    "M-CEM-01": "OPC 42.5 cement, 50kg (Dangote, BUA or HBM, best available)",
}


def clean_name(r):
    """Customer-facing name: drop estimator wording the rate book uses."""
    if r["c"] in NAME_FIX:
        return NAME_FIX[r["c"]]
    s = re.sub(r"\s*-\s*adopted market average", "", r["d"])
    s = re.sub(r",\s*per (t|tonne|m2|m3|kg|litre)$", "", s)
    return s.strip()


def build_catalog(d):
    res = {r["c"]: r for r in d["resources"]}

    def val(code, key="r"):
        r = res[code]
        k = r.get("k")
        if k:
            if key != "r" and k.get("s"):
                return val(k["b"], "r") * k["f"] * (1 - k["s"] if key == "lo" else 1 + k["s"])
            return val(k["b"], key) * k["f"]
        v = r.get(key)
        return r.get("r") if v is None else v

    margin = 1 + CFG["buyMargin"]
    items, groups, used = [], {}, set()
    for r in d["resources"]:
        g = GMAP.get(r["g"])
        if not g or r.get("cat") == "Subcontract" or r.get("u") == "kWh":
            continue
        k = r.get("k")
        if k and res[k["b"]].get("u") in ("load", "pail", "roll", "tin"):
            continue  # per-tonne/per-litre slices of a bulk pack: buyers order the pack
        try:
            p = val(r["c"])
        except KeyError:
            continue
        if not p:
            continue
        _, gslug, gname, sec = g
        name = clean_name(r)
        slug = slugify(f'{r["c"]} {name}')
        while slug in used:
            slug += "-x"
        used.add(slug)
        pr = r.get("pr") if not k else (val(k["b"], "pr") * k["f"] if res[k["b"]].get("pr") else None)
        sf = bool(re.search(r"supply\s*&\s*fix|installed", r["d"], re.I))
        items.append({
            "c": r["c"], "d": name, "u": r["u"], "g": gslug, "cat": r.get("cat", ""),
            "p": nice(p * margin), "lo": nice(val(r["c"], "lo") * margin), "hi": nice(val(r["c"], "hi") * margin),
            "pr": nice(pr * margin) if pr else None, "set": r.get("set"), "conf": r.get("conf"),
            "s": f"/materials/{gslug}/{slug}/", "lk": 1 if gslug in CFG["priceLock"]["eligibleGroups"] else 0,
            "sf": 1 if sf else 0, "note": "" if re.search(r"build-?up|adopted|derived|\bitems?\b", r.get("n") or "", re.I) else (r.get("n") or ""),
        })
        gg = groups.setdefault(gslug, {"s": gslug, "n": gname, "sec": sec, "count": 0})
        gg["count"] += 1

    order = []
    for g in GROUPS:
        if g[1] in groups and g[1] not in order:
            order.append(g[1])
    loc = {l[0]: l[1] for l in d["locations"]}
    states = []
    for st in sorted(STATES, key=lambda s: (s != "FCT (Abuja)", s)):
        hub = STATES[st]
        states.append({"n": st, "hub": hub, "f": round(loc[hub] * (1 + CFG["stateExtra"].get(st, 0)), 4)})

    by = {i["c"]: i for i in items}
    bundles = []
    for b in CFG["bundleList"]:
        missing = [c for c, _ in b["lines"] if c not in by]
        if missing:
            print("  ! bundle", b["id"], "skips missing codes", missing)
        bb = dict(b)
        bb["lines"] = [l for l in b["lines"] if l[0] in by]
        bundles.append(bb)

    watch = [c for c in ["M-CEM-07", "M-STL-01", "M-BLK-01", "M-AGG-01", "M-RF-01", "M-AGG-07", "M-STL-12", "M-CEM-08"] if c in by]
    return {
        "updated": d["meta"]["updated"], "fx": d["meta"].get("fx"), "margin": CFG["buyMargin"],
        "groups": [groups[s] for s in order], "states": states, "items": items, "bundles": bundles,
        "plans": CFG["bundles"]["plans"], "payInFullDiscount": CFG["bundles"]["payInFullDiscount"],
        "holdMonths": CFG["bundles"]["holdMonths"], "lock": {k: v for k, v in CFG["priceLock"].items() if not k.startswith("_")},
        "risk": {k: v for k, v in CFG["risk"].items() if not k.startswith("_")}, "watch": watch,
    }


# ----------------------------------------------------------------- icons ---
ICON = {
    "cart": '<path d="M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 8H6.2"/><circle cx="10" cy="20" r="1.4"/><circle cx="17" cy="20" r="1.4"/>',
    "stack": '<path d="M12 3 3 7.5 12 12l9-4.5L12 3Z"/><path d="m3 12 9 4.5 9-4.5"/><path d="m3 16.5 9 4.5 9-4.5"/>',
    "tag": '<path d="M3 12V4h8l10 10-8 8L3 12Z"/><circle cx="7.5" cy="8" r="1.5"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
    "shield": '<path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6L12 3Z"/><path d="m8.8 12 2.2 2.2 4.4-4.4"/>',
    "lock": '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
    "chat": '<path d="M20 11.5a8 8 0 0 1-11.7 7.1L4 20l1.4-4.1A8 8 0 1 1 20 11.5Z"/>',
    "truck": '<path d="M2.5 6h11v9.5h-11z"/><path d="M13.5 9.5h4l3 3.2v2.8h-7"/><circle cx="6.5" cy="17.5" r="1.7"/><circle cx="17" cy="17.5" r="1.7"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "arrow": '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "pin": '<path d="M12 21s-6.5-6.2-6.5-11a6.5 6.5 0 0 1 13 0c0 4.8-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.3"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "arrow-ur": '<path d="M7 17 17 7"/><path d="M8 7h9v9"/>',
    "bag": '<path d="M6 7h12l1 13H5L6 7Z"/><path d="M9 7V5a3 3 0 0 1 6 0v2"/>',
    "rebar": '<path d="M5 19 19 5M9 21 21 9M3 15 15 3"/>',
    "brick": '<rect x="3" y="6" width="18" height="12" rx="1.5"/><path d="M3 12h18M9 6v6M15 12v6"/>',
    "heap": '<path d="M3 19h18l-6-10-3 4-2-3-7 9Z"/>',
    "roof": '<path d="M3 11 12 4l9 7"/><path d="M6 10v9h12v-9"/>',
    "plank": '<rect x="3" y="8" width="18" height="8" rx="1.5"/><path d="M7 12h6"/>',
    "box": '<path d="M4 8l8-4 8 4v8l-8 4-8-4V8Z"/><path d="m4 8 8 4 8-4M12 12v8"/>',
    "tap": '<path d="M5 9h8a3 3 0 0 1 3 3v2"/><path d="M9 6v3M5 6h8M16 17v2"/>',
    "bolt": '<path d="M13 3 5 14h6l-1 7 8-11h-6l1-7Z"/>',
    "paint": '<rect x="4" y="4" width="13" height="6" rx="1.5"/><path d="M17 7h3v5h-8v3"/><path d="M12 15v5"/>',
    "tile": '<rect x="4" y="4" width="16" height="16" rx="1.5"/><path d="M12 4v16M4 12h16"/>',
    "door": '<rect x="6" y="3" width="12" height="18" rx="1"/><path d="M14 12h.01"/>',
    "drop": '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11Z"/>',
    "download": '<path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M5 20h14"/>',
    "list": '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
}


GROUP_ICON = {"cement": "bag", "reinforcement-steel": "rebar", "blocks-bricks-precast": "brick", "aggregates": "heap",
              "roofing": "roof", "timber": "plank", "concrete": "box", "waterproofing": "drop", "doors-windows": "door",
              "plumbing": "tap", "tiles-floor-finishes": "tile", "paint": "paint", "ceilings-glass": "tile",
              "architectural-finishes": "tile", "electrical": "bolt", "hvac-ict": "bolt", "fire-protection": "drop",
              "tools": "box", "safety-ppe": "shield", "site-water": "drop", "roads": "heap", "water-supply-sewerage": "tap",
              "geosynthetics": "tile", "piling": "rebar", "power": "bolt", "bridges": "rebar", "marine": "drop",
              "railways": "rebar", "industrial": "roof", "oil-gas": "tap"}


def icon(name, cls="ic"):
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{ICON[name]}</svg>'


WA_SVG = ('<svg class="ic" viewBox="0 0 24 24" aria-hidden="true" style="fill:currentColor;stroke:none">'
          '<path d="M12 2.2a9.7 9.7 0 0 0-8.3 14.8L2.3 21.8l4.9-1.3A9.7 9.7 0 1 0 12 2.2Zm0 17.7c-1.5 0-3-.4-4.2-1.2l-.3-.2-2.9.8.8-2.8-.2-.3A8 8 0 1 1 12 19.9Zm4.4-6c-.2-.1-1.4-.7-1.7-.8-.2-.1-.4-.1-.5.1l-.8 1c-.1.2-.3.2-.5.1a6.6 6.6 0 0 1-3.3-2.9c-.2-.4.2-.4.7-1.3.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.5-.4h-.5a.9.9 0 0 0-.6.3 2.7 2.7 0 0 0-.8 2c0 1.2.9 2.3 1 2.5.1.2 1.7 2.6 4.2 3.6 1.6.7 2.2.7 3 .6.5-.1 1.4-.6 1.6-1.1.2-.6.2-1 .1-1.1l-.5-.3Z"/></svg>')

JOURNEYS = [
    ("buy", "/buy/", "Buy", "cart", "Cement, iron rods, blocks, sand, roofing and 800+ more lines at checked prices, delivered to any state."),
    ("stockpile", "/stockpile/", "Stockpile", "stack", "Special bundle offers and Price Lock: fix today's price, pay over time, take delivery when you're ready."),
    ("sell", "/sell/", "Sell", "tag", "Manufacturers, dealers, quarries and people with surplus stock: list your materials with us."),
    ("source", "/source/", "Source", "search", "Send us your list or BoQ. We find the materials, compare suppliers and quote you on WhatsApp."),
    ("risk", "/risk-control/", "Risk control", "shield", "Check how much price rises could add to your project, then cover it with locks, escrow and checks."),
]


# ---------------------------------------------------------------- layout ---
def head_analytics():
    """GA4 gtag.js (and optional Cloudflare beacon) for every page head. One copy only."""
    analytics = ""
    if SCFG.get("ga4_measurement_id"):
        gid = e(SCFG["ga4_measurement_id"])
        analytics += (f'<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script>'
                      f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{gid}');"
                      f"document.addEventListener('click',function(ev){{var el=ev.target,a=el&&el.closest?el.closest('a'):null;"
                      f"if(!a&&el&&el.parentElement&&el.parentElement.closest)a=el.parentElement.closest('a');"
                      f"if(!a||!a.href)return;var u=a.href;"
                      f"if(/wa\\.me|api\\.whatsapp\\.com/.test(u))gtag('event','whatsapp_click',{{link_url:u}});"
                      f"else if(u.indexOf('mailto:')===0)gtag('event','email_click',{{link_url:u}});}});</script>")
    if SCFG.get("cloudflare_web_analytics_token"):
        analytics += (f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
                      f'data-cf-beacon=\'{{"token": "{e(SCFG["cloudflare_web_analytics_token"])}"}}\'></script>')
    return analytics


def layout(path, title, desc, body, page, ver, jsonld=None, crumbs=None, noindex=False):
    canon = SITE + path
    nav = "".join(
        f'<a href="{href}" class="nav-{key}"{" aria-current=\"page\"" if page == key else ""}>{icon(ic)}<span>{lab}</span></a>'
        for key, href, lab, ic, _ in JOURNEYS)
    ld = []
    if jsonld:
        ld += jsonld if isinstance(jsonld, list) else [jsonld]
    if crumbs:
        ld.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": SITE + u} for i, (n, u) in enumerate(crumbs)]})
    ld_html = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld)
    crumb_html = ""
    if crumbs and len(crumbs) > 1:
        crumb_html = '<nav class="crumbs wrap" aria-label="Breadcrumb">' + " <span>/</span> ".join(
            f'<a href="{u}">{e(n)}</a>' if i < len(crumbs) - 1 else f"<span aria-current=\"page\">{e(n)}</span>"
            for i, (n, u) in enumerate(crumbs)) + "</nav>"
    verify = ""
    if SCFG.get("google_site_verification"):
        verify += f'<meta name="google-site-verification" content="{e(SCFG["google_site_verification"])}">\n'
    if SCFG.get("bing_site_verification"):
        verify += f'<meta name="msvalidate.01" content="{e(SCFG["bing_site_verification"])}">\n'
    analytics = head_analytics()
    boot = json.dumps({"wa": CFG["whatsapp"], "waDisplay": CFG["whatsappDisplay"], "email": CFG["email"], "v": ver,
                       "page": page})
    return f"""<!doctype html>
<html lang="en-NG">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{canon}">
{'<meta name="robots" content="noindex">' if noindex else ''}
<meta name="theme-color" content="#D5DFDB" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0D1412" media="(prefers-color-scheme: dark)">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Buildocrat">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{SITE}/og.png">
<meta name="twitter:card" content="summary_large_image">
{verify}<link rel="manifest" href="/manifest.webmanifest">
<link rel="alternate" type="application/rss+xml" title="Buildocrat price updates" href="/feed.xml">
<link rel="icon" href="/icons/icon-192.png" type="image/png">
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/app.css?v={ver}">
{ld_html}
{analytics}
</head>
<body data-page="{page}">
<a class="skip" href="#main">Skip to content</a>
<header class="top">
  <div class="wrap top-row">
    <a class="brand" href="/" aria-label="Buildocrat home"><span class="brand-mark"><svg viewBox="0 0 40 26" aria-hidden="true"><circle cx="13" cy="13" r="12" fill="#165E57"/><circle cx="27" cy="13" r="12" fill="#C7E8A4" fill-opacity=".92"/></svg></span><span class="brand-word">Buildocrat</span></a>
    <button class="state-btn loc-btn" type="button" data-state-btn aria-label="Delivery state: change where prices are for">{icon("pin")}<span class="loc-txt"><small>Deliver to</small><span data-state-label>FCT (Abuja)</span></span><svg class="ic chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></button>
    <button class="state-btn install-btn" type="button" data-install hidden aria-label="Install the Buildocrat app">{icon("download")}<span>Install</span></button>
    <a class="cart-btn" href="/buy/#cart" aria-label="Your cart">{icon("cart")}<span class="cart-count" data-cart-count hidden>0</span></a>
  </div>
  <nav class="tabs" aria-label="Main"><div class="wrap tabs-row">{nav}</div></nav>
</header>
{crumb_html}
<main id="main">
{body}
</main>
<footer class="foot">
  <div class="wrap foot-grid">
    <div>
      <a class="brand brand-foot" href="/"><span class="brand-mark"><svg viewBox="0 0 40 26" aria-hidden="true"><circle cx="13" cy="13" r="12" fill="#165E57"/><circle cx="27" cy="13" r="12" fill="#C7E8A4" fill-opacity=".92"/></svg></span><span class="brand-word">Buildocrat</span></a>
      <p>Buy, stockpile, sell and source building materials across Nigeria, with your price locked when it matters.</p>
      <p class="co-line">{e(CFG["legalName"])}<br>CAC RC {CFG["rc"]}<br>{e(CFG["address"])}</p>
    </div>
    <div>
      <h2>Talk to us</h2>
      <p><a href="https://wa.me/{CFG["whatsapp"]}" rel="noopener">{WA_SVG} WhatsApp {e(CFG["whatsappDisplay"])}</a></p>
      <p><a href="mailto:{CFG["email"]}">{e(CFG["email"])}</a></p>
      <p class="small">We only take payment into an account in the name of <strong>{e(CFG["legalName"])} (RC {CFG["rc"]})</strong>, shared in the chat from this number. Never pay a personal account.</p>
    </div>
    <div>
      <h2>Explore</h2>
      <p><a href="/materials/">All materials &amp; prices</a></p>
      <p><a href="/help/">How it works &amp; FAQ</a></p>
      <p><a href="/requests/">My requests</a></p>
      <p><a href="/materials/#open-data">Open price data (CSV / JSON)</a></p>
      <p><button class="linkbtn" type="button" data-install hidden>Install the app</button></p>
      <p><a href="{CFG["rateBookUrl"]}">Nigeria Construction Rate Book</a></p>
      <p><a href="{CFG["landValueUrl"]}">Nigeria Land Value Book</a></p>
    </div>
  </div>
  <p class="wrap small foot-note">Prices are Buildocrat selling prices built from the weekly Nigeria Construction Rate Book, Abuja base adjusted for your state. Delivery is quoted per order. Every order is confirmed in writing on WhatsApp before you pay.</p>
</footer>
<a class="wa-float" href="https://wa.me/{CFG["whatsapp"]}" rel="noopener" aria-label="Chat with Buildocrat on WhatsApp">{WA_SVG}</a>
<div class="sheet" data-sheet hidden></div>
<script>window.BDC={boot};</script>
<script src="/assets/app.js?v={ver}" defer></script>
<script src="/assets/pwa.js?v={ver}" defer></script>
</body>
</html>
"""


# ----------------------------------------------------------------- pages ---
def item_row(i):
    return (f'<li class="mrow" data-code="{i["c"]}"><span class="mi">{icon(GROUP_ICON.get(i["g"], "box"))}</span><a href="{i["s"]}"><span class="mname">{e(i["d"])}</span>'
            f'<span class="munit">per {e(unit_word(i["u"]))}</span></a>'
            f'<span class="mprice" data-price="{i["c"]}">{naira(i["p"])}</span></li>')


def bar_html(i):
    lo, hi, p = i["lo"], i["hi"], i["p"]
    mn, mx = lo * 0.82, hi * 1.06
    f = lambda v: max(0, min(100, (v - mn) / (mx - mn) * 100))
    cap = BAR_CAP.get(i["c"], i["c"][2:5])
    return (f'<a class="pbar" href="{i["s"]}" title="{e(i["d"])}: {naira(lo)} – {naira(hi)}, today {naira(p)}">'
            f'<span class="rail"><span class="rng" style="bottom:0;height:{f(hi):.0f}%"></span>'
            f'<span class="now" style="height:{f(p):.0f}%"></span></span><span class="cap">{cap}</span></a>')


BAR_CAP = {"M-CEM-07": "CEM", "M-CEM-08": "BUA", "M-STL-01": "ROD", "M-BLK-01": "BLK", "M-AGG-01": "SND",
           "M-RF-01": "RF", "M-AGG-07": "GRN", "M-STL-12": "12MM"}


def coin(variant="teal"):
    a, b = ("#165E57", "#C7E8A4") if variant == "teal" else ("#C7E8A4", "#FFFFFF")
    return (f'<svg class="coin" viewBox="0 0 38 38" aria-hidden="true"><circle cx="19" cy="19" r="18" fill="{a}"/>'
            f'<path d="M10 22c3-7 15-9 18-4M10 16c3 5 14 6 18-1" stroke="{b}" stroke-width="3" fill="none" stroke-linecap="round"/></svg>')


def page_home(cat, ver):
    by = {i["c"]: i for i in cat["items"]}
    hero = by["M-CEM-07"]
    ch = (hero["p"] - hero["pr"]) / hero["pr"] if hero.get("pr") else 0
    pill = (f'<span class="pill">{"↗" if ch > 0 else "↘"} {abs(ch) * 100:.1f}%</span>' if ch else '<span class="pill">steady</span>')
    rows = "".join(
        f'<a class="prow-l" href="{by[c]["s"]}">{icon(GROUP_ICON.get(by[c]["g"], "box"))}<span class="t"><b>{e(short_name(by[c]))}</b>'
        f'<span>per {e(unit_word(by[c]["u"]))} · checked {fdate(by[c]["set"] or cat["updated"])}</span></span>'
        f'<span class="amt" data-price="{c}">{naira(by[c]["p"])}</span></a>' for c in ["M-STL-01", "M-BLK-01", "M-AGG-01", "M-RF-01"] if c in by)
    bars = "".join(bar_html(by[c]) for c in cat["watch"])
    trailer = next((b for b in cat["bundles"] if b["id"] == "cement-trailer"), cat["bundles"][0])
    tm = sum(by[c]["p"] * q for c, q in trailer["lines"])
    lockv, lockd = 12000000, 0.10
    cards = "".join(
        f'<a class="jcard j-{k}" href="{h}"><span class="jicon">{icon(ic)}</span><span class="jtitle">{lab}</span>'
        f'<span class="jtext">{t}</span><span class="jgo">{icon("arrow-ur")}</span></a>' for k, h, lab, ic, t in JOURNEYS)
    groups = "".join(
        f'<a class="gchip" href="/materials/{g["s"]}/">{icon(GROUP_ICON.get(g["s"], "box"))}{e(g["n"])} <span>{g["count"]}</span></a>'
        for g in cat["groups"] if g["sec"] == "building")
    body = f"""
<section class="wrap bento">
  <div class="bx hero-card s7">
    <p class="eyebrow">Nigeria's price-certain materials desk</p>
    <h1>Buy, stockpile, sell and source building materials with Buildocrat. <em>Lock the price.</em></h1>
    <p class="lede">Pick what you need, see a checked price for your state, and finish on WhatsApp with a real person. You pay only after we confirm stock, delivery and the final invoice.</p>
    <div class="tiles">
      <a class="tile tile-mint" href="/buy/"><span class="tl">Shop materials</span><span class="tile-ic">{icon("cart")}</span></a>
      <a class="tile tile-teal" href="/stockpile/#lock"><span class="tl">Lock a price</span><span class="tile-ic">{icon("lock")}</span></a>
    </div>
    <ul class="trust">
      <li>{icon("check")} Weekly <a href="{CFG["rateBookUrl"]}">Rate Book</a> prices</li>
      <li>{icon("check")} All 36 states + FCT</li>
      <li>{icon("check")} RC {CFG["rc"]}</li>
    </ul>
  </div>
  <div class="bx pcard s5">
    <div class="pcard-top">
      <div class="bx-head"><span class="mask">**** RC {CFG["rc"]}</span>{coin()}</div>
      <span class="lbl">{e(short_name(hero))} · <b data-state-label>FCT (Abuja)</b> <button class="chg" type="button" data-state-btn>Change</button></span>
      <div class="bx-head" style="align-items:flex-end;margin:0"><div class="big-num" data-price="{hero["c"]}">{naira(hero["p"])}</div>{pill}</div>
    </div>
    <div class="pcard-list">{rows}</div>
    <a class="more-a" href="/materials/">All {len(cat["items"])} materials {icon("arrow")}</a>
  </div>
  <div class="bx s5">
    <div class="stats">
      <div>
        <h2>This week's prices</h2>
        <div class="keys">
          <span class="key"><span><i style="background:var(--teal)"></i>Today</span><b>Updated {fdate(cat["updated"])}</b></span>
          <span class="key"><span><i style="background:var(--mint)"></i>Market range</span><b>Low to high</b></span>
        </div>
      </div>
      <div class="bars" role="img" aria-label="Today's price against this week's market range for key materials">{bars}</div>
    </div>
  </div>
  <a class="bx bx-teal s4" href="/stockpile/#lock">
    <div class="bx-head"><span class="mask">**** PRICE LOCK</span>{coin("mint")}</div>
    <div class="big-num" style="font-size:2rem">{naira(lockv * lockd)} <span style="opacity:.55">/ {naira(lockv)}</span></div>
    <span class="lbl">Activation deposit on a ₦12m lock</span>
    <div class="prog"><i style="width:{lockd * 100:.0f}%"></i></div>
    <span class="small">{lockd * 100:.0f}% secures today's price for up to 12 months</span>
    <span class="go-sq">{icon("arrow-ur")}</span>
  </a>
  <a class="bx s3" href="/stockpile/">
    <span class="small muted">Stockpile offer</span>
    <div class="big-num" style="font-size:1.9rem;color:var(--teal)" >{naira(tm * (1 - trailer["discount"]))}</div>
    <b style="font-weight:600">{e(trailer["name"])}</b>
    <p class="small muted" style="margin:2px 0 46px">Save {trailer["discount"] * 100:.0f}% · held {CFG["bundles"]["holdMonths"]} months</p>
    <span class="go-sq">{icon("arrow-ur")}</span>
  </a>
</section>
<section class="wrap block">
  <h2 class="sec-title">What do you want to do?</h2>
  <div class="jgrid">{cards}</div>
</section>
<section class="wrap block">
  <h2 class="sec-title">How every deal works</h2>
  <ol class="steps-list">
    <li><span class="step-n">[01]</span><b>Choose online</b>Add materials to your cart, pick a stockpile offer, list what you sell, or send a sourcing request.</li>
    <li><span class="step-n">[02]</span><b>Finish on WhatsApp</b>Your request opens in a chat with Buildocrat, already filled in with a reference number.</li>
    <li><span class="step-n">[03]</span><b>Confirm and pay</b>We confirm stock, delivery and dates in writing, then invoice from {e(CFG["legalName"])}.</li>
    <li><span class="step-n">[04]</span><b>Delivered or held</b>We deliver to site, or hold your stockpile and deliver whenever you call it off.</li>
  </ol>
</section>
<section class="wrap block">
  <h2 class="sec-title">Shop by material</h2>
  <div class="gchips">{groups}</div>
  <p class="more-link"><a href="/materials/">Infrastructure, power, water and oil &amp; gas materials {icon("arrow")}</a></p>
</section>
<section class="wrap">
  <div class="lockband">
    <div>
      <p class="eyebrow">Price Lock</p>
      <h2>Building over 6–12 months? Freeze today's cement, iron rod, block and roofing prices.</h2>
      <p>Pay an activation deposit, draw your materials month by month at the locked price, with no fees. If prices rise, the rise is ours, not yours.</p>
    </div>
    <div class="tiles" style="grid-template-columns:1fr">
      <a class="tile tile-mint" href="/stockpile/#lock"><span class="tl">Work out my lock</span><span class="tile-ic">{icon("lock")}</span></a>
      <a class="tile tile-white" href="https://wa.me/{CFG["whatsapp"]}?text={urllib.parse.quote("Hello Buildocrat, I'd like to talk about Price Lock.")}" rel="noopener"><span class="tl">Ask on WhatsApp</span><span class="tile-ic">{icon("chat")}</span></a>
    </div>
  </div>
</section>
"""
    org_cfg = SCFG.get("organization") or {}
    web_cfg = SCFG.get("website") or {}
    site_url = (org_cfg.get("url") or SITE).rstrip("/") + "/"
    same_as = org_cfg.get("sameAs")
    if same_as is None:
        same_as = [CFG["rateBookUrl"], CFG["landValueUrl"]]
    same_as = [u for u in same_as if u]
    org = {
        "@context": "https://schema.org", "@type": "Organization",
        "name": org_cfg.get("name") or "Buildocrat",
        "legalName": org_cfg.get("legalName") or CFG["legalName"],
        "url": site_url,
        "logo": org_cfg.get("logo") or (SITE.rstrip("/") + "/icons/icon-512.png"),
        "email": org_cfg.get("email") or CFG["email"],
        "telephone": "+" + CFG["whatsapp"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": org_cfg.get("streetAddress") or "No. 30 Anthony Enahoro Street",
            "addressLocality": org_cfg.get("addressLocality") or "Utako District, Abuja",
            "addressRegion": org_cfg.get("addressRegion") or "FCT",
            "addressCountry": org_cfg.get("addressCountry") or "NG",
        },
        "founder": {"@type": "Person", "name": org_cfg.get("founder") or "Engr. Akolade Maruf Ibrahim"},
        "identifier": {"@type": "PropertyValue", "propertyID": "CAC RC", "value": CFG["rc"]},
    }
    if same_as:
        org["sameAs"] = same_as
    website = {
        "@context": "https://schema.org", "@type": "WebSite",
        "name": web_cfg.get("name") or "Buildocrat",
        "alternateName": web_cfg.get("alternateName") or "Buildocrat Store",
        "url": (web_cfg.get("url") or site_url).rstrip("/") + "/",
        "potentialAction": {"@type": "SearchAction", "target": SITE + "/buy/?q={search_term_string}",
                            "query-input": "required name=search_term_string"},
    }
    ld = [org, website]
    return layout("/", "Buildocrat — buy, stockpile, sell & source building materials in Nigeria",
                  "Buy cement, iron rods, blocks, sand and roofing at checked prices for your state, lock prices for your build, sell or source materials, all finished on WhatsApp.",
                  body, "home", ver, ld)


def short_name(i):
    names = {"M-CEM-07": "Dangote cement 50kg", "M-CEM-08": "BUA cement 50kg", "M-STL-01": "Iron rod 12–16mm",
             "M-BLK-01": '9" hollow block', "M-AGG-01": "Sharp sand 20t", "M-RF-01": "Longspan 0.55mm",
             "M-AGG-07": 'Granite 3/4" 30t', "M-STL-12": "12mm rod, 12m"}
    return names.get(i["c"], i["d"])


def page_buy(cat, ver):
    body = f"""
<section class="wrap page-head">
  <h1>Buy building materials</h1>
  <p class="lede">Prices are for <b data-state-label>FCT (Abuja)</b> <button class="chg" type="button" data-state-btn>Change</button>, before delivery. Add items to your cart, then send the order to WhatsApp. Nothing is charged here.</p>
</section>
<section class="wrap shop" data-shop>
  <div class="shop-tools">
    <label class="search">{icon("search")}<input type="search" placeholder="Search cement, 12mm rod, longspan, tiles…" data-q aria-label="Search materials"></label>
    <div class="seg" role="tablist" data-sec>
      <button type="button" role="tab" aria-selected="true" data-secval="building">Building</button>
      <button type="button" role="tab" aria-selected="false" data-secval="infrastructure">Infrastructure</button>
      <button type="button" role="tab" aria-selected="false" data-secval="all">All</button>
    </div>
    <div class="chips" data-chips></div>
  </div>
  <p class="small muted" data-count>Loading prices…</p>
  <ul class="plist" data-list></ul>
  <button class="btn btn-ghost more" type="button" data-more hidden>Show more</button>
</section>
<section class="wrap cart-wrap" id="cart" data-cart>
  <h2 class="sec-title">{icon("cart")} Your cart</h2>
  <div data-cart-body><p class="muted">Your cart is empty. Add materials above.</p></div>
</section>
<noscript><p class="wrap">Browse <a href="/materials/">all materials and prices</a>, then message us on WhatsApp {e(CFG["whatsappDisplay"])}.</p></noscript>
"""
    return layout("/buy/", "Buy building materials online in Nigeria — Buildocrat",
                  "Order cement, iron rods, blocks, sand, granite, roofing, tiles, paint and plumbing at checked prices for your state. Finish your order on WhatsApp.",
                  body, "buy", ver, crumbs=[("Home", "/"), ("Buy", "/buy/")])


def page_stockpile(cat, ver):
    body = f"""
<section class="wrap page-head">
  <h1>Stockpile building materials</h1>
  <p class="lede">Buy ahead of price rises. Take a <b>special bundle offer</b>, or use <b>Price Lock</b> to fix today's price on your own list and draw it down month by month. We hold your stock and deliver when you call it off.</p>
  <div class="seg seg-lg" role="tablist" data-stab>
    <button type="button" role="tab" aria-selected="true" data-tab="offers">{icon("stack")} Special offers</button>
    <button type="button" role="tab" aria-selected="false" data-tab="lock">{icon("lock")} Price Lock</button>
  </div>
</section>
<section class="wrap" data-panel="offers">
  <div class="bgrid" data-bundles><p class="muted">Loading offers…</p></div>
</section>
<section class="wrap" id="lock" data-panel="lock" hidden>
  <div class="lock-grid">
    <form class="card form" data-lockform>
      <h2>Lock my prices</h2>
      <label>I am a<select name="seg" data-lseg></select></label>
      <label>Lock for<select name="tenor" data-ltenor></select></label>
      <fieldset>
        <legend>Materials to lock</legend>
        <div data-llines></div>
        <button type="button" class="btn btn-ghost btn-sm" data-ladd>+ Add a material</button>
      </fieldset>
      <label>First delivery wanted<input type="month" name="start" data-lstart></label>
      <label class="inline">Prices rise about <input type="number" name="infl" min="0" max="200" step="1" data-linfl> % a year (your assumption)</label>
    </form>
    <div class="card lock-out" data-lockout></div>
  </div>
  <div class="card note">
    <h3>How Price Lock works</h3>
    <ul>
      <li><b>Zero fees.</b> Your locked price is today's price plus a fixed spread for the lock period. That spread is all we earn.</li>
      <li><b>Activation deposit</b> secures the lock. The rest is paid as you draw materials, at the locked price.</li>
      <li><b>Draw down monthly</b> or on call-off. Prices are fixed in writing for every line in your lock.</li>
      <li>Available on cement, iron rods, blocks, sand and granite, and roofing.</li>
    </ul>
  </div>
</section>
"""
    return layout("/stockpile/", "Stockpile building materials & Price Lock — Buildocrat",
                  "Special bundle offers on cement, iron rods, blocks and roofing with pay-in-full discounts or 3–6 month plans, plus Price Lock to freeze today's material prices.",
                  body, "stockpile", ver, crumbs=[("Home", "/"), ("Stockpile", "/stockpile/")])


def page_sell(cat, ver):
    body = f"""
<section class="wrap page-head">
  <h1>Sell building materials through Buildocrat</h1>
  <p class="lede">Manufacturers, distributors, importers, quarries, block plants, timber yards and anyone with surplus stock: list what you sell. We bring prepaid orders, bulk developer demand and Price Lock forward orders.</p>
</section>
<section class="wrap two-col">
  <form class="card form" data-sellform>
    <h2>Your business</h2>
    <fieldset class="radios" data-sellertype>
      <legend>I am a</legend>
      <label><input type="radio" name="type" value="Manufacturer" checked> Manufacturer</label>
      <label><input type="radio" name="type" value="Distributor / dealer"> Distributor / dealer</label>
      <label><input type="radio" name="type" value="Importer"> Importer</label>
      <label><input type="radio" name="type" value="Quarry / block plant / timber yard"> Quarry, block plant or timber yard</label>
      <label><input type="radio" name="type" value="Individual with surplus materials"> Individual with surplus materials</label>
    </fieldset>
    <label>Business or your name<input name="biz" required autocomplete="organization"></label>
    <label>Contact person<input name="name" required autocomplete="name"></label>
    <label>Phone / WhatsApp<input name="phone" type="tel" required autocomplete="tel" placeholder="080…"></label>
    <div class="row2">
      <label>State<select name="state" data-states></select></label>
      <label>Town / area<input name="town" required></label>
    </div>
    <label>CAC RC / BN number <span class="opt">(optional)</span><input name="rc"></label>
    <div class="row2">
      <label>Can you deliver?<select name="delivery"><option>Yes, own trucks</option><option>Yes, hired trucks</option><option>Pickup only</option></select></label>
      <label>Credit you can give<select name="credit"><option>Cash before delivery</option><option>Cash on delivery</option><option>7-day credit</option><option>30-day credit</option></select></label>
    </div>
    <h2>What you sell</h2>
    <p class="small muted">Start typing to match our catalogue. Send photos, price lists or certificates in the WhatsApp chat.</p>
    <div data-sell-lines></div>
    <button type="button" class="btn btn-ghost btn-sm" data-sell-add>+ Add another product</button>
    <label>Anything else <span class="opt">(optional)</span><textarea name="notes" rows="3" placeholder="Brands, factory location, monthly capacity, warehouse…"></textarea></label>
    <button class="btn btn-wa" type="submit">{WA_SVG} Send my listing on WhatsApp</button>
  </form>
  <aside class="card side">
    <h3>Why sell with us</h3>
    <ul class="ticks">
      <li>{icon("check")} <span><b>Prepaid orders.</b> Buyers pay Buildocrat before we release your order.</span></li>
      <li>{icon("check")} <span><b>Bulk demand.</b> Developers, contractors and diaspora clients across all states.</span></li>
      <li>{icon("check")} <span><b>Forward orders.</b> Price Lock clients commit to months of drawdowns, so you can plan production.</span></li>
      <li>{icon("check")} <span><b>Free listing.</b> We agree a supply price with you; no listing fee.</span></li>
    </ul>
    <p class="small muted">Every supplier is checked (CAC, site visit or references) before their stock is offered to buyers.</p>
  </aside>
</section>
<datalist id="catalog-names"></datalist>
"""
    return layout("/sell/", "Sell building materials in Nigeria — become a Buildocrat supplier",
                  "Manufacturers, dealers, quarries, block plants and individuals with surplus building materials: list your products with Buildocrat and get prepaid bulk orders.",
                  body, "sell", ver, crumbs=[("Home", "/"), ("Sell", "/sell/")])


def page_source(cat, ver):
    body = f"""
<section class="wrap page-head">
  <h1>Source building materials</h1>
  <p class="lede">Can't find it, need a large quantity, a specific brand, or imported items? Send your list or BoQ. We search our suppliers and manufacturers, compare them and quote you on WhatsApp, usually within one working day.</p>
</section>
<section class="wrap two-col">
  <form class="card form" data-sourceform>
    <h2>Your project</h2>
    <div class="row2">
      <label>Your name<input name="name" required autocomplete="name"></label>
      <label>Phone / WhatsApp<input name="phone" type="tel" required autocomplete="tel"></label>
    </div>
    <div class="row2">
      <label>I am a<select name="who"><option>Homeowner / individual</option><option>Contractor</option><option>Developer</option><option>Diaspora client</option><option>Government / institution</option><option>Consultant / QS</option></select></label>
      <label>Project type<select name="ptype"><option>House / residential</option><option>Estate / multiple units</option><option>Commercial building</option><option>Road / civil works</option><option>Industrial / factory</option><option>Water / power / oil &amp; gas</option><option>Renovation</option></select></label>
    </div>
    <div class="row2">
      <label>Delivery state<select name="state" data-states></select></label>
      <label>Town / site area<input name="town" required></label>
    </div>
    <div class="row2">
      <label>Needed by<input type="date" name="date"></label>
      <label>Budget <span class="opt">(optional, ₦)</span><input name="budget" inputmode="numeric" data-money></label>
    </div>
    <h2>Materials needed</h2>
    <p class="small muted">Type a material, size or brand. Have a BoQ? Add the main lines here and attach the full BoQ in the WhatsApp chat.</p>
    <div data-src-lines></div>
    <button type="button" class="btn btn-ghost btn-sm" data-src-add>+ Add another line</button>
    <fieldset class="checks">
      <legend>Also needed</legend>
      <label><input type="checkbox" name="req" value="Test certificates / mill certs"> Test certificates</label>
      <label><input type="checkbox" name="req" value="Specific brand only"> Specific brand only</label>
      <label><input type="checkbox" name="req" value="Imported items (FX quote)"> Imported items</label>
      <label><input type="checkbox" name="req" value="Staged deliveries"> Staged deliveries</label>
      <label><input type="checkbox" name="req" value="Quality inspection on delivery"> Quality inspection</label>
      <label><input type="checkbox" name="req" value="BoQ check by our engineers"> BoQ / quantity check</label>
    </fieldset>
    <label>Notes <span class="opt">(optional)</span><textarea name="notes" rows="3"></textarea></label>
    <button class="btn btn-wa" type="submit">{WA_SVG} Send sourcing request on WhatsApp</button>
  </form>
  <aside class="card side">
    <h3>What we source</h3>
    <ul class="ticks">
      <li>{icon("check")} <span>Bulk cement and iron rods direct from manufacturers and major distributors</span></li>
      <li>{icon("check")} <span>Hard-to-find sizes, brands and specifications</span></li>
      <li>{icon("check")} <span>Imported finishes, fittings and equipment, quoted at today's exchange rate</span></li>
      <li>{icon("check")} <span>Full BoQ packages for estates, roads and commercial buildings</span></li>
    </ul>
    <p class="small muted">We quote landed at your site. You confirm in the chat before anything is ordered.</p>
  </aside>
</section>
<datalist id="catalog-names"></datalist>
"""
    return layout("/source/", "Source building materials in Nigeria — send your list or BoQ | Buildocrat",
                  "Send Buildocrat your materials list or BoQ. We find suppliers, compare prices, source imported or hard-to-find items and quote delivered to site on WhatsApp.",
                  body, "source", ver, crumbs=[("Home", "/"), ("Source", "/source/")])


def page_risk(cat, ver):
    body = f"""
<section class="wrap page-head">
  <h1>Control construction project risk</h1>
  <p class="lede">Material prices, scarcity, fake products, theft on site and unpaid deliveries are what push Nigerian builds over budget. Check your exposure in a minute, then tell us which risks to take off your hands.</p>
</section>
<section class="wrap lock-grid">
  <form class="card form" data-riskform>
    <h2>Project risk check</h2>
    <div class="row2">
      <label>Project<select name="ptype"><option>House / residential</option><option>Estate / multiple units</option><option>Commercial building</option><option>Road / civil works</option><option>Industrial</option></select></label>
      <label>State<select name="state" data-states></select></label>
    </div>
    <label>Total construction budget (₦)<input name="budget" inputmode="numeric" data-money value="60,000,000"></label>
    <label class="inline">Materials are <input type="number" name="share" min="10" max="90" step="1" value="55"> % of the budget</label>
    <div class="row2">
      <label>Building starts in<select name="start"><option value="0">Now</option><option value="1">1 month</option><option value="3">3 months</option><option value="6">6 months</option><option value="12">12 months</option></select></label>
      <label>Build takes<select name="dur"><option value="3">3 months</option><option value="6">6 months</option><option value="9">9 months</option><option value="12" selected>12 months</option><option value="18">18 months</option><option value="24">24 months</option></select></label>
    </div>
    <div class="row2">
      <label class="inline">Likely price rise <input type="number" name="ib" min="0" max="200" step="1"> % a year</label>
      <label class="inline">Bad year <input type="number" name="ih" min="0" max="300" step="1"> % a year</label>
    </div>
    <fieldset class="checks">
      <legend>Which risks worry you?</legend>
      <label><input type="checkbox" name="risk" value="price" checked> Prices rising mid-build</label>
      <label><input type="checkbox" name="risk" value="scarcity"> Scarcity / stock-outs</label>
      <label><input type="checkbox" name="risk" value="quality"> Fake or sub-standard materials</label>
      <label><input type="checkbox" name="risk" value="theft"> Theft &amp; wastage on site</label>
      <label><input type="checkbox" name="risk" value="quantity"> Inflated quantities / overbilling</label>
      <label><input type="checkbox" name="risk" value="supplier"> Paying a supplier who doesn't deliver</label>
      <label><input type="checkbox" name="risk" value="fx"> Exchange rate on imported items</label>
      <label><input type="checkbox" name="risk" value="diaspora"> Managing the build from abroad</label>
    </fieldset>
    <div class="row2">
      <label>Your name<input name="name" autocomplete="name"></label>
      <label>Phone / WhatsApp<input name="phone" type="tel" autocomplete="tel"></label>
    </div>
    <button class="btn btn-wa" type="submit">{WA_SVG} Get my risk plan on WhatsApp</button>
  </form>
  <div class="card lock-out" data-riskout></div>
</section>
<section class="wrap block">
  <h2 class="sec-title">How Buildocrat takes the risk off your project</h2>
  <div class="rgrid">
    <div class="rcard">{icon("lock")}<h3>Price risk</h3><p>Price Lock fixes cement, iron rod, block, sand and roofing prices for up to 12 months.</p></div>
    <div class="rcard">{icon("stack")}<h3>Scarcity</h3><p>Stockpile bundles held for you and called off when site is ready.</p></div>
    <div class="rcard">{icon("shield")}<h3>Quality</h3><p>Checked suppliers, manufacturer-direct cement and steel, test certificates on request.</p></div>
    <div class="rcard">{icon("truck")}<h3>Theft &amp; wastage</h3><p>Staged deliveries matched to your programme, so less sits on site.</p></div>
    <div class="rcard">{icon("list")}<h3>Quantities</h3><p>Engineer-checked BoQ quantities against the <a href="{CFG["rateBookUrl"]}">Rate Book</a> before you buy.</p></div>
    <div class="rcard">{icon("clock")}<h3>Supplier default</h3><p>You pay Buildocrat; suppliers are paid on confirmed delivery.</p></div>
  </div>
</section>
"""
    return layout("/risk-control/", "Construction project risk control in Nigeria — Buildocrat",
                  "Check how much rising cement, iron rod and block prices could add to your build, and cover price, scarcity, quality, theft and supplier risk with Buildocrat.",
                  body, "risk", ver, crumbs=[("Home", "/"), ("Risk control", "/risk-control/")])


def page_requests(ver):
    body = f"""
<section class="wrap page-head">
  <h1>My requests</h1>
  <p class="lede">Orders, offers, listings and requests you've sent from this device. Tap one to open it in WhatsApp again.</p>
</section>
<section class="wrap"><div data-requests><p class="muted">Nothing sent from this device yet.</p></div></section>
"""
    return layout("/requests/", "My requests — Buildocrat", "Your Buildocrat orders and requests on this device.", body,
                  "requests", ver, noindex=True)


FAQ = [
    ("How do I pay?", "After you send your order, a Buildocrat person confirms stock, delivery cost and dates in the WhatsApp chat and sends an invoice. You pay by bank transfer into a Buildocrat Property Technologies Ltd company account (CAC RC 7019619) named on the invoice. We never ask you to pay into a personal account."),
    ("Are the prices on the site final?", "They are our current selling prices for your state, built from the weekly Nigeria Construction Rate Book plus our margin. Delivery is added per order, and we confirm the final price in writing before you pay. Prices can move during the week; the invoice price is the one you pay."),
    ("How do I change my location?", "Tap the “Deliver to” button at the top of every page (it shows a map pin and your state), or any “Change” link next to a price. Pick your state from the list, type to search, or tap “Use my location”. Every price, bundle and Price Lock on the site updates at once, and your choice is remembered on this device."),
    ("Do you deliver outside Abuja?", "Yes, to all 36 states and the FCT. Prices on the site adjust to your state; delivery is quoted separately because it depends on distance, access and load size."),
    ("What is Price Lock?", "Price Lock fixes today's price on cement, iron rods, blocks, sand, granite and roofing for 3 to 12 months. You pay an activation deposit, then pay for each draw-down at the locked price. There are no fees: the locked price includes a fixed spread, which is all we earn."),
    ("What is a stockpile offer?", "A ready-made bundle (for example a foundation pack or a trailer of cement) at a discount if you pay in full, or on a 3 or 6-month plan at a fixed price. We hold the materials and deliver whenever you call them off within the hold period."),
    ("How do I sell materials through Buildocrat?", "Fill in the Sell form with your business and products. It opens in WhatsApp; send photos, price lists or certificates in the chat. We check every supplier before offering their stock to buyers."),
    ("Can you source items you don't list?", "Yes. Use the Source form or send your BoQ in WhatsApp. We find suppliers, compare them and quote delivered to your site."),
    ("Who is behind Buildocrat?", f"{CFG['legalName']} (CAC RC {CFG['rc']}), Abuja, which also publishes the free Nigeria Construction Rate Book and Nigeria Land Value Book."),
]


def page_help(ver):
    qa = "".join(f"<details class='qa'><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in FAQ)
    body = f"""
<section class="wrap page-head">
  <h1>How Buildocrat works</h1>
  <p class="lede">Every purchase, offer, listing and request on this site ends in a WhatsApp chat with Buildocrat on {e(CFG["whatsappDisplay"])}. Nothing is charged on the website.</p>
</section>
<section class="wrap block">
  <div class="card note pay-safe">
    <h2>{icon("shield")} Paying safely</h2>
    <ul>
      <li>We only chat from <b>{e(CFG["whatsappDisplay"])}</b>.</li>
      <li>We only take payment into a <b>{e(CFG["legalName"])}</b> (RC {CFG["rc"]}) company account named on your invoice.</li>
      <li>Every request has a reference like <b>BDC-B-261018-K7Q2</b>. Quote it when you pay.</li>
      <li>If anyone asks you to pay into a personal account in our name, stop and call us.</li>
    </ul>
  </div>
</section>
<section class="wrap block">
  <div class="card">
    <h2>Company details</h2>
    <table class="co-table"><tbody>
      <tr><td>Registered name</td><td>{e(CFG["legalName"])}</td></tr>
      <tr><td>CAC RC number</td><td>{CFG["rc"]}</td></tr>
      <tr><td>Office</td><td>{e(CFG["address"])}, FCT, Nigeria</td></tr>
      <tr><td>WhatsApp</td><td><a href="https://wa.me/{CFG["whatsapp"]}" rel="noopener">{e(CFG["whatsappDisplay"])}</a></td></tr>
      <tr><td>Email</td><td><a href="mailto:{CFG["email"]}">{e(CFG["email"])}</a></td></tr>
    </tbody></table>
  </div>
</section>
<section class="wrap block">
  <h2 class="sec-title">Questions</h2>
  {qa}
</section>
"""
    ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]}
    return layout("/help/", "How Buildocrat works — payment, delivery, Price Lock FAQ",
                  "How ordering, paying, delivery, stockpile offers, Price Lock and selling work on Buildocrat, with safe-payment rules.",
                  body, "help", ver, ld, crumbs=[("Home", "/"), ("Help", "/help/")])


def page_materials_index(cat, ver):
    def sec(name, key):
        return (f"<h2 class='sec-title'>{name}</h2><div class='gcards'>" + "".join(
            f'<a class="gcard" href="/materials/{g["s"]}/"><span class="mi">{icon(GROUP_ICON.get(g["s"], "box"))}</span><b>{e(g["n"])}</b><span>{g["count"]} lines</span></a>'
            for g in cat["groups"] if g["sec"] == key) + "</div>")
    body = f"""
<section class="wrap page-head">
  <h1>Building material prices in Nigeria</h1>
  <p class="lede">{len(cat["items"])} materials with Buildocrat selling prices, updated {fdate(cat["updated"])}. Prices show for <b data-state-label>FCT (Abuja)</b> <button class="chg" type="button" data-state-btn>Change</button>.</p>
</section>
<section class="wrap block">{sec("Building materials", "building")}{sec("Infrastructure &amp; industrial", "infrastructure")}</section>
<section class="wrap block" id="open-data">
  <div class="card note">
    <h2>Open price data</h2>
    <p>Download every Buildocrat selling price (Abuja base, before delivery), free to use with credit to Buildocrat. Updated weekly from the <a href="{CFG["rateBookUrl"]}">Nigeria Construction Rate Book</a>.</p>
    <div class="dl"><a class="btn btn-ghost btn-sm" href="/data/prices.csv" download>{icon("download")} prices.csv</a><a class="btn btn-ghost btn-sm" href="/data/prices.json" download>{icon("download")} prices.json</a><a class="btn btn-ghost btn-sm" href="/feed.xml">RSS: weekly price changes</a></div>
  </div>
</section>
"""
    ds = {"@context": "https://schema.org", "@type": "Dataset", "name": "Buildocrat building material prices, Nigeria",
          "description": f"{len(cat['items'])} building and infrastructure material selling prices in Nigerian naira, Abuja base with state factors, updated weekly.",
          "url": SITE + "/materials/", "dateModified": cat["updated"], "license": "https://creativecommons.org/licenses/by/4.0/",
          "creator": {"@type": "Organization", "name": "Buildocrat", "url": SITE}, "spatialCoverage": "Nigeria", "inLanguage": "en-NG",
          "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": SITE + "/data/prices.csv"},
                           {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": SITE + "/data/prices.json"}]}
    return layout("/materials/", f"Building material prices in Nigeria ({fdate(cat['updated'])}) — Buildocrat",
                  "Current prices of cement, iron rods, blocks, sand, granite, roofing, timber, tiles, paint, plumbing and electrical materials in Nigeria, by state.",
                  body, "materials", ver, ds, crumbs=[("Home", "/"), ("Materials", "/materials/")])


def page_group(cat, g, items, ver):
    intro = GROUP_INTRO.get(g["s"], f'{g["n"]} supplied to sites across Nigeria.')
    rows = "".join(item_row(i) for i in items)
    body = f"""
<section class="wrap page-head">
  <h1>{e(g["n"])} prices in Nigeria</h1>
  <p class="lede">{e(intro)} Prices for <b data-state-label>FCT (Abuja)</b> <button class="chg" type="button" data-state-btn>Change</button>, updated {fdate(cat["updated"])}, before delivery.</p>
  <p><a class="btn btn-primary btn-sm" href="/buy/?g={g["s"]}">{icon("cart")} Shop {e(g["n"].lower())}</a></p>
</section>
<section class="wrap"><ul class="plist static">{rows}</ul></section>
"""
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": g["n"] + " prices in Nigeria",
          "itemListElement": [{"@type": "ListItem", "position": n + 1, "url": SITE + i["s"], "name": i["d"]}
                              for n, i in enumerate(items[:100])]}
    return layout(f"/materials/{g['s']}/", f"{g['n']} prices in Nigeria ({fdate(cat['updated'])}) — Buildocrat",
                  f"{intro} Current Buildocrat prices by state, order on WhatsApp.", body, "materials", ver, ld,
                  crumbs=[("Home", "/"), ("Materials", "/materials/"), (g["n"], f"/materials/{g['s']}/")])


def page_item(cat, i, g, related, ver, loc_rows):
    upd = cat["updated"]
    valid = (dt.date.fromisoformat(upd) + dt.timedelta(days=14)).isoformat()
    lock_btn = (f'<a class="btn btn-ghost" href="/stockpile/?lock={i["c"]}#lock">{icon("lock")} Lock this price</a>'
                if i["lk"] else "")
    rng = f'{naira(i["lo"])} – {naira(i["hi"])}' if i["lo"] != i["hi"] else naira(i["p"])
    rel = "".join(item_row(r) for r in related)
    sf = '<p class="small badge">Supplied and fixed by our installer partners</p>' if i["sf"] else ""
    body = f"""
<section class="wrap item">
  <div class="item-main">
    <p class="eyebrow">{e(g["n"])}</p>
    <h1>{e(i["d"])}</h1>
    {sf}
    <div class="price-box">
      <div><span class="small muted">Buildocrat price · <b data-state-label>FCT (Abuja)</b> <button class="chg" type="button" data-state-btn>Change</button></span>
      <div class="big-price"><span data-price="{i["c"]}">{naira(i["p"])}</span> <small>per {e(unit_word(i["u"]))}</small></div>
      <span class="small muted">Market range {rng} · checked {fdate(i["set"] or upd)} · delivery quoted separately</span></div>
    </div>
    <div class="buy-row" data-buy="{i["c"]}">
      <div class="qty"><button type="button" data-dec aria-label="Less">−</button><input type="number" min="0" step="any" value="1" inputmode="decimal" aria-label="Quantity"><button type="button" data-inc aria-label="More">+</button></div>
      <button class="btn btn-primary" type="button" data-add>{icon("cart")} Add to cart</button>
      <button class="btn btn-wa" type="button" data-now>{WA_SVG} Order now</button>
    </div>
    <div class="cta-row">{lock_btn}<a class="btn btn-ghost" href="/source/?item={i["c"]}">{icon("search")} Need a large quantity?</a></div>
    {f'<p class="small muted">{e(i["note"])}</p>' if i["note"] else ''}
  </div>
  <aside class="card side">
    <h2 class="h3">Price by city</h2>
    <table class="loc"><tbody>{loc_rows}</tbody></table>
    <p class="small muted">Before delivery. Other states use their nearest city. <button class="chg" type="button" data-state-btn>Set my state</button></p>
  </aside>
</section>
<section class="wrap block"><h2 class="sec-title">Related {e(g["n"].lower())}</h2><ul class="plist static">{rel}</ul></section>
"""
    ld = {"@context": "https://schema.org", "@type": "Product", "name": i["d"], "sku": i["c"], "category": g["n"],
          "brand": {"@type": "Brand", "name": "Buildocrat"} if False else None,
          "offers": {"@type": "Offer", "priceCurrency": "NGN", "price": i["p"], "priceValidUntil": valid,
                     "availability": "https://schema.org/InStock", "url": SITE + i["s"],
                     "areaServed": "NG", "seller": {"@type": "Organization", "name": "Buildocrat"}}}
    ld = {k: v for k, v in ld.items() if v is not None}
    title = f"{i['d']} price in Nigeria — {naira(i['p'])} per {unit_word(i['u'])} | Buildocrat"
    desc = (f"{i['d']}: {naira(i['p'])} per {unit_word(i['u'])} in Abuja ({fdate(upd)}). See prices in Lagos, Port Harcourt, "
            f"Kano and more. Order on WhatsApp with delivery to your site.")
    return layout(i["s"], title, desc, body, "item", ver, ld,
                  crumbs=[("Home", "/"), ("Materials", "/materials/"), (g["n"], f"/materials/{g['s']}/"), (i["d"][:60], i["s"])])


def page_404(ver):
    body = f"""<section class="wrap page-head"><h1>Page not found</h1><p class="lede">That page isn't here. Try <a href="/buy/">shopping materials</a> or <a href="/">the home page</a>, or ask us on WhatsApp.</p></section>"""
    return layout("/404.html", "Page not found — Buildocrat", "Page not found.", body, "404", ver, noindex=True)


# ----------------------------------------------------------- site files ---
def make_icons():
    out = os.path.join(DOCS, "icons")
    if os.path.exists(os.path.join(out, "icon-512.png")) and os.path.exists(os.path.join(DOCS, "og.png")):
        return
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(out, exist_ok=True)
    TEAL, MINT, SAGE, INK = "#165E57", "#C7E8A4", "#D5DFDB", "#16211E"

    def font(size, weight="SemiBold"):
        for p in [f"/usr/share/fonts/opentype/inter/InterDisplay-{weight}.otf", f"/usr/share/fonts/opentype/inter/Inter-{weight}.otf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
        return ImageFont.load_default()

    def circles(dr, cx, cy, r):
        dr.ellipse([cx - r * 1.55, cy - r, cx + r * 0.45, cy + r], fill=MINT)
        ov = Image.new("RGBA", (int(r * 4), int(r * 2)), (0, 0, 0, 0))
        return ov

    def mark(size, pad, bg=TEAL):
        S = size * 4
        im = Image.new("RGBA", (S, S), bg)
        dr = ImageDraw.Draw(im)
        r = S * (0.25 - pad * 0.5)
        cy = S / 2
        dr.ellipse([S / 2 - r * 1.62, cy - r, S / 2 + r * 0.38, cy + r], fill=MINT)
        lay = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(lay).ellipse([S / 2 - r * 0.38, cy - r, S / 2 + r * 1.62, cy + r], fill=(255, 255, 255, 200))
        im = Image.alpha_composite(im, lay)
        return im.resize((size, size), Image.LANCZOS).convert("RGB")
    mark(512, 0.04).save(os.path.join(out, "icon-512.png"))
    mark(192, 0.04).save(os.path.join(out, "icon-192.png"))
    mark(180, 0.04).save(os.path.join(out, "apple-touch-icon.png"))
    mark(512, 0.14).save(os.path.join(out, "maskable-512.png"))

    W, H = 1200, 630
    og = Image.new("RGB", (W, H), SAGE)
    dr = ImageDraw.Draw(og)
    dr.rounded_rectangle([50, 50, 720, 580], radius=40, fill="#FFFFFF")
    og.paste(mark(84, 0.04), (90, 90))
    dr.text((196, 132), "Buildocrat", font=font(54, "Bold"), fill=INK, anchor="lm")
    dr.text((90, 250), "Buy, stockpile, sell and", font=font(52), fill=INK, anchor="lm")
    dr.text((90, 316), "source building materials.", font=font(52), fill=INK, anchor="lm")
    dr.text((90, 382), "Lock the price.", font=font(52), fill=TEAL, anchor="lm")
    dr.rounded_rectangle([90, 450, 380, 530], radius=22, fill=MINT)
    dr.text((235, 490), "[SHOP MATERIALS]", font=font(24, "Medium"), fill="#203A12", anchor="mm")
    dr.rounded_rectangle([395, 450, 680, 530], radius=22, fill=TEAL)
    dr.text((537, 490), "[LOCK A PRICE]", font=font(24, "Medium"), fill="#E6F3EF", anchor="mm")
    dr.rounded_rectangle([750, 50, 1150, 330], radius=40, fill=MINT)
    dr.text((790, 105), "**** RC 7019619", font=font(24, "Medium"), fill="#203A12", anchor="lm")
    dr.text((790, 190), "Cement, 50kg", font=font(30, "Medium"), fill="#3D5A2C", anchor="lm")
    dr.text((790, 260), "Weekly prices", font=font(56, "SemiBold"), fill="#203A12", anchor="lm")
    dr.rounded_rectangle([750, 350, 1150, 580], radius=40, fill=TEAL)
    for k, (h, n) in enumerate([(0.55, 0.35), (0.8, 0.6), (0.7, 0.4), (0.9, 0.75), (0.6, 0.3), (0.85, 0.5), (0.75, 0.55)]):
        x = 800 + k * 48
        dr.rounded_rectangle([x, 395, x + 14, 540], radius=7, fill="#22766C")
        dr.rounded_rectangle([x, 540 - 145 * h, x + 14, 540], radius=7, fill=MINT)
        dr.rounded_rectangle([x, 540 - 145 * n, x + 14, 540], radius=7, fill="#E6F3EF")
    og.save(os.path.join(DOCS, "og.png"))


def asset_hash():
    h = hashlib.sha1()
    for f in ("app.css", "app.js", "pwa.js"):
        h.update(open(os.path.join(DOCS, "assets", f), "rb").read())
    return h.hexdigest()[:10]


AI_BOTS = ['GPTBot', 'OAI-SearchBot', 'ChatGPT-User', 'ClaudeBot', 'Claude-User', 'Claude-SearchBot', 'anthropic-ai', 'PerplexityBot', 'Perplexity-User', 'Google-Extended', 'Googlebot', 'Bingbot', 'Applebot', 'Applebot-Extended', 'CCBot', 'meta-externalagent', 'DuckAssistBot', 'YouBot', 'cohere-ai', 'Amazonbot']


def write_extras(cat, d, ver):
    """robots, open data, feed, llms-full and the offline page — the standard kit on every Buildocrat site."""
    import csv
    import io
    robots = "".join(f"User-agent: {b}\nAllow: /\nDisallow: /requests/\n\n" for b in AI_BOTS)
    write("robots.txt", robots + f"User-agent: *\nAllow: /\nDisallow: /requests/\n\nSitemap: {SITE}/sitemap.xml\n")

    gname = {g["s"]: g["n"] for g in cat["groups"]}
    rows = [{"code": i["c"], "material": i["d"], "category": gname[i["g"]], "unit": unit_word(i["u"]),
             "price_ngn_abuja": i["p"], "low_ngn": i["lo"], "high_ngn": i["hi"], "previous_ngn": i["pr"] or "",
             "price_checked": i["set"] or "", "confidence": i["conf"] or "", "url": SITE + i["s"]} for i in cat["items"]]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
    write("data/prices.csv", buf.getvalue())
    write("data/prices.json", json.dumps({
        "source": "Buildocrat (buildocrat.store), built from the Nigeria Construction Rate Book",
        "licence": "CC BY 4.0, credit Buildocrat", "updated": cat["updated"], "currency": "NGN",
        "basis": f"Buildocrat selling price, Abuja, before delivery (rate book market price + {round(CFG['buyMargin'] * 100)}% margin)",
        "state_factors": {s_["n"]: s_["f"] for s_ in cat["states"]}, "items": rows}, ensure_ascii=False, indent=1))

    # feed: one entry per Rate Book edition, history kept in pipeline/feed-history.json
    hist_path = os.path.join(PIPE, "feed-history.json")
    hist = json.load(open(hist_path, encoding="utf-8")) if os.path.exists(hist_path) else []
    if not any(h["date"] == cat["updated"] for h in hist):
        moved = sorted([i for i in cat["items"] if i["pr"] and i["pr"] != i["p"]], key=lambda i: -abs(i["p"] - i["pr"]) / i["pr"])
        lines = [f"{i['d']}: {naira(i['pr'])} → {naira(i['p'])} per {unit_word(i['u'])}" for i in moved[:25]]
        hist.insert(0, {"date": cat["updated"], "count": len(moved), "lines": lines})
        hist = hist[:52]
        json.dump(hist, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    items = []
    for h in hist:
        pub = dt.datetime.fromisoformat(h["date"]).strftime("%a, %d %b %Y 09:00:00 +0100")
        body = ("<ul>" + "".join(f"<li>{e(x)}</li>" for x in h["lines"]) + "</ul>") if h["lines"] else "<p>No price changes this week.</p>"
        items.append(f"<item><title>Building material prices, {e(fdate(h['date']))}: {h['count']} changes</title>"
                     f"<link>{SITE}/materials/</link><guid isPermaLink=\"false\">bdc-prices-{h['date']}</guid><pubDate>{pub}</pubDate>"
                     f"<description><![CDATA[{body}<p>See all prices at {SITE}/materials/</p>]]></description></item>")
    write("feed.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>
<title>Buildocrat — building material price updates</title><link>{SITE}/</link>
<atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>
<description>Weekly changes to Buildocrat's building material prices in Nigeria.</description><language>en-NG</language>
{"".join(items)}
</channel></rss>
""")

    full = [f"# Buildocrat — full price list ({fdate(cat['updated'])})", "",
            f"Buildocrat selling prices in naira, Abuja, before delivery. Other states: multiply by the state factor. Order on WhatsApp {CFG['whatsappDisplay']} or at {SITE}/buy/.",
            "", "## State factors", ""] + [f"- {s_['n']}: ×{s_['f']}" for s_ in cat["states"]]
    for g in cat["groups"]:
        full += ["", f"## {g['n']}", ""]
        full += [f"- {i['d']}: {naira(i['p'])} per {unit_word(i['u'])} ({SITE}{i['s']})" for i in cat["items"] if i["g"] == g["s"]]
    full += ["", "## Stockpile bundle offers", ""]
    by = {i["c"]: i for i in cat["items"]}
    for b in cat["bundles"]:
        m = sum(by[c]["p"] * q for c, q in b["lines"])
        full.append(f"- {b['name']} ({b['for']}): {naira(m * (1 - b['discount']))} paid in full, Abuja (market value {naira(m)})")
    full += ["", "## FAQ", ""] + [f"Q: {q}\nA: {a}\n" for q, a in FAQ]
    write("llms-full.txt", "\n".join(full) + "\n")

    write("offline.html", """<!doctype html><html lang="en-NG"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Offline | Buildocrat</title><meta name="robots" content="noindex"><meta name="theme-color" content="#D5DFDB" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0D1412" media="(prefers-color-scheme: dark)">
<link rel="icon" href="/icons/icon-192.png" type="image/png"><link rel="manifest" href="/manifest.webmanifest">
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#F4F6F2;color:#0F1A14;font:16px/1.55 Inter,system-ui,sans-serif;padding:16px;box-sizing:border-box}
.c{background:#fff;border-radius:22px;max-width:440px;padding:30px 28px;box-shadow:0 10px 30px rgba(11,61,42,.12)}
img{width:56px;height:56px;border-radius:14px}h1{color:#0B3D2A;font-size:1.5rem;margin:14px 0 6px;line-height:1.2}
a{display:inline-block;margin:14px 8px 0 0;background:#00A651;color:#fff;text-decoration:none;font-weight:700;padding:10px 20px;border-radius:999px}
@media (prefers-color-scheme:dark){body{background:#0C130F;color:#ECF3EE}.c{background:#141F19}h1{color:#7EE2A8}}</style>""" + head_analytics() + """</head>
<body><div class="c"><img src="/icons/icon-192.png" alt=""><h1>You're offline</h1>
<p>This page isn't saved on this device yet. The shop, stockpile offers and this week's prices still open offline from your last visit. Your cart is kept; send the order when you're back online.</p>
<a href="/buy/">Open the shop</a><a href="/stockpile/">Stockpile offers</a></div></body></html>
""")


def main(argv):
    d = load_rate_data(argv)
    cat = build_catalog(d)
    cat_json = json.dumps(cat, ensure_ascii=False, separators=(",", ":"))
    ver = hashlib.sha1((cat_json + asset_hash()).encode()).hexdigest()[:10]
    cat["v"] = ver
    os.makedirs(os.path.join(DOCS, "data"), exist_ok=True)
    write("data/catalog.json", json.dumps(cat, ensure_ascii=False, separators=(",", ":")))
    make_icons()

    # wipe generated material pages so removed lines disappear
    shutil.rmtree(os.path.join(DOCS, "materials"), ignore_errors=True)

    urls = []

    def put(path, text, pri="0.6"):
        write(path.lstrip("/") + ("index.html" if path.endswith("/") else ""), text)
        if "noindex" not in text[:3000]:
            urls.append((path, pri))

    put("/", page_home(cat, ver), "1.0")
    put("/buy/", page_buy(cat, ver), "0.9")
    put("/stockpile/", page_stockpile(cat, ver), "0.9")
    put("/sell/", page_sell(cat, ver), "0.8")
    put("/source/", page_source(cat, ver), "0.8")
    put("/risk-control/", page_risk(cat, ver), "0.8")
    put("/help/", page_help(ver), "0.5")
    put("/requests/", page_requests(ver))
    put("/materials/", page_materials_index(cat, ver), "0.8")
    write("404.html", page_404(ver))

    gname = {g["s"]: g for g in cat["groups"]}
    locs = d["locations"]
    for g in cat["groups"]:
        items = [i for i in cat["items"] if i["g"] == g["s"]]
        put(f"/materials/{g['s']}/", page_group(cat, g, items, ver), "0.7")
        for n, i in enumerate(items):
            same = [x for x in items if x["cat"] == i["cat"] and x is not i]
            related = (same + [x for x in items if x not in same and x is not i])[:8]
            loc_rows = "".join(f"<tr><td>{e(l[0])}</td><td>{naira(nice(i['p'] * l[1]))}</td></tr>" for l in locs)
            put(i["s"], page_item(cat, i, gname[i["g"]], related, ver, loc_rows), "0.6")

    today = cat["updated"]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p, pri in urls:
        sm.append(f"<url><loc>{SITE}{p}</loc><lastmod>{today}</lastmod><priority>{pri}</priority></url>")
    sm.append("</urlset>")
    write("sitemap.xml", "\n".join(sm))
    write_extras(cat, d, ver)
    write("CNAME", SITE.split("//")[1] + "\n")
    write(".nojekyll", "")

    top = [i for i in cat["items"] if i["c"] in cat["watch"]]
    write("llms.txt", f"""# Buildocrat — buildocrat.store

> Buildocrat ({CFG['legalName']}, CAC RC {CFG['rc']}, Abuja) sells, stockpiles, sources and lists building materials for every Nigerian state. Prices are Buildocrat selling prices built from the weekly Nigeria Construction Rate Book ({CFG['rateBookUrl']}), Abuja base adjusted by state. Every order, offer, listing and request is finished in a WhatsApp chat on {CFG['whatsappDisplay']}; payment is only to a Buildocrat company account.

Prices updated: {today}. {len(cat['items'])} material lines.

## Key prices (Abuja, before delivery)
""" + "\n".join(f"- {i['d']}: {naira(i['p'])} per {unit_word(i['u'])} ({SITE}{i['s']})" for i in top) + f"""

## Services
- [Buy]({SITE}/buy/): cart of materials, sent to WhatsApp for confirmation and invoice.
- [Stockpile]({SITE}/stockpile/): bundle offers (pay in full discount or 3/6-month plans, held for call-off) and Price Lock (fix prices 3–12 months; activation deposit; zero fees, spread only).
- [Sell]({SITE}/sell/): manufacturers, dealers, quarries and individuals list materials.
- [Source]({SITE}/source/): send a list or BoQ for quotes, including imported and bulk items.
- [Risk control]({SITE}/risk-control/): estimate material price exposure and request a risk plan.
- [All materials]({SITE}/materials/)
- [How it works & FAQ]({SITE}/help/)

## Data
- [Full price list for AI assistants]({SITE}/llms-full.txt)
- [All prices, CSV]({SITE}/data/prices.csv) and [JSON]({SITE}/data/prices.json) (CC BY 4.0)
- [Weekly price changes, RSS]({SITE}/feed.xml)
""")

    manifest = {
        "name": "Buildocrat — building materials", "short_name": "Buildocrat", "start_url": "/?src=app",
        "scope": "/", "display": "standalone", "background_color": "#D5DFDB", "theme_color": "#165E57",
        "description": "Buy, stockpile, sell and source building materials in Nigeria.",
        "icons": [{"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "/icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
        "shortcuts": [{"name": "Buy materials", "url": "/buy/"}, {"name": "Stockpile offers", "url": "/stockpile/"},
                      {"name": "Price Lock", "url": "/stockpile/#lock"}, {"name": "Sell materials", "url": "/sell/"}],
    }
    write("manifest.webmanifest", json.dumps(manifest, indent=1))
    write("sw.js", f"""// Buildocrat service worker, edition {ver}
const V = "bdc-{ver}";
const SHELL = ["/", "/buy/", "/stockpile/", "/sell/", "/source/", "/risk-control/", "/help/", "/requests/", "/materials/", "/offline.html",
  "/assets/app.css?v={ver}", "/assets/app.js?v={ver}", "/assets/pwa.js?v={ver}", "/data/catalog.json?v={ver}", "/icons/icon-192.png", "/manifest.webmanifest"];
self.addEventListener("install", ev => {{ ev.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); }});
self.addEventListener("activate", ev => {{ ev.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim())); }});
self.addEventListener("message", ev => {{
  if (ev.data && ev.data.t === "warm") caches.open(V).then(c => Promise.all(ev.data.urls.map(u => c.match(u).then(hit => hit || c.add(u).catch(() => {{}})))));
}});
self.addEventListener("fetch", ev => {{
  const u = new URL(ev.request.url);
  if (ev.request.method !== "GET" || u.origin !== location.origin) return;
  if (ev.request.mode === "navigate") {{
    ev.respondWith(fetch(ev.request).then(r => {{ if (r.ok) {{ const c = r.clone(); caches.open(V).then(x => x.put(ev.request, c)); }} return r; }})
      .catch(() => caches.match(ev.request, {{ ignoreSearch: true }}).then(r => r || caches.match("/offline.html"))));
    return;
  }}
  ev.respondWith(caches.match(ev.request).then(r => r || fetch(ev.request).then(res => {{
    if (res.ok) {{ const c = res.clone(); caches.open(V).then(x => x.put(ev.request, c)); }} return res; }})));
}});
""")

    print(f"Built {len(urls)} indexable pages, {len(cat['items'])} materials, {len(cat['groups'])} groups, "
          f"{len(cat['bundles'])} bundles; prices dated {today}; version {ver}")


if __name__ == "__main__":
    main(sys.argv)
