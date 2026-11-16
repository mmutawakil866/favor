(() => {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const root = document.getElementById("reports");
  const feed = root.dataset.feed;
  const ALL = JSON.parse(document.getElementById("statuses").textContent);
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };
  const ICONS = {
    revenue: '<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
    orders: '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 17.5v-11"/>',
    trend: '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
    cancel: '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/>',
    tag: '<path d="M12.6 2.6A2 2 0 0 0 11.2 2H4a2 2 0 0 0-2 2v7.2a2 2 0 0 0 .6 1.4l8.7 8.7a2.4 2.4 0 0 0 3.4 0l6.6-6.6a2.4 2.4 0 0 0 0-3.4z"/><circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/>',
    bike: '<circle cx="5.5" cy="17.5" r="3.5"/><circle cx="18.5" cy="17.5" r="3.5"/><path d="M15 6a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm-3 11.5V14l-3-3 4-3 2 3h2"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  };
  // Static, trusted markup only. Nothing from the server ever goes through innerHTML.
  const icon = (name) => {
    const s = document.createElementNS(NS, "svg");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("class", "i"); s.setAttribute("aria-hidden", "true");
    s.innerHTML = ICONS[name];
    return s;
  };
  const SYMBOL = { GHS: "GH\u20B5", NGN: "\u20A6" };
  let currency = "GHS";
  const money = (n) => (SYMBOL[currency] || currency) + " " +
    Number(n).toLocaleString("en", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const iso = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  const shortDate = (s) => {
    const [y, m, d] = s.split("-").map(Number);
    return d + " " + ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m - 1];
  };
  const daysAgo = (n) => { const d = new Date(); d.setDate(d.getDate() - n); return iso(d); };

  const q = new URLSearchParams(location.search);
  const state = { from: q.get("date_from") || daysAgo(29), to: q.get("date_to") || iso(new Date()), statuses: new Set(q.getAll("status")) };
  let last = null, seq = 0;

  function panel(id) { const n = $(id); n.replaceChildren(); return n; }
  const empty = (msg) => el("div", "empty", msg);
  const row = (name, pct, value, sub) => {
    const r = el("div", "row");
    r.append(el("span", "nm", name));
    const track = el("div", "bar-track"), fill = el("div", "bar-fill");
    fill.style.width = Math.max(pct, pct > 0 ? 2 : 0) + "%";
    track.append(fill);
    const num = el("span", "num", value);
    if (sub) num.append(" ", el("span", "sub", sub));
    r.append(track, num);
    return r;
  };

  function kpis(s) {
    const items = [
      ["revenue", "Revenue", money(s.revenue)],
      ["orders", "Orders", String(s.orders_count)],
      ["trend", "Average order", money(s.average_order_value)],
      ["cancel", "Cancelled", String(s.cancelled_count)],
      ["tag", "Discounts given", money(s.discounts_total)],
      ["bike", "Delivery fees", money(s.delivery_fees_total)],
    ];
    const box = panel("kpis");
    items.forEach(([ic, label, val]) => {
      const k = el("div", "kpi"), lab = el("div", "lab");
      lab.append(icon(ic), label);
      k.append(lab, el("div", "val", val));
      box.append(k);
    });
  }

  function daily(rows) {
    const box = panel("daily");
    if (!rows.length) { box.append(empty("No orders in this period.")); return; }
    const W = 760, H = 230, L = 6, B = 26, T = 18, n = rows.length;
    const max = Math.max(...rows.map((r) => Number(r.revenue)), 1);
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 " + W + " " + H); svg.setAttribute("class", "chart");
    svg.setAttribute("role", "img"); svg.setAttribute("aria-label", "Daily revenue bar chart");
    const defs = document.createElementNS(NS, "defs");
    defs.innerHTML = '<linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f6b91f"/><stop offset=".55" stop-color="#e8531a"/><stop offset="1" stop-color="#c1241a"/></linearGradient>';
    svg.append(defs);
    const slot = (W - L * 2) / n, bw = Math.max(2, slot * 0.7);
    rows.forEach((r, i) => {
      const h = Number(r.revenue) / max * (H - B - T);
      const rect = document.createElementNS(NS, "rect");
      rect.setAttribute("class", "b"); rect.setAttribute("fill", "url(#g)"); rect.setAttribute("rx", "3");
      rect.setAttribute("x", L + i * slot + (slot - bw) / 2); rect.setAttribute("width", bw);
      rect.setAttribute("y", H - B - Math.max(h, Number(r.revenue) > 0 ? 2 : 0)); rect.setAttribute("height", Math.max(h, Number(r.revenue) > 0 ? 2 : 0));
      const t = document.createElementNS(NS, "title");
      t.textContent = shortDate(r.day) + ": " + money(r.revenue) + ", " + r.orders_count + " orders";
      rect.append(t); svg.append(rect);
    });
    const text = (x, y, s, anchor) => {
      const t = document.createElementNS(NS, "text");
      t.setAttribute("x", x); t.setAttribute("y", y); t.setAttribute("text-anchor", anchor || "start"); t.textContent = s;
      svg.append(t);
    };
    text(L, 12, "Highest day: " + money(max));
    text(L, H - 6, shortDate(rows[0].day));
    if (n > 2) text(W / 2, H - 6, shortDate(rows[Math.floor(n / 2)].day), "middle");
    if (n > 1) text(W - L, H - 6, shortDate(rows[n - 1].day), "end");
    box.append(svg);
  }

  function counts(boxId, obj) {
    const box = panel(boxId), vals = Object.values(obj), max = Math.max(...vals, 1);
    Object.entries(obj).forEach(([k, v]) => box.append(row(k.replaceAll("_", " ").toLowerCase(), v / max * 100, String(v))));
  }

  function lists(data) {
    const pay = panel("by-pay"), maxPay = Math.max(...data.by_payment_method.map((p) => Number(p.revenue)), 1);
    if (!data.by_payment_method.length) pay.append(empty("No delivered orders yet."));
    data.by_payment_method.forEach((p) => pay.append(row(p.payment_method, Number(p.revenue) / maxPay * 100, money(p.revenue), p.orders + " orders")));
    const pop = panel("popular"), maxU = Math.max(...data.popular_items.map((p) => p.units), 1);
    if (!data.popular_items.length) pop.append(empty("No items sold in this period."));
    data.popular_items.forEach((p, i) => pop.append(row((i + 1) + ". " + p.name, p.units / maxU * 100, p.units + " sold", money(p.revenue))));
  }

  function stats(boxId, pairs) {
    const box = panel(boxId), grid = el("div", "stats");
    pairs.forEach(([label, val]) => { const s = el("div", "stat"); s.append(el("b", null, val), el("span", null, label)); grid.append(s); });
    box.append(grid);
  }
  const mins = (v) => (v == null ? "No data" : v + " min");

  function delivery(d) {
    stats("delivery", [
      ["Deliveries", String(d.deliveries_count)], ["Delivered", String(d.delivered_count)],
      ["Failed", String(d.failed_count)], ["Cancelled", String(d.cancelled_count)],
      ["Rider accepts in", mins(d.avg_assign_to_accepted_min)], ["Assigned to delivered", mins(d.avg_assign_to_delivered_min)],
    ]);
  }

  function reviews(r) {
    const box = panel("reviews");
    if (!r.count) { box.append(empty("No reviews in this period.")); return; }
    [["Overall", r.overall], ["Food", r.food], ["Service", r.service]].forEach(([n, v]) => box.append(row(n, v / 5 * 100, v.toFixed(1) + " / 5")));
    box.append(el("p", "note", r.count + " reviews" + (r.hidden_count ? ", " + r.hidden_count + " hidden by moderators" : "")));
  }

  function render(data) {
    last = data; currency = data.sales.currency || currency;
    kpis(data.sales); daily(data.daily);
    counts("by-status", data.by_status); lists(data); delivery(data.delivery); reviews(data.reviews);
  }

  function note(msg, err) { const n = $("note"); n.textContent = msg; n.className = "note" + (err ? " err" : ""); }
  function sync() {
    const p = new URLSearchParams({ date_from: state.from, date_to: state.to });
    state.statuses.forEach((s) => p.append("status", s));
    history.replaceState(null, "", "?" + p);
    return p;
  }
  async function load() {
    $("from").value = state.from; $("to").value = state.to;
    if (state.from > state.to) { note("The start date is after the end date.", true); return; }
    const mine = ++seq, p = sync();
    note("Loading");
    try {
      const res = await fetch(feed + "?" + p, { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (mine !== seq) return;
      if (res.status === 401 || res.status === 403) { note("Your session has ended. Please sign in again.", true); return; }
      if (!res.ok) { const b = await res.json().catch(() => ({})); note(b.detail || "Could not load the reports.", true); return; }
      render(await res.json());
      note(shortDate(state.from) + " to " + shortDate(state.to) + (state.statuses.size ? ", filtered by status" : ""));
    } catch (e) {
      if (mine === seq) note("No connection. Change a filter to try again.", true);
    }
  }

  function csv() {
    if (!last) return;
    const lines = ["date,orders,cancelled,revenue"].concat(last.daily.map((r) => [r.day, r.orders_count, r.cancelled_count, r.revenue].join(",")));
    const a = el("a"); a.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    a.download = "daily-sales-" + state.from + "-to-" + state.to + ".csv"; a.click(); URL.revokeObjectURL(a.href);
  }

  function build() {
    [["7 days", 6], ["30 days", 29], ["90 days", 89]].forEach(([label, n]) => {
      const b = el("button", null, label); b.type = "button";
      b.addEventListener("click", () => { state.from = daysAgo(n); state.to = iso(new Date()); load(); });
      $("presets").append(b);
    });
    ALL.forEach((s) => {
      const b = el("button", null, s.replaceAll("_", " ").toLowerCase()); b.type = "button";
      b.setAttribute("aria-pressed", state.statuses.has(s));
      b.addEventListener("click", () => {
        state.statuses.has(s) ? state.statuses.delete(s) : state.statuses.add(s);
        b.setAttribute("aria-pressed", state.statuses.has(s)); load();
      });
      $("chips").append(b);
    });
    $("from").addEventListener("change", (e) => { state.from = e.target.value; load(); });
    $("to").addEventListener("change", (e) => { state.to = e.target.value; load(); });
    const c = $("csv"); c.append(icon("download"), "Download CSV"); c.addEventListener("click", csv);
  }
  build(); load();
})();