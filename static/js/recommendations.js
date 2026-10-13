const { api, esc, num, money, badge, toast } = App;
const $ = (id) => document.getElementById(id);
let items = [];

function render() {
  const f = $("filter").value;
  const shown = items.filter((i) => !f || (f === "order" ? i.additional_stock_required > 0 : i.status === f));
  $("rows").innerHTML = shown.length ? `<table><thead><tr><th>Priority</th><th>Product</th><th>Status</th><th class="num">Stock</th><th class="num">Reorder lvl</th><th class="num">Predicted demand</th><th class="num">Days of cover</th><th class="num">Order qty</th><th class="num">Cost</th><th>Recommendation</th></tr></thead><tbody>` +
    shown.map((i) => `<tr><td>${i.priority}</td><td><b>${esc(i.name)}</b><br><small>${esc(i.product_id)} · ${esc(i.category)}</small></td><td>${badge(i.status)}</td><td class="num">${num(i.current_stock)}</td><td class="num">${num(i.reorder_level)}</td><td class="num">${num(i.predicted_total_demand, 1)}</td><td class="num">${i.days_of_cover === null ? "–" : num(i.days_of_cover, 1)}</td><td class="num"><b>${num(i.additional_stock_required)}</b></td><td class="num">${money(i.order_cost)}</td><td class="wrap">${esc(i.recommendation)}</td></tr>`).join("") + "</tbody></table>"
    : '<div class="empty">No products match.</div>';
}

async function load() {
  const days = $("days").value;
  $("csv").href = `/api/reports/inventory.csv?days=${days}`;
  try {
    const r = await api(`/recommendations?days=${days}`);
    items = r.items;
    const crit = items.filter((i) => i.status === "Critical").length, low = items.filter((i) => i.status === "Low Stock").length;
    $("alertBox").innerHTML = crit || low ? `<div class="notice warn"><b>${crit}</b> critical and <b>${low}</b> low-stock product(s) need attention.</div>` : "";
    render();
  } catch (e) { toast(e.message, "error"); }
}
$("days").addEventListener("change", load);
$("filter").addEventListener("change", render);
load();
