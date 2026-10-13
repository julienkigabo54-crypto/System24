const { api, esc, num, money, badge, chart, COLORS, toast } = App;

function table(items, columns) {
  if (!items.length) return '<div class="empty">Nothing to show.</div>';
  return `<table><thead><tr>${columns.map((c) => `<th class="${c.num ? "num" : ""}">${c.label}</th>`).join("")}</tr></thead><tbody>` +
    items.map((i) => `<tr>${columns.map((c) => `<td class="${c.num ? "num" : ""} ${c.wrap ? "wrap" : ""}">${c.render(i)}</td>`).join("")}</tr>`).join("") +
    "</tbody></table>";
}

const COLS = [
  { label: "Product", render: (i) => `<b>${esc(i.name)}</b><br><small>${esc(i.product_id)}</small>` },
  { label: "Status", render: (i) => badge(i.status) },
  { label: "Stock", num: true, render: (i) => num(i.current_stock) },
  { label: "Reorder lvl", num: true, render: (i) => num(i.reorder_level) },
  { label: "Predicted demand", num: true, render: (i) => num(i.predicted_total_demand, 1) },
  { label: "Days of cover", num: true, render: (i) => (i.days_of_cover === null ? "–" : num(i.days_of_cover, 1)) },
  { label: "Order qty", num: true, render: (i) => `<b>${num(i.additional_stock_required)}</b>` },
  { label: "Order cost", num: true, render: (i) => money(i.order_cost) },
  { label: "Recommendation", wrap: true, render: (i) => esc(i.recommendation) },
];

async function load() {
  const days = document.getElementById("days").value;
  try {
    const [d, value] = await Promise.all([api(`/dashboard?days=${days}`), api("/analytics/inventory-value")]);
    document.getElementById("notice").innerHTML = d.model_trained ? "" :
      '<div class="notice warn">No trained model yet. Figures use a simple moving average. Train the model on the <a href="/model">ML Model</a> page for machine-learning predictions.</div>';
    document.getElementById("kpis").innerHTML = [
      ["Total products", num(d.total_products), ""],
      ["Units in stock", num(d.total_units), ""],
      ["Inventory value", money(d.inventory_value), ""],
      ["Critical products", num(d.critical_count), "critical"],
      ["Low-stock products", num(d.low_stock_count), "low"],
      [`Predicted demand (${d.days}d)`, num(d.total_predicted_demand), ""],
      ["Recommended order units", num(d.total_recommended_units), ""],
      ["Estimated order cost", money(d.total_recommended_cost), ""],
    ].map(([l, v, c]) => `<div class="card kpi ${c}"><div class="label">${l}</div><div class="value">${v}</div></div>`).join("");

    const labels = Object.keys(d.status_counts);
    chart("statusChart", { type: "doughnut", data: { labels, datasets: [{ data: labels.map((l) => d.status_counts[l]), backgroundColor: labels.map((l) => COLORS[l]) }] }, options: { plugins: { legend: { position: "bottom" } } } });

    const top = [...d.items].sort((a, b) => b.additional_stock_required - a.additional_stock_required).slice(0, 8);
    chart("orderChart", { type: "bar", data: { labels: top.map((i) => i.name), datasets: [{ label: "Units to order", data: top.map((i) => i.additional_stock_required), backgroundColor: top.map((i) => COLORS[i.status]) }] }, options: { indexAxis: "y", plugins: { legend: { display: false } } } });

    const byDemand = [...d.items].sort((a, b) => b.predicted_total_demand - a.predicted_total_demand).slice(0, 10);
    chart("demandChart", { type: "bar", data: { labels: byDemand.map((i) => i.name), datasets: [{ label: "Predicted demand", data: byDemand.map((i) => i.predicted_total_demand), backgroundColor: "#1f5eff" }, { label: "Current stock", data: byDemand.map((i) => i.current_stock), backgroundColor: "#9db8ff" }] }, options: { scales: { x: { ticks: { maxRotation: 50, minRotation: 30 } } } } });

    chart("valueChart", { type: "bar", data: { labels: value.labels, datasets: [{ label: "Inventory value", data: value.value, backgroundColor: "#1f5eff" }] }, options: { plugins: { legend: { display: false } }, scales: { y: { ticks: { callback: (v) => "$" + Number(v).toLocaleString() } } } } });

    document.getElementById("alerts").innerHTML = table(d.alerts, COLS);
    document.getElementById("orders").innerHTML = table(d.recommendations, COLS);
  } catch (e) { toast(e.message, "error"); }
}
document.getElementById("days").addEventListener("change", load);
load();
