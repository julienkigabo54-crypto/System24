const { api, esc, num, money, badge, toast, chart, productSelect, busy } = App;
const $ = (id) => document.getElementById(id);

async function loadStored() {
  const rows = await api("/predictions?limit=15");
  $("stored").innerHTML = rows.length ? `<table><thead><tr><th>Created</th><th>Product</th><th class="num">Days</th><th class="num">Predicted demand</th><th class="num">Stock then</th><th class="num">Extra needed</th><th>Status</th><th>Model</th></tr></thead><tbody>` +
    rows.map((r) => `<tr><td>${esc(r.created_at.replace("T", " "))}</td><td>${esc(r.product_id)}</td><td class="num">${r.days_ahead}</td><td class="num">${num(r.predicted_demand, 1)}</td><td class="num">${num(r.current_stock)}</td><td class="num">${num(r.additional_stock_required)}</td><td>${badge(r.status)}</td><td>${esc(r.model)}</td></tr>`).join("") + "</tbody></table>"
    : '<div class="empty">No predictions stored yet.</div>';
}

$("form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  await busy(ev.submitter, async () => {
    const pid = $("product").value;
    const r = await api("/predict", { json: { product_id: pid, days: $("days").value, model: $("model").value } });
    $("result").hidden = false;
    $("kpis").innerHTML = [
      ["Total predicted demand", num(r.predicted_total_demand, 1)],
      ["Average per day", num(r.predicted_avg_daily, 1)],
      ["Current stock", num(r.current_stock)],
      ["Additional stock required", num(r.additional_stock_required)],
      ["Status", badge(r.status)],
      ["Days of cover", r.days_of_cover === null ? "–" : num(r.days_of_cover, 1)],
    ].map(([l, v]) => `<div class="card kpi"><div class="label">${l}</div><div class="value">${v}</div></div>`).join("");
    $("reco").textContent = r.recommendation + `  (Target stock ${num(r.target_stock, 0)} = predicted demand + reorder level ${num(r.reorder_level)}.)`;
    $("daily").innerHTML = `<table><thead><tr><th>Date</th><th>Day</th><th class="num">Predicted demand</th></tr></thead><tbody>` +
      r.daily.map((d) => `<tr><td>${esc(d.date)}</td><td>${new Date(d.date + "T12:00").toLocaleDateString(undefined, { weekday: "short" })}</td><td class="num">${num(d.predicted_demand, 1)}</td></tr>`).join("") +
      `<tr><td colspan="2"><b>Total</b></td><td class="num"><b>${num(r.predicted_total_demand, 1)}</b></td></tr></tbody></table>`;
    const s = await api(`/analytics/demand-series?product_id=${encodeURIComponent(pid)}&history_days=45&days=${r.days}&model=${encodeURIComponent($("model").value)}`);
    const labels = [...s.history.dates, ...s.forecast.dates];
    chart("chart", { type: "line", data: { labels, datasets: [
      { label: "Historical", data: [...s.history.demand, ...s.forecast.dates.map(() => null)], borderColor: "#1f5eff", pointRadius: 0, tension: 0.2 },
      { label: "Predicted", data: [...s.history.dates.map((_, i) => (i === s.history.dates.length - 1 ? s.history.demand[i] : null)), ...s.forecast.demand], borderColor: "#ea580c", borderDash: [6, 4], pointRadius: 2, tension: 0.2 }] },
      options: { scales: { x: { ticks: { maxTicksLimit: 8 } } }, interaction: { mode: "index", intersect: false } } });
    toast("Prediction stored");
    await loadStored();
    $("result").scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

productSelect($("product")).then(loadStored).catch((e) => toast(e.message, "error"));
