const { api, esc, num, money, toast, chart, productSelect } = App;
const $ = (id) => document.getElementById(id);
const BLUE = "#1f5eff";

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
      { label: "Historical demand", data: [...s.history.demand, ...s.forecast.dates.map(() => null)], borderColor: BLUE, pointRadius: 0, tension: 0.2 },
      { label: `Predicted demand (${s.model.replace("_", " ")})`, data: [...s.history.dates.map((_, i) => (i === last ? s.history.demand[i] : null)), ...s.forecast.demand], borderColor: "#ea580c", borderDash: [6, 4], pointRadius: 2, tension: 0.2 }] },
      options: { scales: { x: { ticks: { maxTicksLimit: 10 } } }, interaction: { mode: "index", intersect: false } } });
  } catch (e) { toast(e.message, "error"); }
}

async function load() {
  await productSelect($("product"));
  series();
  const [t, v, st] = await Promise.all([api("/analytics/trends"), api("/analytics/inventory-value"), api("/analytics/statistics")]);
  chart("monthChart", { type: "bar", data: { labels: t.monthly.labels, datasets: [{ label: "Units sold", data: t.monthly.demand, backgroundColor: BLUE }] }, options: { plugins: { legend: { display: false } } } });
  chart("weekChart", { type: "bar", data: { labels: t.weekday.labels, datasets: [{ label: "Avg units / day", data: t.weekday.avg_demand, backgroundColor: "#12a150" }] }, options: { plugins: { legend: { display: false } } } });
  chart("catChart", { type: "doughnut", data: { labels: t.category.labels, datasets: [{ data: t.category.demand, backgroundColor: ["#1f5eff", "#12a150", "#e8920c", "#7a52e0", "#d92d20", "#0ea5b7"] }] }, options: { plugins: { legend: { position: "bottom" } } } });
  chart("valueChart", { type: "bar", data: { labels: v.labels, datasets: [{ label: "Value", data: v.value, backgroundColor: "#7a52e0" }] }, options: { plugins: { legend: { display: false } }, scales: { y: { ticks: { callback: (x) => "$" + Number(x).toLocaleString() } } } } });
  const arrow = { rising: "▲ rising", falling: "▼ falling", stable: "● stable" };
  $("stats").innerHTML = st.products.length ? `<table><thead><tr><th>Product</th><th>Category</th><th class="num">Total demand</th><th class="num">Mean / day</th><th class="num">Std dev</th><th class="num">Peak day</th><th class="num">Variability</th><th>Trend</th></tr></thead><tbody>` +
    st.products.map((r) => `<tr><td><b>${esc(r.name)}</b><br><small>${esc(r.product_id)}</small></td><td>${esc(r.category)}</td><td class="num">${num(r.total_demand)}</td><td class="num">${num(r.mean_daily, 1)}</td><td class="num">${num(r.std_daily, 1)}</td><td class="num">${num(r.max_daily)}</td><td class="num">${r.variability === null ? "–" : num(r.variability, 2)}</td><td>${arrow[r.trend]}</td></tr>`).join("") + "</tbody></table>"
    : '<div class="empty">No history yet.</div>';
}
$("product").addEventListener("change", series);
$("days").addEventListener("change", series);
load().catch((e) => toast(e.message, "error"));
