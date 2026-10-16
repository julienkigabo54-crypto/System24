const { api, esc, num, toast, chart, busy, modelName, MODEL_HELP, featureName, FIELD_NAMES, dateTime } = App;
const $ = (id) => document.getElementById(id);

const METRICS = [
  { key: "mae", name: "Mean Absolute Error", better: "lower", help: "On average, a prediction is wrong by this many units per product per day." },
  { key: "mse", name: "Mean Squared Error", better: "lower", help: "Like the average error, but big mistakes count extra. It is not in units, so use it only to compare models." },
  { key: "rmse", name: "Root Mean Squared Error", better: "lower", help: "The mean squared error turned back into units. It is higher than the average error when there are some big mistakes." },
  { key: "r2", name: "R-squared score", better: "higher", help: "How much of the ups and downs in sales the model explains. 1 is perfect. 0 is no better than always guessing the average." },
];

async function loadQuality() {
  const q = await api("/data/quality");
  const empty = Object.entries(q.missing_values).map(([k, v]) => `${FIELD_NAMES[k] || k}: ${v}`).join(", ") || "None";
  $("quality").innerHTML = `<table class="key-value"><tbody>
    <tr><td>Records (one for each product on each day)</td><td class="num">${num(q.rows)}</td></tr>
    <tr><td>Products</td><td class="num">${num(q.products)}</td></tr>
    <tr><td>Period covered</td><td class="num">${esc(q.first_date || "-")} to ${esc(q.last_date || "-")}</td></tr>
    <tr><td>Repeated records</td><td class="num">${num(q.duplicate_rows)}</td></tr>
    <tr><td>Empty fields</td><td class="num">${esc(empty)}</td></tr>
    <tr><td>Days with no record</td><td class="num">${num(q.missing_days)}</td></tr></tbody></table>`;
}

function renderRetrain(r) {
  if (!r || !r.previous || !r.previous.metrics) { $("retrainResult").innerHTML = ""; return; }
  const p = r.previous.metrics, n = r.metrics[r.active_model];
  $("retrainResult").innerHTML = `<div class="notice">The model was trained again using ${num(r.n_rows)} records (before: ${num(r.previous.n_rows)}). The Root Mean Squared Error changed from ${num(p.rmse, 3)} to <b>${num(n.rmse, 3)}</b>, and the R-squared score from ${num(p.r2, 3)} to <b>${num(n.r2, 3)}</b>.</div>`;
}

function showMethodHelp() { $("methodHelp").textContent = MODEL_HELP[$("active").value] || ""; }

