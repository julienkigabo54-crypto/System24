/* Shared helpers used by every page. */
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
    catch (e) { throw new Error("Cannot reach the system. Please check that the program is still running."); }
    let data = null;
    try { data = await res.json(); } catch (e) { /* the reply was not JSON */ }
    if (!res.ok) throw new Error((data && data.error) || `Something went wrong (code ${res.status}).`);
    return data;
  }

  function toast(message, type = "ok") {
    let box = document.getElementById("toasts");
    if (!box) { box = document.createElement("div"); box.id = "toasts"; box.setAttribute("role", "status"); document.body.appendChild(box); }
    const t = document.createElement("div");
    t.className = "toast " + (type === "error" ? "error" : "");
    t.textContent = message;
    box.appendChild(t);
    setTimeout(() => t.remove(), type === "error" ? 7000 : 4000);
  }

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (n, d = 0) => (n === null || n === undefined ? "-" : Number(n).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d }));
  const money = (n) => (n === null || n === undefined ? "-" : Number(n).toLocaleString(undefined, { style: "currency", currency: "USD" }));
  const longDate = (iso) => new Date(iso + "T12:00:00").toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const dateTime = (iso) => new Date(iso).toLocaleString(undefined, { day: "numeric", month: "long", year: "numeric", hour: "numeric", minute: "2-digit" });

  /* ---- Plain-language names ---- */
  const STATUS_CLASS = { "Critical": "critical", "Low Stock": "low", "OK": "ok", "Overstock": "over" };
  const STATUS_HELP = {
    "Critical": "Out of stock, or the stock will run out before a new delivery could arrive.",
    "Low Stock": "The stock has reached the reorder level. It is time to order more.",
    "OK": "There is enough stock for the coming days.",
    "Overstock": "There is much more stock than will be sold soon. Avoid ordering more.",
  };
  const COLORS = { "Critical": "#b42818", "Low Stock": "#e09a10", "OK": "#1f8a4c", "Overstock": "#6d55c9" };
  const badge = (s) => `<span class="badge ${STATUS_CLASS[s] || "plain"}" title="${esc(STATUS_HELP[s] || "")}">${esc(s)}</span>`;

  const MODEL_NAMES = {
    linear_regression: "Linear Regression",
    random_forest: "Random Forest",
    baseline_moving_average: "Simple average of recent sales",
    no_history: "No sales history yet",
  };
  const MODEL_HELP = {
    linear_regression: "Finds a straight-line relationship between past sales and future sales. Simple and fast.",
    random_forest: "Combines many decision trees. It can pick up more complicated patterns.",
  };
  const modelName = (k) => MODEL_NAMES[k] || k;

  const FEATURE_NAMES = {
    lag_1: "Sales yesterday", lag_7: "Sales one week ago", roll_7: "Average sales of the last 7 days",
    roll_28: "Average sales of the last 28 days", t: "Long-term change over time", is_weekend: "Weekend or not",
    dow_sin: "Day of the week (first part)", dow_cos: "Day of the week (second part)",
    month_sin: "Time of the year (first part)", month_cos: "Time of the year (second part)",
  };
  const featureName = (k) => FEATURE_NAMES[k] || k;

  const TREND = { rising: "Going up", falling: "Going down", stable: "Steady" };

  /* Fields that can be empty in the records, in plain words */
  const FIELD_NAMES = { product_id: "product code", date: "date", stock_in: "stock added", stock_out: "stock removed", demand: "units sold", closing_stock: "stock left at the end of the day" };

  /* ---- Charts ---- */
  const charts = {};
  function chart(id, config) {
    if (charts[id]) charts[id].destroy();
    const el = document.getElementById(id);
    if (!el) return null;
    if (typeof Chart === "undefined") {
      el.parentElement.innerHTML = '<div class="empty">The chart could not be loaded. Please check your internet connection and reload the page.</div>';
      return null;
    }
    Chart.defaults.color = "#52646d";
    Chart.defaults.borderColor = "#e8efee";
    Chart.defaults.font.family = '"Segoe UI", system-ui, sans-serif';
    Chart.defaults.font.size = 13;
    config.options = { responsive: true, maintainAspectRatio: false, ...(config.options || {}) };
    charts[id] = new Chart(el, config);
    return charts[id];
  }

  /* Fill a <select> with products; returns the product list. */
  async function productSelect(select, { includeAll = false } = {}) {
    const items = await api("/products");
    select.innerHTML = (includeAll ? '<option value="">All products</option>' : "") +
      items.map((p) => `<option value="${esc(p.product_id)}">${esc(p.name)} (${esc(p.product_id)})</option>`).join("");
    return items;
  }

  /* Run an action on a button: disables it while working and shows errors clearly. */
  async function busy(button, fn) {
    const label = button.textContent;
    button.disabled = true;
    try { return await fn(); }
    catch (e) { toast(e.message, "error"); }
    finally { button.disabled = false; button.textContent = label; }
  }

  /* The table of products with their status and recommended order, used on two pages. */
  function itemsTable(items, { days, showReorder = false, showCategory = false } = {}) {
    if (!items.length) return '<div class="empty">Nothing to show here.</div>';
    const head = `<tr><th>Product</th><th>Status</th><th class="num">In stock</th>` +
      (showReorder ? '<th class="num">Reorder level</th>' : "") +
      `<th class="num">Expected sales${days ? ` (next ${days} days)` : ""}</th><th class="num">Days the stock will last</th><th class="num">Units to order</th><th class="num">Estimated cost</th></tr>`;
    const rows = items.map((i) => `<tr>
      <td class="product-cell"><b>${esc(i.name)}</b> <small>${esc(i.product_id)}${showCategory ? " - " + esc(i.category) : ""}</small><span class="advice">${esc(i.recommendation)}</span></td>
      <td>${badge(i.status)}</td>
      <td class="num">${num(i.current_stock)}</td>
      ${showReorder ? `<td class="num">${num(i.reorder_level)}</td>` : ""}
      <td class="num">${num(i.predicted_total_demand, 1)}</td>
      <td class="num">${i.days_of_cover === null ? "-" : num(i.days_of_cover, 1)}</td>
      <td class="num"><b>${num(i.additional_stock_required)}</b></td>
      <td class="num">${money(i.order_cost)}</td></tr>`).join("");
    return `<table><thead>${head}</thead><tbody>${rows}</tbody></table>`;
  }

  return { api, toast, esc, num, money, longDate, dateTime, badge, chart, productSelect, busy, itemsTable,
           COLORS, STATUS_HELP, modelName, MODEL_HELP, featureName, TREND, FIELD_NAMES };
})();
