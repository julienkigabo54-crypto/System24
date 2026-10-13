const { api, esc, num, toast, chart, productSelect, busy } = App;
const $ = (id) => document.getElementById(id);

async function load() {
  const p = new URLSearchParams({ limit: $("limit").value });
  if ($("product").value) p.set("product_id", $("product").value);
  if ($("start").value) p.set("start", $("start").value);
  if ($("end").value) p.set("end", $("end").value);
  const rows = await api("/history?" + p);
  $("rows").innerHTML = rows.length ? `<table><thead><tr><th>Date</th><th>Product</th><th class="num">Stock in</th><th class="num">Stock out</th><th class="num">Demand</th><th class="num">Closing stock</th></tr></thead><tbody>` +
    rows.map((r) => `<tr><td>${esc(r.date)}</td><td>${esc(r.product_id)}</td><td class="num">${num(r.stock_in)}</td><td class="num">${num(r.stock_out)}</td><td class="num">${num(r.demand)}</td><td class="num">${num(r.closing_stock)}</td></tr>`).join("") + "</tbody></table>"
    : '<div class="empty">No history records match.</div>';
  const single = $("product").value && rows.length > 1;
  $("chartCard").hidden = !single;
  if (single) {
    const asc = [...rows].reverse();
    chart("chart", { type: "line", data: { labels: asc.map((r) => r.date), datasets: [
      { label: "Closing stock", data: asc.map((r) => r.closing_stock), borderColor: "#1f5eff", pointRadius: 0, tension: 0.2 },
      { label: "Demand", data: asc.map((r) => r.demand), borderColor: "#ea580c", pointRadius: 0, tension: 0.2 }] },
      options: { scales: { x: { ticks: { maxTicksLimit: 8 } } }, interaction: { mode: "index", intersect: false } } });
  }
}

$("apply").addEventListener("click", (e) => busy(e.currentTarget, load));
productSelect($("product"), { includeAll: true }).then(load).catch((e) => toast(e.message, "error"));
