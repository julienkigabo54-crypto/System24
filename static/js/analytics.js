const { api, esc, num, toast, chart, productSelect, modelName, TREND } = App;
const $ = (id) => document.getElementById(id);
const TEAL = "#0e6b62", ORANGE = "#d9660a";

async function series() {
  const pid = $("product").value;
  if (!pid) return;
  const days = $("days").value || 14;
  $("png").href = `/api/reports/demand-chart/${encodeURIComponent(pid)}.png`;
  try {
    const s = await api(`/analytics/demand-series?product_id=${encodeURIComponent(pid)}&history_days=90&days=${days}`);
    const labels = [...s.history.dates, ...s.forecast.dates];
    const last = s.history.dates.length - 1;
    chart("seriesChart", { type: "line", data: { labels, datasets: [
      { label: "Past sales", data: [...s.history.demand, ...s.forecast.dates.map(() => null)], borderColor: TEAL, backgroundColor: TEAL, pointRadius: 0, tension: 0.25, borderWidth: 2.5 },
      { label: `Predicted sales (${modelName(s.model)})`, data: [...s.history.dates.map((_, i) => (i === last ? s.history.demand[i] : null)), ...s.forecast.demand], borderColor: ORANGE, backgroundColor: ORANGE, borderDash: [7, 5], pointRadius: 2, tension: 0.25, borderWidth: 2.5 }] },
      options: { plugins: { legend: { position: "bottom" } }, scales: { x: { ticks: { maxTicksLimit: 10 } }, y: { title: { display: true, text: "Units sold per day" } } }, interaction: { mode: "index", intersect: false } } });
  } catch (e) { toast(e.message, "error"); }
}

async function load() {
  await productSelect($("product"));
  series();
  const [t, v, st] = await Promise.all([api("/analytics/trends"), api("/analytics/inventory-value"), api("/analytics/statistics")]);
  const noLegend = { legend: { display: false } };
  chart("monthChart", { type: "bar", data: { labels: t.monthly.labels, datasets: [{ label: "Units sold", data: t.monthly.demand, backgroundColor: TEAL, borderRadius: 6 }] }, options: { plugins: noLegend, scales: { y: { title: { display: true, text: "Units sold" } } } } });
  chart("weekChart", { type: "bar", data: { labels: t.weekday.labels, datasets: [{ label: "Average units sold per day", data: t.weekday.avg_demand, backgroundColor: "#2f9e8f", borderRadius: 6 }] }, options: { plugins: noLegend, scales: { y: { title: { display: true, text: "Average units sold per day" } } } } });
  chart("catChart", { type: "doughnut", data: { labels: t.category.labels, datasets: [{ data: t.category.demand, backgroundColor: ["#0e6b62", "#d9660a", "#5a42b5", "#e0a100", "#2f7fc1", "#b42818"], borderWidth: 2, borderColor: "#fff" }] }, options: { cutout: "55%", plugins: { legend: { position: "bottom" } } } });
  chart("valueChart", { type: "bar", data: { labels: v.labels, datasets: [{ label: "Value of the stock", data: v.value, backgroundColor: "#5a42b5", borderRadius: 6 }] }, options: { plugins: noLegend, scales: { y: { title: { display: true, text: "Value in US dollars" }, ticks: { callback: (x) => "$" + Number(x).toLocaleString() } } } } });
  $("stats").innerHTML = st.products.length ? `<table><thead><tr><th>Product</th><th>Category</th><th class="num">Total units sold</th><th class="num">Average sold per day</th><th class="num">Day-to-day variation</th><th class="num">Highest in one day</th><th class="num">Unevenness of sales</th><th>Direction</th></tr></thead><tbody>` +
    st.products.map((r) => `<tr><td><b>${esc(r.name)}</b> <small>${esc(r.product_id)}</small></td><td>${esc(r.category)}</td><td class="num">${num(r.total_demand)}</td><td class="num">${num(r.mean_daily, 1)}</td><td class="num">${num(r.std_daily, 1)}</td><td class="num">${num(r.max_daily)}</td><td class="num">${r.variability === null ? "-" : num(r.variability, 2)}</td><td>${esc(TREND[r.trend] || r.trend)}</td></tr>`).join("") + "</tbody></table>"
    : '<div class="empty">There are no sales records yet.</div>';
}
$("product").addEventListener("change", series);
$("days").addEventListener("change", series);
load().catch((e) => toast(e.message, "error"));
