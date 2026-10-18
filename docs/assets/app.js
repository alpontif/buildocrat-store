/* Buildocrat store — every journey ends in a prefilled WhatsApp chat. Hand-written; no build step. */
(() => {
  "use strict";
  const B = window.BDC || {};
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const LS = {
    get(k, d) { try { const v = localStorage.getItem("bdc." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("bdc." + k, JSON.stringify(v)); } catch (e) { /* private mode */ } }
  };
  const fmt = n => "₦" + Math.round(n || 0).toLocaleString("en-NG");
  const nice = x => { const s = x < 1000 ? 10 : x < 100000 ? 50 : x < 1e6 ? 100 : 1000; return Math.round(x / s) * s; };
  const num = v => { const n = parseFloat(String(v == null ? "" : v).replace(/[^\d.]/g, "")); return isFinite(n) ? n : 0; };
  const r100 = x => Math.round(x / 100) * 100;
  const pct = x => (Math.round(x * 1000) / 10).toString().replace(/\.0$/, "") + "%";
  const UNIT = { nr: "each", bag: "bag", t: "tonne", load: "load", m2: "m²", m3: "m³", m: "metre", length: "length", L: "litre", kg: "kg", roll: "roll", pail: "pail", tin: "tin", sheet: "sheet", set: "set", pair: "pair", pack: "pack", coil: "coil" };
  const uw = u => UNIT[u] || u;
  const qfmt = q => (Math.round(q * 100) / 100).toLocaleString("en-NG");
  const today = () => new Date();
  const dstr = d => d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  const WA_ICON = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true" style="fill:currentColor;stroke:none"><path d="M12 2.2a9.7 9.7 0 0 0-8.3 14.8L2.3 21.8l4.9-1.3A9.7 9.7 0 1 0 12 2.2Zm0 17.7c-1.5 0-3-.4-4.2-1.2l-.3-.2-2.9.8.8-2.8-.2-.3A8 8 0 1 1 12 19.9Z"/></svg>';

  // ------------------------------------------------------------ catalogue
  let CAT = null; const BY = {};
  function loadCat() {
    if (!loadCat.p) loadCat.p = fetch("/data/catalog.json?v=" + (B.v || ""))
      .then(r => { if (!r.ok) throw new Error("catalog " + r.status); return r.json(); })
      .then(c => { CAT = c; c.items.forEach(i => { BY[i.c] = i; }); return c; });
    return loadCat.p;
  }
  const stateName = () => LS.get("state", "FCT (Abuja)");
  function factor() {
    if (!CAT) return 1;
    const s = CAT.states.find(x => x.n === stateName());
    return s ? s.f : 1;
  }
  const price = i => nice(i.p * factor());
  const groupName = s => { const g = CAT && CAT.groups.find(x => x.s === s); return g ? g.n : s; };
  const stepFor = u => (u === "t" ? 0.5 : 1);

  function paintPrices() {
    $$("[data-state-label]").forEach(el => { el.textContent = stateName(); });
    if (!CAT) return;
    $$("[data-price]").forEach(el => { const i = BY[el.dataset.price]; if (i) el.textContent = fmt(price(i)); });
    $$("[data-change]").forEach(el => {
      const i = BY[el.dataset.change];
      if (!i || !i.pr || i.pr === i.p) { el.textContent = "steady"; el.className = "tick-ch muted"; return; }
      const ch = (i.p - i.pr) / i.pr;
      el.textContent = (ch > 0 ? "▲ " : "▼ ") + pct(Math.abs(ch)) + " this week";
      el.className = "tick-ch " + (ch > 0 ? "up" : "down");
    });
  }

  // ------------------------------------------------------------------ cart
  const getCart = () => LS.get("cart", {});
  function setCart(c) { LS.set("cart", c); paintCartCount(); document.dispatchEvent(new CustomEvent("bdc:cart")); }
  function addToCart(code, q) {
    const c = getCart(); c[code] = Math.round(((c[code] || 0) + q) * 100) / 100;
    if (c[code] <= 0) delete c[code];
    setCart(c);
  }
  function paintCartCount() {
    const n = Object.keys(getCart()).length;
    $$("[data-cart-count]").forEach(el => { el.textContent = n; el.hidden = !n; });
  }

  // ----------------------------------------------------------------- sheet
  const sheet = $("[data-sheet]");
  let lastFocus = null;
  function openSheet(title, html) {
    lastFocus = document.activeElement;
    sheet.innerHTML = `<div class="sheet-box" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="sheet-head"><h2>${esc(title)}</h2><button class="x" type="button" data-close aria-label="Close">×</button></div>${html}</div>`;
    sheet.hidden = false; document.body.style.overflow = "hidden";
    const f = sheet.querySelector("input,select,button:not(.x),a"); (f || sheet.querySelector(".x")).focus();
    return sheet.firstChild;
  }
  function closeSheet() { sheet.hidden = true; sheet.innerHTML = ""; document.body.style.overflow = ""; if (lastFocus) lastFocus.focus(); }
  sheet.addEventListener("click", ev => { if (ev.target === sheet || ev.target.closest("[data-close]")) closeSheet(); });
  document.addEventListener("keydown", ev => { if (ev.key === "Escape" && !sheet.hidden) closeSheet(); });
  window.addEventListener("hashchange", () => { if (!sheet.hidden) closeSheet(); });
  function toast(msg) {
    const t = document.createElement("div"); t.className = "toast"; t.textContent = msg; t.setAttribute("role", "status");
    document.body.appendChild(t); setTimeout(() => t.remove(), 2200);
  }

  function pickState() {
    loadCat().then(() => {
      const cur = stateName();
      const box = openSheet("Deliver to which state?", `<p class="small muted">Prices adjust to your state. Delivery is quoted on WhatsApp.</p><div class="state-list">${CAT.states.map(s => `<button type="button" data-st="${esc(s.n)}" aria-pressed="${s.n === cur}">${esc(s.n)}</button>`).join("")}</div>`);
      box.addEventListener("click", ev => {
        const b = ev.target.closest("[data-st]"); if (!b) return;
        LS.set("state", b.dataset.st); closeSheet(); paintPrices();
        document.dispatchEvent(new CustomEvent("bdc:state"));
        toast("Prices now for " + b.dataset.st);
      });
    });
  }
  $$("[data-state-btn]").forEach(b => b.addEventListener("click", pickState));

  // ------------------------------------------------------- whatsapp hand-off
  function makeRef(letter) {
    const d = today(); const p = n => String(n).padStart(2, "0");
    const abc = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; let r = "";
    const rnd = (window.crypto && crypto.getRandomValues) ? crypto.getRandomValues(new Uint8Array(4)) : [1, 2, 3, 4].map(() => Math.random() * 256);
    for (let k = 0; k < 4; k++) r += abc[rnd[k] % abc.length];
    return `BDC-${letter}-${String(d.getFullYear()).slice(2)}${p(d.getMonth() + 1)}${p(d.getDate())}-${r}`;
  }
  const waLink = text => `https://wa.me/${B.wa}?text=${encodeURIComponent(text)}`;
  function sendToWhatsApp(kind, ref, text, meta) {
    const reqs = LS.get("reqs", []);
    reqs.unshift({ ref, kind, title: meta.title, total: meta.total || null, date: today().toISOString(), text });
    LS.set("reqs", reqs.slice(0, 50));
    const url = waLink(text);
    const w = window.open(url, "_blank", "noopener");
    const box = openSheet("Finish on WhatsApp", `
      <p>Your reference is</p><p><span class="ref">${esc(ref)}</span></p>
      <p class="small muted">${w ? "WhatsApp should now be open with your message ready. Just press send." : "Tap the button to open WhatsApp with your message ready, then press send."} We reply from ${esc(B.waDisplay)} to confirm details and send an invoice for a Buildocrat company account.</p>
      <a class="btn btn-wa" href="${url}" target="_blank" rel="noopener">${WA_ICON} Open WhatsApp</a>
      <p style="margin-top:12px"><button class="btn btn-ghost btn-sm" type="button" data-copy>Copy message</button> <a class="small" href="/requests/">My requests</a></p>
      <details><summary class="small">See the message</summary><pre class="msg">${esc(text)}</pre></details>`);
    box.querySelector("[data-copy]").addEventListener("click", () => {
      (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(() => toast("Message copied"), () => toast("Copy not available"));
    });
    if (meta.onSent) meta.onSent();
  }
  const priceNote = () => `Prices from buildocrat.store for ${stateName()}, ${CAT ? dstr(new Date(CAT.updated)) : ""} list. Delivery to be quoted.`;

  // --------------------------------------------------------------- helpers
  function fillStates(sel) {
    sel.innerHTML = CAT.states.map(s => `<option${s.n === stateName() ? " selected" : ""}>${esc(s.n)}</option>`).join("");
  }
  function moneyInputs(root) {
    $$("[data-money]", root).forEach(inp => inp.addEventListener("input", () => {
      const n = num(inp.value); const pos = inp.value.length - inp.selectionStart;
      inp.value = n ? Math.round(n).toLocaleString("en-NG") : "";
      try { inp.setSelectionRange(inp.value.length - pos, inp.value.length - pos); } catch (e) { /* number inputs */ }
    }));
  }
  function fillDatalist() {
    const dl = $("#catalog-names"); if (!dl || dl.children.length) return;
    dl.innerHTML = CAT.items.map(i => `<option value="${esc(i.d)}"></option>`).join("");
  }
  const byName = name => CAT.items.find(i => i.d.toLowerCase() === String(name).trim().toLowerCase());
  function formData(form) {
    const o = {}; new FormData(form).forEach((v, k) => { if (o[k] !== undefined) o[k] = [].concat(o[k], v); else o[k] = v; }); return o;
  }
  function need(form, names) {
    $$(".err", form).forEach(x => x.remove());
    for (const n of names) {
      const el = form.elements[n];
      if (el && !String(el.value).trim()) {
        el.insertAdjacentHTML("afterend", '<span class="err">Please fill this in.</span>'); el.focus(); return false;
      }
    }
    return true;
  }
  function qtyBox(val, step) {
    return `<div class="qty"><button type="button" data-dec aria-label="Less">−</button><input type="number" min="0" step="any" inputmode="decimal" value="${val}" data-step="${step}" aria-label="Quantity"><button type="button" data-inc aria-label="More">+</button></div>`;
  }
  // generic +/- buttons
  document.addEventListener("click", ev => {
    const b = ev.target.closest("[data-inc],[data-dec]"); if (!b) return;
    const inp = b.parentElement.querySelector("input"); const st = parseFloat(inp.dataset.step || inp.step) || 1;
    const v = Math.max(0, Math.round((num(inp.value) + (b.hasAttribute("data-inc") ? st : -st)) * 100) / 100);
    inp.value = v; inp.dispatchEvent(new Event("change", { bubbles: true }));
  });

  // ------------------------------------------------------------- item page
  function initItem() {
    $$("[data-buy]").forEach(box => {
      const code = box.dataset.buy;
      const inp = box.querySelector("input");
      loadCat().then(() => { const i = BY[code]; if (i) inp.dataset.step = stepFor(i.u); });
      box.querySelector("[data-add]").addEventListener("click", () => {
        const q = num(inp.value); if (!q) return toast("Enter a quantity");
        addToCart(code, q); toast("Added to cart");
      });
      box.querySelector("[data-now]").addEventListener("click", () => {
        const q = num(inp.value) || 1; addToCart(code, q); location.href = "/buy/#cart";
      });
    });
  }

  // -------------------------------------------------------------- buy page
  function initBuy() {
    const shop = $("[data-shop]"); if (!shop) return;
    const params = new URLSearchParams(location.search);
    const qEl = $("[data-q]"), list = $("[data-list]"), moreBtn = $("[data-more]"), countEl = $("[data-count]"), chips = $("[data-chips]");
    let sec = "building", grp = params.get("g") || "", shown = 40;
    qEl.value = params.get("q") || "";
    loadCat().then(() => {
      if (grp) { const g = CAT.groups.find(x => x.s === grp); if (g) sec = g.sec; }
      paintSec(); renderChips(); render(); renderCart();
      if (location.hash === "#cart") setTimeout(() => $("#cart").scrollIntoView(), 50);
    }).catch(() => { countEl.textContent = "Prices could not load. Check your connection, or message us on WhatsApp."; });

    function paintSec() { $$("[data-secval]").forEach(b => b.setAttribute("aria-selected", b.dataset.secval === sec)); }
    $("[data-sec]").addEventListener("click", ev => {
      const b = ev.target.closest("[data-secval]"); if (!b) return;
      sec = b.dataset.secval; grp = ""; shown = 40; paintSec(); renderChips(); render();
    });
    function renderChips() {
      const gs = CAT.groups.filter(g => sec === "all" || g.sec === sec);
      chips.innerHTML = `<button class="chip" type="button" data-g="" aria-pressed="${!grp}">All</button>` +
        gs.map(g => `<button class="chip" type="button" data-g="${g.s}" aria-pressed="${g.s === grp}">${esc(g.n)}</button>`).join("");
    }
    chips.addEventListener("click", ev => {
      const b = ev.target.closest("[data-g]"); if (!b) return;
      grp = b.dataset.g; shown = 40; renderChips(); render();
    });
    let tmr; qEl.addEventListener("input", () => { clearTimeout(tmr); tmr = setTimeout(() => { shown = 40; render(); }, 120); });
    moreBtn.addEventListener("click", () => { shown += 60; render(); });

    function matches() {
      const q = qEl.value.trim().toLowerCase();
      const toks = q.split(/\s+/).filter(Boolean);
      let res = CAT.items.filter(i => {
        if (!q) { if (grp && i.g !== grp) return false; if (!grp && sec !== "all" && CAT.groups.find(g => g.s === i.g).sec !== sec) return false; }
        else if (grp && i.g !== grp) return false;
        if (!toks.length) return true;
        const hay = (i.d + " " + i.cat + " " + groupName(i.g) + " " + i.c).toLowerCase();
        return toks.every(t => hay.includes(t));
      });
      if (q) res = res.slice().sort((a, b) => (b.d.toLowerCase().includes(q) - a.d.toLowerCase().includes(q)) || (b.conf === "HIGH") - (a.conf === "HIGH"));
      return res;
    }
    function render() {
      const res = matches(); const cart = getCart();
      countEl.textContent = res.length ? `${res.length.toLocaleString()} materials · prices for ${stateName()}, before delivery` : "No match. Try another word, or send us a sourcing request.";
      list.innerHTML = res.slice(0, shown).map(i => {
        const inC = cart[i.c];
        return `<li class="prow" data-code="${i.c}"><div class="pinfo"><a class="pname" href="${i.s}">${esc(i.d)}</a>
          <span class="punit">${fmt(price(i))} per ${esc(uw(i.u))}${i.lk ? ' · <span class="badge">Price Lock</span>' : ""}${i.sf ? ' · supply &amp; fix' : ""}</span></div>
          <div class="pright">${qtyBox(inC || 1, stepFor(i.u))}<button class="add${inC ? " in" : ""}" type="button" data-addc>${inC ? "✓ In cart" : "Add"}</button></div></li>`;
      }).join("") + (res.length ? "" : `<li><a class="btn btn-primary" href="/source/?q=${encodeURIComponent(qEl.value)}">Ask us to source “${esc(qEl.value)}”</a></li>`);
      moreBtn.hidden = res.length <= shown;
    }
    list.addEventListener("click", ev => {
      const b = ev.target.closest("[data-addc]"); if (!b) return;
      const row = b.closest("[data-code]"); const q = num(row.querySelector("input").value);
      if (!q) return toast("Enter a quantity");
      const c = getCart(); c[row.dataset.code] = q; setCart(c);
      b.classList.add("in"); b.textContent = "✓ In cart"; toast("Added to cart");
    });
    list.addEventListener("change", ev => {
      const row = ev.target.closest("[data-code]"); if (!row || !ev.target.matches("input")) return;
      const c = getCart(); if (c[row.dataset.code] !== undefined) { const q = num(ev.target.value); if (q) c[row.dataset.code] = q; else delete c[row.dataset.code]; setCart(c); }
    });
    document.addEventListener("bdc:state", () => { render(); renderCart(); });
    document.addEventListener("bdc:cart", () => renderCart());

    // cart + checkout
    const body = $("[data-cart-body]");
    function cartLines() { const c = getCart(); return Object.keys(c).filter(k => BY[k]).map(k => ({ i: BY[k], q: c[k] })); }
    function renderCart() {
      if (!CAT) return;
      const lines = cartLines();
      if (!lines.length) { body.innerHTML = '<p class="muted">Your cart is empty. Add materials above, or take a <a href="/stockpile/">stockpile offer</a>.</p>'; return; }
      const sub = lines.reduce((s, l) => s + price(l.i) * l.q, 0);
      const lockable = lines.filter(l => l.i.lk).reduce((s, l) => s + price(l.i) * l.q, 0);
      if (!body.querySelector("[data-cart-lines]")) {
        body.innerHTML = '<div data-cart-lines></div>' + checkoutForm();
        fillStates($("[data-states]", body));
        body.querySelector("[data-states]").addEventListener("change", ev => { LS.set("state", ev.target.value); paintPrices(); document.dispatchEvent(new CustomEvent("bdc:state")); });
      }
      const st = body.querySelector("[data-states]"); if (st.value !== stateName()) st.value = stateName();
      body.querySelector("[data-subtotal]").textContent = fmt(sub);
      body.querySelector("[data-cart-lines]").innerHTML = `<div class="card">
        ${lines.map(l => `<div class="cart-line" data-code="${l.i.c}"><div><div class="cl-n">${esc(l.i.d)}</div><div class="small muted">${fmt(price(l.i))} per ${esc(uw(l.i.u))}</div></div>
          <div class="cl-t">${fmt(price(l.i) * l.q)}</div><div>${qtyBox(l.q, stepFor(l.i.u))}</div><button class="cl-x" type="button" data-rm>Remove</button></div>`).join("")}
        <div class="totals"><div><span>Materials (${lines.length} line${lines.length > 1 ? "s" : ""})</span><b class="grand">${fmt(sub)}</b></div>
        <div class="small muted"><span>Delivery to ${esc(stateName())}</span><span>quoted on WhatsApp</span></div></div>
        ${lockable >= CAT.lock.minValue ? `<p class="small"><span class="badge">Price Lock</span> Not buying it all now? <a href="/stockpile/?from=cart#lock">Lock today's price on the ${fmt(lockable)} of eligible items</a> and draw down monthly.</p>` : ""}
      </div>`;
    }
    function checkoutForm() {
      return `<form class="card form" data-checkout style="margin-top:14px">
        <h2>Send order to WhatsApp</h2>
        <div class="row2"><label>Your name<input name="name" required autocomplete="name"></label>
        <label>Phone / WhatsApp<input name="phone" type="tel" required autocomplete="tel"></label></div>
        <div class="row2"><label>Delivery state<select name="state" data-states></select></label>
        <label>Needed by<input name="date" type="date"></label></div>
        <label>Delivery address / site location<textarea name="addr" rows="2" required placeholder="Street, area, town, landmark"></textarea></label>
        <div class="row2"><label>I am a<select name="who"><option>Homeowner / individual</option><option>Contractor</option><option>Developer</option><option>Diaspora client</option><option>Business / institution</option></select></label>
        <label>Payment<select name="pay"><option>Bank transfer after invoice</option><option>Part-payment now, balance before delivery</option><option>Talk to me about a payment plan</option></select></label></div>
        <label>Notes <span class="opt">(optional)</span><textarea name="notes" rows="2" placeholder="Preferred brand, offloading, access for trucks…"></textarea></label>
        <button class="btn btn-wa" type="submit">${WA_ICON} Send order on WhatsApp · <span data-subtotal></span></button>
        <p class="small muted">Nothing is charged here. We confirm stock, delivery and the invoice in the chat.</p>
      </form>`;
    }
    body.addEventListener("click", ev => {
      const rm = ev.target.closest("[data-rm]"); if (!rm) return;
      const c = getCart(); delete c[rm.closest("[data-code]").dataset.code]; setCart(c); render();
    });
    body.addEventListener("change", ev => {
      const line = ev.target.closest(".cart-line"); if (!line || !ev.target.matches("input")) return;
      const c = getCart(); const q = num(ev.target.value); if (q) c[line.dataset.code] = q; else delete c[line.dataset.code];
      setCart(c); render();
    });
    body.addEventListener("submit", ev => {
      ev.preventDefault(); const f = ev.target;
      if (!need(f, ["name", "phone", "addr"])) return;
      const d = formData(f); const lines = cartLines(); const ref = makeRef("B");
      const sub = lines.reduce((s, l) => s + price(l.i) * l.q, 0);
      const shown = lines.slice(0, 60);
      const txt = [`*Buildocrat order* ${ref}`, "",
        `Name: ${d.name}`, `Phone: ${d.phone}`, `I am a: ${d.who}`, `Deliver to: ${d.addr.trim()}, ${d.state}`,
        d.date ? `Needed by: ${dstr(new Date(d.date))}` : "", "", "*Items*",
        ...shown.map((l, n) => `${n + 1}. ${l.i.d} — ${qfmt(l.q)} ${uw(l.i.u)} × ${fmt(price(l.i))} = ${fmt(price(l.i) * l.q)}`),
        lines.length > shown.length ? `…and ${lines.length - shown.length} more lines (full list to follow)` : "",
        "", `*Materials subtotal: ${fmt(sub)}*`, priceNote(), `Payment: ${d.pay}`, d.notes ? `Notes: ${d.notes}` : "", "",
        "Please confirm availability, delivery cost and send the invoice."].filter((x, k, a) => x !== "" || a[k - 1] !== "").join("\n");
      sendToWhatsApp("Order", ref, txt, { title: `Order · ${lines.length} lines`, total: sub, onSent: () => { setCart({}); render(); } });
    });
  }

  // ---------------------------------------------------------- stockpile page
  function initStockpile() {
    const tabs = $("[data-stab]"); if (!tabs) return;
    const params = new URLSearchParams(location.search);
    function show(t) {
      $$("[data-tab]", tabs).forEach(b => b.setAttribute("aria-selected", b.dataset.tab === t));
      $$("[data-panel]").forEach(p => { p.hidden = p.dataset.panel !== t; });
    }
    tabs.addEventListener("click", ev => { const b = ev.target.closest("[data-tab]"); if (b) { show(b.dataset.tab); history.replaceState(null, "", b.dataset.tab === "lock" ? "#lock" : location.pathname); } });
    if (location.hash === "#lock" || params.get("lock") || params.get("from")) show("lock");
    window.addEventListener("hashchange", () => show(location.hash === "#lock" ? "lock" : "offers"));

    loadCat().then(() => {
      renderBundles(); initLock();
      document.addEventListener("bdc:state", () => { renderBundles(); calcLock(); });
    });

    // ---- bundles
    const grid = $("[data-bundles]");
    function bundleCalc(b) {
      const market = b.lines.reduce((s, [c, q]) => s + price(BY[c]) * q, 0);
      return { market, plans: CAT.plans.map(p => {
        const monthlyRaw = p.months > 1 ? (market * (1 + p.premium) * (1 - p.upfront)) / (p.months - 1) : 0;
        const monthly = r100(monthlyRaw);
        const total = p.id === "full" ? r100(market * (1 - b.discount)) : r100(market * (1 + p.premium) * p.upfront) + monthly * (p.months - 1);
        const up = p.months > 1 ? total - monthly * (p.months - 1) : total;
        return Object.assign({}, p, { total, up, monthly });
      }) };
    }
    function renderBundles() {
      grid.innerHTML = CAT.bundles.map(b => {
        const c = bundleCalc(b); const full = c.plans[0];
        return `<article class="bcard" data-bundle="${b.id}"><span class="ribbon">Save ${pct(b.discount)}</span>
          <h2>${esc(b.name)}</h2><p class="small muted" style="margin:0">${esc(b.for)}</p>
          <details><summary>What's in it (${b.lines.length} item${b.lines.length > 1 ? "s" : ""})</summary><ul>${b.lines.map(([cd, q]) => `<li>${qfmt(q)} ${esc(uw(BY[cd].u))} — ${esc(BY[cd].d)}</li>`).join("")}</ul></details>
          <div><span class="was">${fmt(c.market)}</span><div class="bprice">${fmt(full.total)}</div><span class="small muted">pay in full · ${esc(stateName())} · held up to ${CAT.holdMonths} months</span></div>
          <div class="plans" role="radiogroup" aria-label="Payment plan">${c.plans.map((p, k) => `<label><input type="radio" name="plan-${b.id}" value="${p.id}"${k ? "" : " checked"}><span><b>${esc(p.label)}: ${p.months > 1 ? fmt(p.up) + " now + " + (p.months - 1) + " × " + fmt(p.monthly) : fmt(p.total)}</b>${esc(p.note)}${p.months > 1 ? " · total " + fmt(p.total) : ""}</span></label>`).join("")}</div>
          <button class="btn btn-primary" type="button" data-reserve>${WA_ICON} Reserve this offer</button></article>`;
      }).join("");
    }
    grid.addEventListener("click", ev => {
      const btn = ev.target.closest("[data-reserve]"); if (!btn) return;
      const card = btn.closest("[data-bundle]"); const b = CAT.bundles.find(x => x.id === card.dataset.bundle);
      const planId = (card.querySelector("input[type=radio]:checked") || {}).value || "full";
      const box = openSheet("Reserve " + b.name, `<form class="form" data-resform>
        <div class="row2"><label>Your name<input name="name" required autocomplete="name"></label><label>Phone / WhatsApp<input name="phone" type="tel" required autocomplete="tel"></label></div>
        <div class="row2"><label>Delivery state<select name="state" data-states></select></label><label>First delivery<select name="first"><option>As soon as possible</option><option>Within 1 month</option><option>In 1–3 months</option><option>In 3–6 months</option><option>Not sure yet — hold it</option></select></label></div>
        <label>Site town / area<input name="town" required></label>
        <label>I am a<select name="who"><option>Homeowner / individual</option><option>Diaspora client</option><option>Contractor</option><option>Developer</option></select></label>
        <button class="btn btn-wa" type="submit">${WA_ICON} Reserve on WhatsApp</button></form>`);
      fillStates(box.querySelector("[data-states]"));
      box.querySelector("form").addEventListener("submit", e2 => {
        e2.preventDefault(); const f = e2.target; if (!need(f, ["name", "phone", "town"])) return;
        const d = formData(f);
        if (d.state !== stateName()) { LS.set("state", d.state); paintPrices(); }
        const c = bundleCalc(b); const p = c.plans.find(x => x.id === planId); const ref = makeRef("S");
        const txt = [`*Stockpile offer reservation* ${ref}`, "", `Offer: ${b.name} (${b.for})`,
          `Plan: ${p.label} — ${p.months > 1 ? `${fmt(p.up)} now + ${p.months - 1} × ${fmt(p.monthly)} (total ${fmt(p.total)})` : `${fmt(p.total)} (save ${pct(b.discount)})`}`,
          `Market value today: ${fmt(c.market)}`, "", "*Contents*", ...b.lines.map(([cd, q]) => `- ${qfmt(q)} ${uw(BY[cd].u)} ${BY[cd].d}`), "",
          `Name: ${d.name}`, `Phone: ${d.phone}`, `I am a: ${d.who}`, `Site: ${d.town}, ${d.state}`, `First delivery: ${d.first}`, "",
          priceNote(), "Please confirm the offer and send the invoice for the first payment."].join("\n");
        sendToWhatsApp("Stockpile offer", ref, txt, { title: b.name + " · " + p.label, total: p.total });
      });
    });

    // ---- price lock
    const lf = $("[data-lockform]"), out = $("[data-lockout]"), linesBox = $("[data-llines]");
    const eligible = () => CAT.items.filter(i => i.lk && !i.sf);
    function lineHtml(code, q) {
      const opts = CAT.groups.filter(g => CAT.lock.eligibleGroups.includes(g.s)).map(g => `<optgroup label="${esc(g.n)}">${eligible().filter(i => i.g === g.s).map(i => `<option value="${i.c}"${i.c === code ? " selected" : ""}>${esc(i.d)}</option>`).join("")}</optgroup>`).join("");
      return `<div class="line" data-lline><label class="wide">Material<select data-lc>${opts}</select></label><label>Quantity<input type="number" min="0" step="any" inputmode="decimal" value="${q}" data-lq></label><label>Unit<input readonly tabindex="-1" data-lu></label><button type="button" class="rm" data-lrm aria-label="Remove">×</button></div>`;
    }
    function initLock() {
      $("[data-lseg]").innerHTML = CAT.lock.segments.map(s => `<option value="${s.id}">${esc(s.label)} — ${pct(s.deposit)} deposit</option>`).join("");
      $("[data-ltenor]").innerHTML = CAT.lock.tenors.map(t => `<option value="${t.months}"${t.months === 6 ? " selected" : ""}>${t.months} months</option>`).join("");
      const nm = new Date(); nm.setMonth(nm.getMonth() + 1);
      $("[data-lstart]").value = nm.toISOString().slice(0, 7);
      $("[data-linfl]").value = Math.round(CAT.risk.inflationBase * 100);
      let start = [["M-CEM-07", 400], ["M-STL-01", 3], ["M-BLK-01", 3000]];
      if (params.get("lock") && BY[params.get("lock")] && BY[params.get("lock")].lk) start = [[params.get("lock"), BY[params.get("lock")].u === "t" ? 2 : 100]];
      if (params.get("from") === "cart") { const c = getCart(); const l = Object.keys(c).filter(k => BY[k] && BY[k].lk && !BY[k].sf).map(k => [k, c[k]]); if (l.length) start = l; }
      linesBox.innerHTML = start.filter(([c]) => BY[c]).map(([c, q]) => lineHtml(c, q)).join("");
      calcLock();
    }
    $("[data-ladd]").addEventListener("click", () => { linesBox.insertAdjacentHTML("beforeend", lineHtml("M-RF-01", 200)); calcLock(); });
    linesBox.addEventListener("click", ev => { const r = ev.target.closest("[data-lrm]"); if (r) { r.closest("[data-lline]").remove(); calcLock(); } });
    lf.addEventListener("input", () => calcLock()); lf.addEventListener("change", () => calcLock());
    function lockState() {
      const seg = CAT.lock.segments.find(s => s.id === $("[data-lseg]").value) || CAT.lock.segments[0];
      const months = +$("[data-ltenor]").value; const ten = CAT.lock.tenors.find(t => t.months === months);
      const lines = $$("[data-lline]", linesBox).map(el => { const i = BY[el.querySelector("[data-lc]").value]; el.querySelector("[data-lu]").value = uw(i.u); return { i, q: num(el.querySelector("[data-lq]").value) }; }).filter(l => l.q > 0);
      const now = lines.reduce((s, l) => s + price(l.i) * l.q, 0);
      const locked = r100(now * (1 + ten.spread));
      const sv = $("[data-lstart]").value; let off = 1;
      if (sv) { const [y, m] = sv.split("-").map(Number); const n = today(); off = Math.max(0, (y - n.getFullYear()) * 12 + (m - 1 - n.getMonth())); }
      const mkt = rate => { let s = 0; for (let k = 0; k < months; k++) s += (now / months) * Math.pow(1 + rate, (off + k + 0.5) / 12); return s; };
      const ib = num($("[data-linfl]").value) / 100;
      return { seg, months, ten, lines, now, locked, deposit: r100(locked * seg.deposit), monthly: r100(locked / months), off, mBase: mkt(ib), mHigh: mkt(Math.max(ib, CAT.risk.inflationHigh)), ib };
    }
    function calcLock() {
      if (!CAT || !out) return;
      const s = lockState();
      if (!s.lines.length) { out.innerHTML = '<p class="muted">Add at least one material to see your locked price.</p>'; return; }
      const save = s.mBase - s.locked, saveH = s.mHigh - s.locked;
      const small = s.locked < CAT.lock.minValue;
      out.innerHTML = `<h2>Your Price Lock</h2>
        <div class="kpi hl"><span>Locked value for ${s.months} months · ${esc(stateName())}</span><b>${fmt(s.locked)}</b><span>today's prices ${fmt(s.now)} + ${pct(s.ten.spread)} lock spread, no fees</span></div>
        <div class="kgrid"><div class="kpi sun"><span>Activation deposit (${pct(s.seg.deposit)})</span><b>${fmt(s.deposit)}</b></div>
        <div class="kpi"><span>Average monthly draw-down</span><b>${fmt(s.monthly)}</b></div></div>
        <div class="kpi"><span>Buying the same each month at market, if prices rise ${pct(s.ib)} a year</span><b>${fmt(s.mBase)}</b>
          <span>${save >= 0 ? "Price Lock saves about <b>" + fmt(save) + "</b>" : "If prices barely move you pay about " + fmt(-save) + " more, in exchange for certainty"}. In a bad year (${pct(Math.max(s.ib, CAT.risk.inflationHigh))}) it saves about ${fmt(Math.max(0, saveH))}.</span></div>
        <details><summary class="small">Locked unit prices</summary><table class="loc"><tbody>${s.lines.map(l => `<tr><td>${esc(l.i.d)}<br><span class="small muted">${qfmt(l.q)} ${esc(uw(l.i.u))}</span></td><td>${fmt(price(l.i) * (1 + s.ten.spread))}</td></tr>`).join("")}</tbody></table></details>
        ${small ? `<p class="small err">Price Lock starts at ${fmt(CAT.lock.minValue)}. For smaller lists, take a <a href="/stockpile/">bundle offer</a> or <a href="/buy/">buy now</a>.</p>` : ""}
        <form class="form" data-lsend>
          <div class="row2"><label>Your name<input name="name" required autocomplete="name"></label><label>Phone / WhatsApp<input name="phone" type="tel" required autocomplete="tel"></label></div>
          <label>Company <span class="opt">(optional)</span><input name="co" autocomplete="organization"></label>
          <label>Site town / area<input name="town" required></label>
          <button class="btn btn-wa" type="submit"${small ? " disabled" : ""}>${WA_ICON} Request this Price Lock</button>
          <p class="small muted">Indicative. Your lock is confirmed in writing in the chat before any deposit is paid.</p>
        </form>`;
    }
    out.addEventListener("submit", ev => {
      ev.preventDefault(); const f = ev.target; if (!need(f, ["name", "phone", "town"])) return;
      const d = formData(f); const s = lockState(); const ref = makeRef("L");
      const txt = [`*Price Lock request* ${ref}`, "", `Client type: ${s.seg.label}`, `Lock period: ${s.months} months, first delivery ${$("[data-lstart]").value ? new Date($("[data-lstart]").value + "-01").toLocaleDateString("en-GB", { month: "long", year: "numeric" }) : "next month"}`,
        "", "*Materials*", ...s.lines.map(l => `- ${qfmt(l.q)} ${uw(l.i.u)} ${l.i.d} @ ${fmt(price(l.i) * (1 + s.ten.spread))} locked (today ${fmt(price(l.i))})`), "",
        `Value at today's prices: ${fmt(s.now)}`, `*Locked value: ${fmt(s.locked)}* (spread ${pct(s.ten.spread)}, zero fees)`,
        `Activation deposit ${pct(s.seg.deposit)}: ${fmt(s.deposit)}`, `Average monthly draw-down: ${fmt(s.monthly)}`, "",
        `Name: ${d.name}`, d.co ? `Company: ${d.co}` : "", `Phone: ${d.phone}`, `Site: ${d.town}, ${stateName()}`, "",
        priceNote(), "Please confirm the lock terms and send the deposit invoice."].filter(Boolean).join("\n");
      sendToWhatsApp("Price Lock", ref, txt, { title: `Price Lock · ${s.months} months`, total: s.locked });
    });
  }

  // ------------------------------------------------------------ sell page
  function initSell() {
    const form = $("[data-sellform]"); if (!form) return;
    const box = $("[data-sell-lines]");
    const units = ["bag", "tonne", "load", "each", "m²", "metre", "length", "sheet", "roll", "pail", "litre", "kg", "set"];
    const line = () => `<div class="line" data-sline><label class="wide">Product<input list="catalog-names" data-sp placeholder="e.g. Dangote 3X 42.5R, 50kg"></label>
      <label>Your price (₦)<input inputmode="numeric" data-money data-spr></label>
      <label>Per<select data-su>${units.map(u => `<option>${u}</option>`).join("")}</select></label><button type="button" class="rm" data-srm aria-label="Remove">×</button>
      <label>Quantity available<input inputmode="decimal" data-sq placeholder="e.g. 2,000"></label><label>Minimum order<input inputmode="decimal" data-sm placeholder="e.g. 100"></label>
      <span class="small muted wide" data-shint></span></div>`;
    loadCat().then(() => { fillStates(form.querySelector("[data-states]")); fillDatalist(); });
    box.innerHTML = line(); moneyInputs(box);
    $("[data-sell-add]").addEventListener("click", () => { box.insertAdjacentHTML("beforeend", line()); moneyInputs(box.lastElementChild); });
    box.addEventListener("click", ev => { const r = ev.target.closest("[data-srm]"); if (r && $$("[data-sline]", box).length > 1) r.closest("[data-sline]").remove(); });
    box.addEventListener("change", ev => {
      if (!ev.target.matches("[data-sp]") || !CAT) return;
      const i = byName(ev.target.value); const ln = ev.target.closest("[data-sline]");
      if (i) { const u = uw(i.u); const sel = ln.querySelector("[data-su]"); if (![...sel.options].some(o => o.value === u)) sel.insertAdjacentHTML("beforeend", `<option>${u}</option>`); sel.value = u; ln.querySelector("[data-shint]").textContent = `Our current selling price: ${fmt(price(i))} per ${u} in ${stateName()}.`; }
    });
    form.addEventListener("submit", ev => {
      ev.preventDefault(); if (!need(form, ["biz", "name", "phone", "town"])) return;
      const d = formData(form);
      const prods = $$("[data-sline]", box).map(l => ({ p: l.querySelector("[data-sp]").value.trim(), pr: l.querySelector("[data-spr]").value, u: l.querySelector("[data-su]").value, q: l.querySelector("[data-sq]").value, m: l.querySelector("[data-sm]").value })).filter(x => x.p);
      if (!prods.length) { box.querySelector("[data-sp]").focus(); return toast("Add at least one product"); }
      const ref = makeRef("V");
      const txt = [`*Supplier listing* ${ref}`, "", `Seller type: ${d.type}`, `Business: ${d.biz}`, d.rc ? `CAC: ${d.rc}` : "", `Contact: ${d.name}`, `Phone: ${d.phone}`,
        `Location: ${d.town}, ${d.state}`, `Delivery: ${d.delivery}`, `Terms: ${d.credit}`, "", "*Products*",
        ...prods.map((x, n) => `${n + 1}. ${x.p}${x.pr ? ` — ₦${x.pr} per ${x.u}` : ""}${x.q ? `; available ${x.q}` : ""}${x.m ? `; min order ${x.m}` : ""}`),
        d.notes ? "\nNotes: " + d.notes : "", "", "I will send photos / price list / certificates in this chat."].filter(Boolean).join("\n");
      sendToWhatsApp("Seller listing", ref, txt, { title: `${d.biz} · ${prods.length} products` });
    });
  }

  // ----------------------------------------------------------- source page
  function initSource() {
    const form = $("[data-sourceform]"); if (!form) return;
    const box = $("[data-src-lines]"); const params = new URLSearchParams(location.search);
    const line = (desc, q, u) => `<div class="line" data-rline><label class="wide">Material, size or brand<input list="catalog-names" data-rd value="${esc(desc || "")}" placeholder="e.g. 16mm iron rod, Dangote cement, 0.55 longspan"></label>
      <label>Quantity<input inputmode="decimal" data-rq value="${esc(q || "")}"></label><label>Unit<input data-ru value="${esc(u || "")}" placeholder="bags, tonnes…"></label><button type="button" class="rm" data-rrm aria-label="Remove">×</button></div>`;
    box.innerHTML = line(params.get("q") || "") + line();
    loadCat().then(() => {
      fillStates(form.querySelector("[data-states]")); fillDatalist();
      const it = BY[params.get("item")]; if (it) box.innerHTML = line(it.d, "", uw(it.u)) + line();
    });
    moneyInputs(form);
    $("[data-src-add]").addEventListener("click", () => box.insertAdjacentHTML("beforeend", line()));
    box.addEventListener("click", ev => { const r = ev.target.closest("[data-rrm]"); if (r && $$("[data-rline]", box).length > 1) r.closest("[data-rline]").remove(); });
    box.addEventListener("change", ev => {
      if (!ev.target.matches("[data-rd]") || !CAT) return;
      const i = byName(ev.target.value); const u = ev.target.closest("[data-rline]").querySelector("[data-ru]");
      if (i && !u.value) u.value = uw(i.u);
    });
    form.addEventListener("submit", ev => {
      ev.preventDefault(); if (!need(form, ["name", "phone", "town"])) return;
      const d = formData(form);
      const items = $$("[data-rline]", box).map(l => ({ d: l.querySelector("[data-rd]").value.trim(), q: l.querySelector("[data-rq]").value.trim(), u: l.querySelector("[data-ru]").value.trim() })).filter(x => x.d);
      if (!items.length) { box.querySelector("[data-rd]").focus(); return toast("Add at least one material"); }
      const reqs = [].concat(d.req || []);
      const ref = makeRef("Q");
      const txt = [`*Sourcing request* ${ref}`, "", `Name: ${d.name}`, `Phone: ${d.phone}`, `I am a: ${d.who}`, `Project: ${d.ptype}`, `Deliver to: ${d.town}, ${d.state}`,
        d.date ? `Needed by: ${dstr(new Date(d.date))}` : "", d.budget ? `Budget: ₦${d.budget}` : "", "", "*Materials*",
        ...items.map((x, n) => `${n + 1}. ${x.d}${x.q ? ` — ${x.q} ${x.u}` : ""}`),
        reqs.length ? "\nAlso needed: " + reqs.join(", ") : "", d.notes ? "Notes: " + d.notes : "", "",
        "Please source and quote delivered to site. I can send the BoQ here."].filter(Boolean).join("\n");
      sendToWhatsApp("Sourcing request", ref, txt, { title: `Sourcing · ${items.length} lines` });
    });
  }

  // ------------------------------------------------------------- risk page
  function initRisk() {
    const form = $("[data-riskform]"); if (!form) return;
    const out = $("[data-riskout]");
    const LOCK_SHARE = 0.6; // share of material spend that is cement, steel, blocks, aggregates and roofing
    moneyInputs(form);
    loadCat().then(() => {
      fillStates(form.querySelector("[data-states]"));
      form.elements.ib.value = Math.round(CAT.risk.inflationBase * 100);
      form.elements.ih.value = Math.round(CAT.risk.inflationHigh * 100);
      form.elements.share.value = Math.round(CAT.risk.materialsShare * 100);
      calc();
    });
    form.addEventListener("input", calc); form.addEventListener("change", calc);
    function model() {
      const f = form.elements; const budget = num(f.budget.value), share = num(f.share.value) / 100;
      const S = +f.start.value, D = +f.dur.value, ib = num(f.ib.value) / 100, ih = num(f.ih.value) / 100;
      const M = budget * share; const lockMax = Math.max(...CAT.lock.tenors.map(t => t.months));
      const tenor = (CAT.lock.tenors.find(t => t.months >= Math.min(S + D, lockMax)) || CAT.lock.tenors[CAT.lock.tenors.length - 1]);
      let rB = 0, rH = 0, covB = 0, covSpend = 0;
      for (let m = 0; m < D; m++) {
        const k = S + m + 0.5; const sp = M / D;
        const gB = sp * (Math.pow(1 + ib, k / 12) - 1), gH = sp * (Math.pow(1 + ih, k / 12) - 1);
        rB += gB; rH += gH;
        if (S + m < tenor.months) { covB += gB; covSpend += sp; }
      }
      const lockCost = covSpend * LOCK_SHARE * tenor.spread;
      const withLock = rB - covB * LOCK_SHARE + lockCost;
      const k = x => Math.round(x / 1000) * 1000;
      return { budget, M, S, D, ib, ih, rB: k(rB), rH: k(rH), withLock: k(withLock), lockCost: k(lockCost), tenor };
    }
    function calc() {
      if (!CAT) return; const r = model();
      if (!r.budget) { out.innerHTML = '<p class="muted">Enter your budget to see your exposure.</p>'; return; }
      const w = x => Math.max(0, Math.min(100, x / r.rH * 100));
      out.innerHTML = `<h2>Your price exposure</h2>
        <div class="kpi"><span>Materials in your budget</span><b>${fmt(r.M)}</b></div>
        <div class="kpi sun"><span>Likely extra cost from price rises (${pct(r.ib)} a year)</span><b>${fmt(r.rB)}</b><span>${pct(r.rB / r.budget)} of your total budget</span></div>
        <div class="kpi"><span>In a bad year (${pct(r.ih)} a year)</span><b>${fmt(r.rH)}</b><span>${pct(r.rH / r.budget)} of your total budget</span></div>
        <div class="kpi hl"><span>With Price Lock on core materials (${r.tenor.months}-month lock)</span><b>${fmt(Math.max(0, r.withLock))}</b><span>includes about ${fmt(r.lockCost)} lock spread</span></div>
        <div class="bar" aria-hidden="true"><i style="width:${w(r.withLock)}%;background:var(--green)"></i><i style="width:${w(r.rB) - w(r.withLock)}%;background:var(--sun)"></i><i style="width:${100 - w(r.rB)}%;background:#E26D5A"></i></div>
        <div class="legend"><span><i style="background:var(--green)"></i>with Price Lock</span><span><i style="background:var(--sun)"></i>likely rise</span><span><i style="background:#E26D5A"></i>bad-year rise</span></div>
        <p class="small muted">Assumes materials are bought evenly over the build and that cement, iron rods, blocks, sand and roofing are about ${Math.round(LOCK_SHARE * 100)}% of the materials bill. An estimate, not a quote.</p>`;
    }
    const SERVICE = { price: "Price Lock on cement, iron rods, blocks, sand & roofing", scarcity: "Stockpile and hold for call-off", quality: "Checked suppliers, manufacturer-direct supply, test certificates",
      theft: "Staged deliveries matched to the build programme", quantity: "Engineer BoQ / quantity check", supplier: "Pay Buildocrat; suppliers paid on confirmed delivery",
      fx: "Imported items quoted and fixed at today's exchange rate", diaspora: "Diaspora desk: buying, delivery and photo reports for you" };
    form.addEventListener("submit", ev => {
      ev.preventDefault(); if (!need(form, ["name", "phone"])) return;
      const d = formData(form); const r = model(); const risks = [].concat(d.risk || []);
      const ref = makeRef("R");
      const txt = [`*Project risk review* ${ref}`, "", `Name: ${d.name}`, `Phone: ${d.phone}`, `Project: ${d.ptype}, ${d.state}`,
        `Budget: ${fmt(r.budget)} (materials ${fmt(r.M)})`, `Starts in ${r.S} month(s), runs ${r.D} months`, "",
        `Likely price-rise cost (${pct(r.ib)}/yr): ${fmt(r.rB)}`, `Bad-year cost (${pct(r.ih)}/yr): ${fmt(r.rH)}`, `With ${r.tenor.months}-month Price Lock: about ${fmt(Math.max(0, r.withLock))}`, "",
        "*Risks to cover*", ...(risks.length ? risks.map(k => "- " + SERVICE[k]) : ["- Not sure yet, please advise"]), "",
        "Please send me a risk plan and quote."].join("\n");
      sendToWhatsApp("Risk review", ref, txt, { title: `Risk review · ${d.ptype}`, total: r.budget });
    });
  }

  // ---------------------------------------------------------- requests page
  function initRequests() {
    const box = $("[data-requests]"); if (!box) return;
    function render() {
      const reqs = LS.get("reqs", []);
      if (!reqs.length) { box.innerHTML = '<p class="muted">Nothing sent from this device yet. <a href="/buy/">Start shopping</a>.</p>'; return; }
      box.innerHTML = reqs.map((r, k) => `<div class="req"><div class="req-top"><b>${esc(r.ref)}</b><span class="small muted">${esc(dstr(new Date(r.date)))}</span></div>
        <span>${esc(r.kind)} · ${esc(r.title || "")}${r.total ? " · " + fmt(r.total) : ""}</span>
        <div class="cta-row" style="margin:6px 0 0"><a class="btn btn-wa btn-sm" style="width:auto;margin:0" href="${waLink(r.text)}" target="_blank" rel="noopener">${WA_ICON} Open in WhatsApp</a><button class="btn btn-ghost btn-sm" type="button" data-del="${k}">Remove</button></div></div>`).join("");
    }
    box.addEventListener("click", ev => { const b = ev.target.closest("[data-del]"); if (!b) return; const reqs = LS.get("reqs", []); reqs.splice(+b.dataset.del, 1); LS.set("reqs", reqs); render(); });
    render();
  }

  // ------------------------------------------------------------------ boot
  paintCartCount();
  $$("[data-state-label]").forEach(el => { el.textContent = stateName(); });
  const needsCat = $$("[data-price],[data-change]").length && stateName() !== "FCT (Abuja)";
  if (needsCat || B.page === "home") loadCat().then(paintPrices).catch(() => {});
  ({ item: initItem, buy: initBuy, stockpile: initStockpile, sell: initSell, source: initSource, risk: initRisk, requests: initRequests }[B.page] || (() => {}))();
  if (["buy", "stockpile", "sell", "source", "risk", "materials"].includes(B.page)) loadCat().then(paintPrices).catch(() => {});
})();
