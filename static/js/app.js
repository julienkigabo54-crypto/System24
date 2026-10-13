/* Shared helpers for every page. */
const App = (() => {
  async function api(path, options = {}) {
    const opts = { headers: {}, ...options };
    if (opts.json !== undefined) {
      opts.method = opts.method || "POST";
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.json);
      delete opts.json;
    }
    let res;
    try { res = await fetch("/api" + path, opts); }
    catch (e) { throw new Error("Cannot reach the server. Is it running?"); }
    let data = null;
    try { data = await res.json(); } catch (e) { /* not JSON */ }
    if (!res.ok) throw new Error((data && data.error) || `Request failed (${res.status})`);
    return data;
  }

  function toast(message, type = "ok") {
    let box = document.getElementById("toasts");
    if (!box) { box = document.createElement("div"); box.id = "toasts"; document.body.appendChild(box); }
    const t = document.createElement("div");
    t.className = "toast " + (type === "error" ? "error" : "");
    t.textContent = message;
    box.appendChild(t);
    setTimeout(() => t.remove(), type === "error" ? 6000 : 3500);
  }

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (n, d = 0) => (n === null || n === undefined ? "–" : Number(n).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d }));
  const money = (n) => (n === null || n === undefined ? "–" : Number(n).toLocaleString(undefined, { style: "currency", currency: "USD" }));
  const BADGE = { "Critical": "critical", "Low Stock": "low", "OK": "ok", "Overstock": "over" };
  const badge = (s) => `<span class="badge ${BADGE[s] || ""}">${esc(s)}</span>`;
  const COLORS = { "Critical": "#d92d20", "Low Stock": "#e8920c", "OK": "#12a150", "Overstock": "#7a52e0" };

  const charts = {};
  function chart(id, config) {
    if (charts[id]) charts[id].destroy();
    const el = document.getElementById(id);
    if (!el || typeof Chart === "undefined") return null;
    const dark = matchMedia("(prefers-color-scheme: dark)").matches;
    Chart.defaults.color = dark ? "#98a3bd" : "#64708a";
    Chart.defaults.borderColor = dark ? "#2a3550" : "#e3e8f1";
    config.options = { responsive: true, maintainAspectRatio: false, ...(config.options || {}) };
    charts[id] = new Chart(el, config);
    return charts[id];
  }

  /* Fill a <select> with products; returns the product list. */
  async function productSelect(select, { includeAll = false } = {}) {
    const items = await api("/products");
    select.innerHTML = (includeAll ? '<option value="">All products</option>' : "") +
      items.map((p) => `<option value="${esc(p.product_id)}">${esc(p.product_id)} – ${esc(p.name)}</option>`).join("");
    return items;
  }

  /* Run an async action on a button: disables it while working and reports errors. */
  async function busy(button, fn) {
    const label = button.textContent;
    button.disabled = true;
    try { return await fn(); }
    catch (e) { toast(e.message, "error"); }
    finally { button.disabled = false; button.textContent = label; }
  }

  return { api, toast, esc, num, money, badge, chart, productSelect, busy, COLORS };
})();
