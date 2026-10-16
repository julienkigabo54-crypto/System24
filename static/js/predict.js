const { api, esc, num, badge, toast, chart, productSelect, busy, modelName, longDate, dateTime } = App;
const $ = (id) => document.getElementById(id);

async function loadStored() {
  const rows = await api("/predictions?limit=15");
  $("stored").innerHTML = rows.length ? `<table><thead><tr><th>Made on</th><th>Product code</th><th class="num">Days ahead</th><th class="num">Expected sales</th><th class="num">In stock at that time</th><th class="num">Extra units needed</th><th>Status</th><th>Prediction method</th></tr></thead><tbody>` +
    rows.map((r) => `<tr><td>${esc(dateTime(r.created_at))}</td><td>${esc(r.product_id)}</td><td class="num">${r.days_ahead}</td><td class="num">${num(r.predicted_demand, 1)}</td><td class="num">${num(r.current_stock)}</td><td class="num">${num(r.additional_stock_required)}</td><td>${badge(r.status)}</td><td>${esc(modelName(r.model))}</td></tr>`).join("") + "</tbody></table>"
    : '<div class="empty">No predictions have been saved yet. Make your first one above.</div>';
}

$("form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  await busy(ev.submitter, async () => {
    const pid = $("product").value;
    const r = await api("/predict", { json: { product_id: pid, days: $("days").value, model: $("model").value } });
    $("result").hidden = false;
    $("reco").innerHTML = `<b>${esc(r.name)}:</b> ${esc(r.recommendation)} The target stock is ${num(r.target_stock)} units (the expected sales plus the reorder level of ${num(r.reorder_level)} units).`;
    $("kpis").innerHTML = [
      [`Expected sales in ${r.days} days`, num(r.predicted_total_demand, 1), "units in total"],
      ["Expected sales per day", num(r.predicted_avg_daily, 1), "units on an average day"],
      ["In stock now", num(r.current_stock), "units"],
      ["Extra units to order", num(r.additional_stock_required), "to reach the target stock"],
      ["Status", badge(r.status), "hover over it to see what it means"],
      ["Days the stock will last", r.days_of_cover === null ? "-" : num(r.days_of_cover, 1), "at the expected rate of sales"],
    ].map(([n, v, note]) => `<div class="figure"><div class="name">${n}</div><div class="number">${v}</div><div class="note">${note}</div></div>`).join("");
    $("daily").innerHTML = `<table><thead><tr><th>Date</th><th class="num">Expected sales</th></tr></thead><tbody>` +
      r.daily.map((d) => `<tr><td>${esc(longDate(d.date))}</td><td class="num">${num(d.predicted_demand, 1)}</td></tr>`).join("") +
      `<tr><td><b>Total for ${r.days} days</b></td><td class="num"><b>${num(r.predicted_total_demand, 1)}</b></td></tr></tbody></table>`;
    const s = await api(`/analytics/demand-series?product_id=${encodeURIComponent(pid)}&history_days=45&days=${r.days}&model=${encodeURIComponent($("model").value)}`);
    const labels = [...s.history.dates, ...s.forecast.dates];
    const last = s.history.dates.length - 1;
    chart("chart", { type: "line", data: { labels, datasets: [
      { label: "Past sales", data: [...s.history.demand, ...s.forecast.dates.map(() => null)], borderColor: "#0e6b62", backgroundColor: "#0e6b62", pointRadius: 0, tension: 0.25, borderWidth: 2.5 },
      { label: "Predicted sales", data: [...s.history.dates.map((_, i) => (i === last ? s.history.demand[i] : null)), ...s.forecast.demand], borderColor: "#d9660a", backgroundColor: "#d9660a", borderDash: [7, 5], pointRadius: 2, tension: 0.25, borderWidth: 2.5 }] },
      options: { plugins: { legend: { position: "bottom" } }, scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { title: { display: true, text: "Units sold per day" } } }, interaction: { mode: "index", intersect: false } } });
    toast("The prediction was made and saved.");
    await loadStored();
    $("result").scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

productSelect($("product")).then(loadStored).catch((e) => toast(e.message, "error"));
