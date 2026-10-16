const { api, esc, num, toast, chart, productSelect, busy } = App;
const $ = (id) => document.getElementById(id);

async function load() {
  const p = new URLSearchParams({ limit: $("limit").value });
  if ($("product").value) p.set("product_id", $("product").value);
  if ($("start").value) p.set("start", $("start").value);
  if ($("end").value) p.set("end", $("end").value);
  const rows = await api("/history?" + p);
  $("rows").innerHTML = rows.length ? `<table><thead><tr><th>Date</th><th>Product code</th><th class="num">Stock added</th><th class="num">Units sold</th><th class="num">Stock left at the end of the day</th></tr></thead><tbody>` +
    rows.map((r) => `<tr><td>${esc(r.date)}</td><td>${esc(r.product_id)}</td><td class="num">${num(r.stock_in)}</td><td class="num">${num(r.demand)}</td><td class="num">${num(r.closing_stock)}</td></tr>`).join("") + "</tbody></table>"
    : '<div class="empty">No records were found. Try a different product or a wider range of dates.</div>';
  const single = $("product").value && rows.length > 1;
  $("chartCard").hidden = !single;
  if (single) {
    const asc = [...rows].reverse();
    chart("chart", { type: "line", data: { labels: asc.map((r) => r.date), datasets: [
      { label: "Stock left at the end of the day", data: asc.map((r) => r.closing_stock), borderColor: "#0e6b62", backgroundColor: "#0e6b62", pointRadius: 0, tension: 0.25, borderWidth: 2.5 },
      { label: "Units sold", data: asc.map((r) => r.demand), borderColor: "#d9660a", backgroundColor: "#d9660a", pointRadius: 0, tension: 0.25, borderWidth: 2 }] },
      options: { plugins: { legend: { position: "bottom" } }, scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { title: { display: true, text: "Units" } } }, interaction: { mode: "index", intersect: false } } });
  }
}

$("apply").addEventListener("click", (e) => busy(e.currentTarget, load));
productSelect($("product"), { includeAll: true }).then(load).catch((e) => toast(e.message, "error"));