async function load() {
  const s = await api("/ml/status");
  await loadQuality();
  if (!s.trained) {
    $("notice").innerHTML = '<div class="notice warn">The model has not been trained yet. Press <b>Train the prediction model</b> to begin. It only takes a few seconds.</div>';
    $("meta").textContent = "";
    $("metrics").innerHTML = '<div class="empty">Train the model to see how accurate it is.</div>';
    $("runs").innerHTML = '<div class="empty">The model has not been trained yet.</div>';
    showMethodHelp();
    return;
  }
  $("notice").innerHTML = "";
  $("active").value = s.active_model;
  showMethodHelp();
  $("meta").innerHTML = `Last trained on <b>${esc(dateTime(s.trained_at))}</b>, using ${num(s.history_days)} days of sales records for ${num(s.n_products)} products (${esc(s.history_start)} to ${esc(s.history_end)}). Predictions currently use <b>${esc(modelName(s.active_model))}</b>.`;

  const names = Object.keys(s.metrics);
  const best = {};
  METRICS.forEach((m) => { best[m.key] = names.reduce((a, b) => ((m.better === "higher" ? s.metrics[b][m.key] > s.metrics[a][m.key] : s.metrics[b][m.key] < s.metrics[a][m.key]) ? b : a)); });
  $("metrics").innerHTML = `<table><thead><tr><th>Score</th>` +
    names.map((n) => `<th class="num">${esc(modelName(n))}${n === s.active_model ? " (in use)" : ""}</th>`).join("") + `<th>What it means</th></tr></thead><tbody>` +
    METRICS.map((m) => `<tr><td><b>${m.name}</b><br><small>${m.better === "lower" ? "Lower is better" : "Higher is better"}</small></td>` +
      names.map((n) => `<td class="num ${best[m.key] === n ? "best" : ""}">${num(s.metrics[n][m.key], 4)}</td>`).join("") +
      `<td style="white-space:normal;min-width:260px;color:var(--muted)">${m.help}</td></tr>`).join("") +
    `<tr><td></td>` + names.map((n) => `<td class="num">${n === s.active_model ? "" : `<button class="small" data-use="${n}">Use this method</button>`}</td>`).join("") + `<td></td></tr></tbody></table>`;

  const c = s.test_curve;
  if (c) chart("curve", { type: "line", data: { labels: c.dates, datasets: [
    { label: "Real sales", data: c.actual, borderColor: "#0e6b62", backgroundColor: "#0e6b62", pointRadius: 0, borderWidth: 2.5 },
    { label: "Predicted by Linear Regression", data: c.linear_regression, borderColor: "#d9660a", backgroundColor: "#d9660a", borderDash: [7, 5], pointRadius: 0, borderWidth: 2 },
    { label: "Predicted by Random Forest", data: c.random_forest, borderColor: "#5a42b5", backgroundColor: "#5a42b5", borderDash: [2, 4], pointRadius: 0, borderWidth: 2 }] },
    options: { plugins: { legend: { position: "bottom" } }, scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { title: { display: true, text: "Units sold per day (all products)" } } }, interaction: { mode: "index", intersect: false } } });

  const imp = s.feature_importance[s.active_model];
  const feats = Object.keys(imp).sort((a, b) => Math.abs(imp[b]) - Math.abs(imp[a]));
  const total = feats.reduce((t, f) => t + Math.abs(imp[f]), 0) || 1;
  chart("importance", { type: "bar", data: { labels: feats.map(featureName), datasets: [{ label: "Share of the model's attention", data: feats.map((f) => Math.round((Math.abs(imp[f]) / total) * 1000) / 10), backgroundColor: "#5a42b5", borderRadius: 4 }] },
    options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { title: { display: true, text: "Share of the model's attention (percent)" } } } } });

  const TRIGGER = { train: "First training", retrain: "Trained again" };
  $("runs").innerHTML = s.runs.length ? `<table><thead><tr><th>Date and time</th><th>What happened</th><th class="num">Records used</th><th>Records up to</th><th class="num">Linear Regression: Root Mean Squared Error</th><th class="num">Linear Regression: R-squared</th><th class="num">Random Forest: Root Mean Squared Error</th><th class="num">Random Forest: R-squared</th></tr></thead><tbody>` +
    s.runs.map((r) => `<tr><td>${esc(dateTime(r.run_at))}</td><td>${esc(TRIGGER[r.trigger] || r.trigger)}</td><td class="num">${num(r.n_rows)}</td><td style="white-space:nowrap">${esc(r.history_end)}</td><td class="num">${num(r.metrics.linear_regression.rmse, 3)}</td><td class="num">${num(r.metrics.linear_regression.r2, 3)}</td><td class="num">${num(r.metrics.random_forest.rmse, 3)}</td><td class="num">${num(r.metrics.random_forest.r2, 3)}</td></tr>`).join("") + "</tbody></table>"
    : '<div class="empty">The model has not been trained yet.</div>';
}

async function run(path, btn) {
  await busy(btn, async () => {
    btn.textContent = "Training. Please wait...";
    const r = await api(path, { json: { active_model: $("active").value } });
    const m = r.metrics[r.active_model];
    toast(`Training is finished. ${modelName(r.active_model)}: Root Mean Squared Error ${num(m.rmse, 2)}, R-squared score ${num(m.r2, 2)}.`);
    await load();
    renderRetrain(r);
  });
}
$("btnTrain").addEventListener("click", (e) => run("/ml/train", e.currentTarget));
$("btnRetrain").addEventListener("click", (e) => run("/ml/retrain", e.currentTarget));
$("active").addEventListener("change", showMethodHelp);
$("btnClean").addEventListener("click", (e) => busy(e.currentTarget, async () => {
  const r = await api("/data/clean", { method: "POST" });
  toast(`Cleaning is finished. ${num(r.duplicates_removed)} repeated records were removed and the empty fields were filled in.`);
  await loadQuality();
}));
$("metrics").addEventListener("click", (e) => {
  const b = e.target.closest("[data-use]");
  if (b) busy(b, async () => { await api("/ml/active", { json: { model: b.dataset.use } }); toast("The prediction method was changed."); await load(); });
});
load().catch((e) => toast(e.message, "error"));
