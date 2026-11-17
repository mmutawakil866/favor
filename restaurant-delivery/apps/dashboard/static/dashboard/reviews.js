(() => {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const root = document.getElementById("reviews");
  const cfg = { feed: root.dataset.feed, hide: root.dataset.hide, restore: root.dataset.restore };
  const RATINGS = JSON.parse(document.getElementById("ratings").textContent);
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || "";
  let canModerate = JSON.parse(document.getElementById("can-moderate").textContent);
  const state = { visibility: "all", ratings: new Set(), q: "", from: "", to: "", page: 1 };
  let seq = 0, typing = null;

  // Review text is customer-supplied: it is only ever written with textContent.
  function stars(n) {
    const wrap = el("span", "stars");
    wrap.setAttribute("role", "img"); wrap.setAttribute("aria-label", n + " out of 5");
    for (let i = 1; i <= 5; i++) {
      const s = document.createElementNS(NS, "svg");
      s.setAttribute("viewBox", "0 0 24 24");
      if (i <= n) s.setAttribute("class", "on");
      const p = document.createElementNS(NS, "polygon");
      p.setAttribute("points", "12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2");
      s.append(p); wrap.append(s);
    }
    return wrap;
  }
  const when = (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  const toast = (msg, err) => {
    const t = $("toast"); t.textContent = msg; t.className = "toast" + (err ? " err" : ""); t.hidden = false;
    clearTimeout(toast.t); toast.t = setTimeout(() => { t.hidden = true; }, 4000);
  };
  const note = (msg, err) => { const n = $("note"); n.textContent = msg; n.className = "note" + (err ? " err" : ""); };
  const url = (base, id) => base.replace(/\/0\/([a-z]+)\/$/, "/" + id + "/$1/");

  async function post(base, id, body) {
    const res = await fetch(url(base, id), {
      method: "POST", credentials: "same-origin",
      headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" },
      body: new URLSearchParams(body || {}),
    });
    if (!res.ok) { const b = await res.json().catch(() => ({})); throw new Error(b.detail || "Could not update the review."); }
  }

  function actions(card, r) {
    const box = el("div", "actions");
    if (!r.is_visible) {
      const b = el("button", null, "Restore review"); b.type = "button";
      b.addEventListener("click", async () => {
        b.disabled = true;
        try { await post(cfg.restore, r.id); toast("Review restored."); load(true); }
        catch (e) { toast(e.message, true); b.disabled = false; }
      });
      box.append(b); return box;
    }
    const open = el("button", null, "Hide review"); open.type = "button";
    open.addEventListener("click", () => {
      box.replaceChildren();
      const input = el("input"); input.type = "text"; input.maxLength = 200; input.required = true;
      input.placeholder = "Why is this review being hidden?"; input.setAttribute("aria-label", "Reason for hiding");
      const ok = el("button", "danger", "Hide review"); ok.type = "button";
      const no = el("button", null, "Cancel"); no.type = "button";
      ok.addEventListener("click", async () => {
        if (!input.value.trim()) { input.focus(); toast("Give a reason first.", true); return; }
        ok.disabled = true;
        try { await post(cfg.hide, r.id, { reason: input.value.trim() }); toast("Review hidden."); load(true); }
        catch (e) { toast(e.message, true); ok.disabled = false; }
      });
      no.addEventListener("click", () => box.replaceWith(actions(card, r)));
      box.append(input, ok, no); input.focus();
    });
    box.append(open);
    return box;
  }

  function card(r) {
    const c = el("article", "review" + (r.is_visible ? "" : " is-hidden") + (r.overall.score <= 2 ? " low" : ""));
    const head = el("div", "head");
    head.append(stars(r.overall.score), el("span", "meta-line",
      (r.customer || "Customer") + (r.order_reference ? ", order " + r.order_reference : "") + ", " + when(r.created_at)));
    c.append(head);
    const tags = el("div", "tags");
    tags.append(el("span", "tag", "Food: " + r.food.label), el("span", "tag", "Service: " + r.service.label));
    if (!r.is_visible) tags.append(el("span", "tag hide", "Hidden"));
    c.append(tags);
    c.append(r.comment ? el("p", "text", r.comment) : el("p", "text none", "No comment."));
    if (!r.is_visible) {
      c.append(el("p", "hidden-note", "Hidden" + (r.hidden_by ? " by " + r.hidden_by : "") +
        (r.hidden_at ? " on " + when(r.hidden_at) : "") + (r.hidden_reason ? ": " + r.hidden_reason : "")));
    }
    if (canModerate) c.append(actions(c, r));
    return c;
  }

  function summary(d) {
    const box = $("summary"); box.replaceChildren();
    const tile = (v, label) => { const t = el("div", "stat-tile"); t.append(el("b", null, v), el("span", null, label)); box.append(t); };
    const s = d.summary, avg = (v) => (v == null ? "No data" : v.toFixed(1) + " / 5");
    tile(String(d.count), "Reviews match these filters");
    tile(avg(s.overall), "Average overall (visible)");
    tile(avg(s.food), "Average food");
    tile(avg(s.service), "Average service");
    tile(String(d.hidden_count), "Hidden by moderators");
  }

  function params(page) {
    const p = new URLSearchParams({ visibility: state.visibility, page });
    if (state.q) p.set("q", state.q);
    if (state.from) p.set("date_from", state.from);
    if (state.to) p.set("date_to", state.to);
    state.ratings.forEach((r) => p.append("rating", r));
    return p;
  }

  async function load(reset) {
    if (state.from && state.to && state.from > state.to) { note("The start date is after the end date.", true); return; }
    const mine = ++seq;
    if (reset) state.page = 1;
    note("Loading");
    try {
      const res = await fetch(cfg.feed + "?" + params(state.page), { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (mine !== seq) return;
      if (res.status === 401 || res.status === 403) { note("Your session has ended. Please sign in again.", true); return; }
      if (!res.ok) { const b = await res.json().catch(() => ({})); note(b.detail || "Could not load reviews.", true); return; }
      const d = await res.json();
      canModerate = d.can_moderate;
      const list = $("list");
      if (reset) list.replaceChildren();
      d.results.forEach((r) => list.append(card(r)));
      if (!list.children.length) list.append(el("div", "empty", "No reviews match these filters."));
      summary(d);
      $("more").hidden = d.page >= d.pages;
      note("");
    } catch (e) {
      if (mine === seq) note("No connection. Change a filter to try again.", true);
    }
  }

  function build() {
    [["all", "All"], ["visible", "Visible"], ["hidden", "Hidden"]].forEach(([v, label]) => {
      const b = el("button", null, label); b.type = "button"; b.setAttribute("aria-pressed", v === state.visibility);
      b.addEventListener("click", () => {
        state.visibility = v;
        $("vis").querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
        load(true);
      });
      $("vis").append(b);
    });
    RATINGS.forEach((r) => {
      const b = el("button", null, r.label); b.type = "button"; b.setAttribute("aria-pressed", "false");
      b.addEventListener("click", () => {
        state.ratings.has(r.value) ? state.ratings.delete(r.value) : state.ratings.add(r.value);
        b.setAttribute("aria-pressed", state.ratings.has(r.value)); load(true);
      });
      $("chips").append(b);
    });
    $("q").addEventListener("input", (e) => { clearTimeout(typing); typing = setTimeout(() => { state.q = e.target.value.trim(); load(true); }, 350); });
    $("from").addEventListener("change", (e) => { state.from = e.target.value; load(true); });
    $("to").addEventListener("change", (e) => { state.to = e.target.value; load(true); });
    $("more").addEventListener("click", () => { state.page += 1; load(false); });
  }
  build(); load(true);
})();