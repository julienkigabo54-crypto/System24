const { api, esc, num, toast, chart, busy } = App;
const $ = (id) => document.getElementById(id);
const LABEL = { linear_regression: "Linear Regression", random_forest: "Random Forest" };

async function loadQuality() {
  const q = await api("/data/quality");
  const missing = Object.entries(q.missing_values).map(([k, v]) => `${k}: ${v}`).join(", ") || "none";
  $("quality").innerHTML = `<table><tbody>
    <tr><td>History rows</td><td class="num">${num(q.rows)}</td></tr>
    <tr><td>Products</td><td class="num">${num(q.products)}</td></tr>
    <tr><td>Period</td><td class="num">${esc(q.first_date || "–")} → ${esc(q.last_date || "–")}</td></tr>
    <tr><td>Duplicate rows</td><td class="num">${num(q.duplicate_rows)}</td></tr>
    <tr><td>Missing values</td><td class="num">${esc(missing)}</td></tr>
    <tr><td>Missing days (gaps)</td><td class="num">${num(q.missing_days)}</td></tr></tbody></table>`;
}

function renderRetrain(r) {
  if (!r || !r.previous) { $("retrainResult").innerHTML = ""; return; }
  const p = r.previous.metrics, n = r.metrics[r.active_model];
  $("retrainResult").innerHTML = p ? `<div class="notice">Retrained on ${num(r.n_rows)} rows (was ${num(r.previous.n_rows)}). RMSE ${num(p.rmse, 3)} → <b>${num(n.rmse, 3)}</b>, R² ${num(p.r2, 3)} → <b>${num(n.r2, 3)}</b>.</div>` : "";
}

async function load(result) {
  const s = await api("/ml/status");
  await loadQuality();
  if (!s.trained) {
    $("notice").innerHTML = '<div class="notice warn">No model has been trained yet. Click <b>Train models</b>.</div>';
    $("meta").textContent = ""; $("metrics").innerHTML = '<div class="empty">Train the models to see their scores.</div>';
    $("runs").innerHTML = '<div class="empty">No training runs yet.</div>';
    return;
  }
  $("notice").innerHTML = "";
  $("active").value = s.active_model;
  $("meta").innerHTML = `Last trained <b>${esc(s.trained_at.replace("T", " "))}</b> on ${num(s.history_days)} days of history (${esc(s.history_start)} → ${esc(s.history_end)}), ${num(s.n_rows)} product-days (${num(s.n_train)} train / ${num(s.n_test)} test). Predictions currently use <b>${LABEL[s.active_model]}</b>.`;
  const keys = ["mae", "mse", "rmse", "r2"], names = Object.keys(s.metrics);
  const best = {}; keys.forEach((k) => { best[k] = names.reduce((a, b) => ((k === "r2" ? s.metrics[b][k] > s.metrics[a][k] : s.metrics[b][k] < s.metrics[a][k]) ? b : a)); });
  $("metrics").innerHTML = `<table><thead><tr><th>Model</th><th class="num">MAE</th><th class="num">MSE</th><th class="num">RMSE</th><th class="num">R²</th><th></th></tr></thead><tbody>` +
    names.map((n) => `<tr><td><b>${LABEL[n]}</b>${n === s.active_model ? ' <span class="badge ok">in use</span>' : ""}</td>` +
      keys.map((k) => `<td class="num ${best[k] === n ? "metric-best" : ""}">${num(s.metrics[n][k], 4)}</td>`).join("") +
      `<td class="num">${n === s.active_model ? "" : `<button class="small" data-use="${n}">Use this model</button>`}</td></tr>`).join("") + "</tbody></table>";
  const c = s.test_curve;
  if (c) chart("curve", { type: "line", data: { labels: c.dates, datasets: [
    { label: "Actual", data: c.actual, borderColor: "#1f5eff", pointRadius: 0 },
    { label: "Linear Regression", data: c.linear_regression, borderColor: "#ea580c", borderDash: [5, 4], pointRadius: 0 },
    { label: "Random Forest", data: c.random_forest, borderColor: "#12a150", borderDash: [2, 3], pointRadius: 0 }] },
    options: { scales: { x: { ticks: { maxTicksLimit: 8 } } }, interaction: { mode: "index", intersect: false } } });
  const imp = s.feature_importance[s.active_model];
  const feats = Object.keys(imp).sort((a, b) => Math.abs(imp[b]) - Math.abs(imp[a]));
  chart("importance", { type: "bar", data: { labels: feats, datasets: [{ label: s.active_model === "linear_regression" ? "Coefficient" : "Importance", data: feats.map((f) => imp[f]), backgroundColor: "#7a52e0" }] }, options: { indexAxis: "y", plugins: { legend: { display: false } } } });
  $("runs").innerHTML = s.runs.length ? `<table><thead><tr><th>When</th><th>Type</th><th class="num">Rows</th><th>Data until</th><th class="num">LR RMSE</th><th class="num">LR R²</th><th class="num">RF RMSE</th><th class="num">RF R²</th></tr></thead><tbody>` +
    s.runs.map((r) => `<tr><td>${esc(r.run_at.replace("T", " "))}</td><td>${esc(r.trigger)}</td><td class="num">${num(r.n_rows)}</td><td>${esc(r.history_end)}</td><td class="num">${num(r.metrics.linear_regression.rmse, 3)}</td><td class="num">${num(r.metrics.linear_regression.r2, 3)}</td><td class="num">${num(r.metrics.random_forest.rmse, 3)}</td><td class="num">${num(r.metrics.random_forest.r2, 3)}</td></tr>`).join("") + "</tbody></table>" : "";
}

async function run(path, btn) {
  await busy(btn, async () => {
    btn.textContent = "Training…";
    const r = await api(path, { json: { active_model: $("active").value } });
    toast(`Done. ${LABEL[r.active_model]}: RMSE ${num(r.metrics[r.active_model].rmse, 3)}, R² ${num(r.metrics[r.active_model].r2, 3)}`);
    await load();
    renderRetrain(r);
  });
}
$("btnTrain").addEventListener("click", (e) => run("/ml/train", e.currentTarget));
$("btnRetrain").addEventListener("click", (e) => run("/ml/retrain", e.currentTarget));
$("btnClean").addEventListener("click", (e) => busy(e.currentTarget, async () => {
  const r = await api("/data/clean", { method: "POST" });
  toast(`Removed ${r.duplicates_removed} duplicate rows; missing values fixed.`);
  await loadQuality();
}));
$("metrics").addEventListener("click", (e) => {
  const b = e.target.closest("[data-use]");
  if (b) busy(b, async () => { await api("/ml/active", { json: { model: b.dataset.use } }); toast("Active model changed"); await load(); });
});
load().catch((e) => toast(e.message, "error"));
