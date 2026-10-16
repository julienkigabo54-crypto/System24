const { api, esc, num, money, badge, chart, COLORS, STATUS_HELP, toast, itemsTable } = App;
const $ = (id) => document.getElementById(id);
const plural = (n, one, many) => `${num(n)} ${n === 1 ? one : many}`;

function summary(d) {
  const crit = d.critical_count, low = d.low_stock_count;
  let sentence, cls = "";
  if (crit > 0) {
    sentence = `${plural(crit, "product needs", "products need")} to be ordered urgently.`;
  } else if (low > 0) {
    sentence = `${plural(low, "product is", "products are")} running low and should be ordered soon.`;
  } else {
    sentence = `Every product has enough stock for the next ${d.days} days.`;
    cls = "good";
  }
  const detail = d.total_recommended_units > 0
    ? `To be ready for the next ${d.days} days, order about ${plural(d.total_recommended_units, "unit", "units")}. This would cost about ${money(d.total_recommended_cost)}.`
    : "No extra stock needs to be ordered at the moment.";
  $("summary").innerHTML = `<div class="summary ${cls}"><p>${esc(sentence)}<small>${esc(detail)}</small></p><a class="btn" href="/recommendations">See what to order</a></div>`;
}

function figures(d) {
  const items = [
    ["Products", num(d.total_products), "different products registered", ""],
    ["Units in stock", num(d.total_units), "all products together", ""],
    ["Value of the stock", money(d.inventory_value), "units multiplied by price", ""],
    [`Expected sales`, num(d.total_predicted_demand), `units in the next ${d.days} days`, ""],
    ["Critical products", num(d.critical_count), "need ordering urgently", d.critical_count ? "alert" : ""],
    ["Products running low", num(d.low_stock_count), "have reached the reorder level", d.low_stock_count ? "warn" : ""],
    ["Units to order", num(d.total_recommended_units), "recommended in total", ""],
    ["Cost of ordering", money(d.total_recommended_cost), "estimated, at current prices", ""],
  ];
  $("figures").innerHTML = items.map(([name, number, note, cls]) =>
    `<div class="figure ${cls}"><div class="name">${name}</div><div class="number">${number}</div><div class="note">${note}</div></div>`).join("");
}

async function load() {
  const days = $("days").value;
  try {
    const [d, value] = await Promise.all([api(`/dashboard?days=${days}`), api("/analytics/inventory-value")]);
    $("notice").innerHTML = d.model_trained ? "" :
      '<div class="notice warn">The prediction model has not been trained yet, so these figures use a simple average of recent sales. To get better predictions, open <a href="/model">Prediction Model</a> and press <b>Train the prediction model</b>.</div>';
    summary(d);
    figures(d);

    const labels = Object.keys(d.status_counts);
    chart("statusChart", { type: "doughnut", data: { labels, datasets: [{ data: labels.map((l) => d.status_counts[l]), backgroundColor: labels.map((l) => COLORS[l]), borderWidth: 2, borderColor: "#fff" }] },
      options: { cutout: "62%", plugins: { legend: { display: false } } } });
    $("legend").innerHTML = labels.map((l) =>
      `<div class="legend-row"><div>${badge(l)}</div><span class="words"><b>${plural(d.status_counts[l], "product", "products")}.</b> ${esc(STATUS_HELP[l])}</span></div>`).join("");

    const top = [...d.items].sort((a, b) => b.additional_stock_required - a.additional_stock_required).slice(0, 8);
    chart("orderChart", { type: "bar", data: { labels: top.map((i) => i.name), datasets: [{ label: "Units to order", data: top.map((i) => i.additional_stock_required), backgroundColor: top.map((i) => COLORS[i.status]), borderRadius: 6 }] },
      options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { title: { display: true, text: "Units to order" } } } } });

    const byDemand = [...d.items].sort((a, b) => b.predicted_total_demand - a.predicted_total_demand).slice(0, 10);
    chart("demandChart", { type: "bar", data: { labels: byDemand.map((i) => i.name), datasets: [
      { label: `Expected sales (next ${d.days} days)`, data: byDemand.map((i) => i.predicted_total_demand), backgroundColor: "#0e6b62", borderRadius: 4 },
      { label: "Stock in hand", data: byDemand.map((i) => i.current_stock), backgroundColor: "#a9d6d0", borderRadius: 4 }] },
      options: { plugins: { legend: { position: "bottom" } }, scales: { x: { ticks: { maxRotation: 45, minRotation: 30 } }, y: { title: { display: true, text: "Units" } } } } });

    chart("valueChart", { type: "bar", data: { labels: value.labels, datasets: [{ label: "Value of the stock", data: value.value, backgroundColor: "#0e6b62", borderRadius: 6 }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { title: { display: true, text: "Value in US dollars" }, ticks: { callback: (v) => "$" + Number(v).toLocaleString() } } } } });

    $("alerts").innerHTML = d.alerts.length ? itemsTable(d.alerts, { days: d.days }) : '<div class="empty">No product is critical or running low. Well done.</div>';
    $("orders").innerHTML = d.recommendations.length ? itemsTable(d.recommendations, { days: d.days }) : '<div class="empty">No extra stock needs to be ordered.</div>';
  } catch (e) { toast(e.message, "error"); }
}
$("days").addEventListener("change", load);
load();
