(() => {
  "use strict";
  const root = document.getElementById("board");
  const cfg = {
    feed: root.dataset.feed, advance: root.dataset.advance,
    poll: (Number(root.dataset.poll) || 10) * 1000, ws: root.dataset.ws || "",
  };
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const NS = "http://www.w3.org/2000/svg";
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || "";
  let seen = null, fetchedAt = Date.now(), pollMs = cfg.poll, pollTimer = null, ws = null, wsTimer = null, debounce = null;

  // Every value from the server is written with textContent, never innerHTML:
  // customer names and items are user-supplied.
  function clock() {
    const s = document.createElementNS(NS, "svg");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true");
    const c = document.createElementNS(NS, "circle");
    c.setAttribute("cx", "12"); c.setAttribute("cy", "12"); c.setAttribute("r", "9");
    const p = document.createElementNS(NS, "path");
    p.setAttribute("d", "M12 7v5l3 2");
    s.append(c, p);
    return s;
  }
  const ageText = (sec) => {
    const m = Math.floor(sec / 60);
    if (m < 1) return "Just now";
    return m < 60 ? m + " min" : Math.floor(m / 60) + " h " + (m % 60) + " min";
  };
  function paintAge(card) {
    const sec = Number(card.dataset.age) + (Date.now() - fetchedAt) / 1000;
    const limit = Number(card.dataset.late) * 60;
    card.querySelector(".age span").textContent = ageText(sec);
    card.classList.toggle("late", limit > 0 && sec >= limit);
    card.classList.toggle("warn", limit > 0 && sec >= limit * 0.7 && sec < limit);
  }

  function buildCard(o, isNew) {
    const card = el("article", "card" + (isNew && !reduce ? " enter" : ""));
    card.dataset.age = o.age_seconds;
    card.dataset.late = o.late_after_minutes || 0;
    const top = el("div", "top");
    top.append(el("span", "ref", o.reference));
    const age = el("span", "age");
    age.append(clock(), el("span"));
    top.append(age);
    card.append(top, el("p", "who", o.customer || "Customer"));
    const list = el("ul", "items");
    o.items.forEach((t) => list.append(el("li", null, t)));
    if (o.more_items) list.append(el("li", null, "+ " + o.more_items + " more"));
    card.append(list);
    const foot = el("div", "foot");
    foot.append(el("strong", null, "GH\u20B5 " + Number(o.total).toFixed(2)), el("span", "pill", o.payment_method));
    card.append(foot);
    if (o.city) card.append(el("div", "items", o.city));
    if (o.next_label) {
      const b = el("button", "btn", o.next_label);
      b.type = "button";
      b.addEventListener("click", () => advance(o, b));
      card.append(b);
    }
    paintAge(card);
    return card;
  }

  function render(data) {
    fetchedAt = Date.now();
    const known = new Set();
    data.columns.forEach((c) => c.orders.forEach((o) => known.add(o.reference)));
    data.columns.forEach((col) => {
      let node = root.querySelector('[data-status="' + col.status + '"]');
      if (!node) {
        node = el("section", "col");
        node.dataset.status = col.status;
        const h = el("h2"); h.append(el("span", null, col.label), el("span", "n"));
        node.append(h, el("div", "list"));
        root.append(node);
      }
      let fresh = 0;
      const list = node.querySelector(".list");
      list.replaceChildren();
      col.orders.forEach((o) => {
        const isNew = seen !== null && !seen.has(o.reference);
        if (isNew) fresh++;
        list.append(buildCard(o, isNew));
      });
      if (!col.orders.length) list.append(el("div", "empty", "Nothing here"));
      node.querySelector(".n").textContent = col.orders.length;
      node.classList.toggle("has-new", fresh > 0 && col.status === "PENDING");
    });
    seen = known;
    const waiting = data.columns.find((c) => c.status === "PENDING").orders.length;
    document.title = (waiting ? "(" + waiting + ") " : "") + "Live orders";
    $("today").textContent = "Today: " + data.today.delivered + " delivered, " + data.today.cancelled + " cancelled";
  }

  function conn(state, text) {
    const c = $("conn");
    c.className = "conn " + state;
    c.textContent = text;
  }
  function toast(msg, isErr) {
    const t = $("toast");
    t.textContent = msg; t.className = "toast" + (isErr ? " err" : ""); t.hidden = false;
    clearTimeout(toast.t);
    toast.t = setTimeout(() => { t.hidden = true; }, 4000);
  }

  async function refresh() {
    try {
      const res = await fetch(cfg.feed, { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (res.status === 401 || res.status === 403) {
        conn("off", "Signed out"); toast("Your session has ended. Please sign in again.", true); stop(); return;
      }
      if (!res.ok) throw new Error(res.status);
      render(await res.json());
      conn("live", ws && ws.readyState === 1 ? "Live" : "Updating every " + pollMs / 1000 + " s");
    } catch (e) {
      conn("off", "Offline, retrying");
    }
  }
  function schedule() { clearInterval(pollTimer); pollTimer = setInterval(refresh, pollMs); }
  function stop() { clearInterval(pollTimer); if (ws) ws.close(); }

  async function advance(o, btn) {
    btn.disabled = true;
    try {
      const res = await fetch(cfg.advance.replace("__ref__", encodeURIComponent(o.reference)), {
        method: "POST", credentials: "same-origin",
        headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" },
        body: new URLSearchParams({ from_status: o.status }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        toast(body.detail || "Could not update the order.", true);
      }
      await refresh();
    } catch (e) {
      toast("No connection. Try again.", true); btn.disabled = false;
    }
  }

  // Optional WebSocket (set DASHBOARD_WS_URL once Dev 4 adds a staff group).
  // Any message triggers a refresh; polling stays on as a slow safety net.
  function connectWs() {
    if (!cfg.ws) return;
    ws = new WebSocket(cfg.ws);
    ws.onopen = () => { pollMs = 60000; schedule(); conn("live", "Live"); };
    ws.onmessage = () => { clearTimeout(debounce); debounce = setTimeout(refresh, 300); };
    ws.onclose = () => { pollMs = cfg.poll; schedule(); clearTimeout(wsTimer); wsTimer = setTimeout(connectWs, 5000); };
  }

  setInterval(() => document.querySelectorAll(".card").forEach(paintAge), 20000);
  refresh(); schedule(); connectWs();
})();