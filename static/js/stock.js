const { api, esc, num, toast, busy } = App;
const $ = (id) => document.getElementById(id);
let products = [];

function showCurrent() {
  const p = products.find((x) => x.product_id === $("product").value);
  const box = $("current");
  if (!p) { box.hidden = true; return; }
  box.hidden = false;
  box.innerHTML = `In stock now: <b>${num(p.quantity)} units</b>. Reorder level: ${num(p.reorder_level)} units.`;
}

async function loadRecent() {
  const pid = $("product").value;
  if (!pid) { $("recent").innerHTML = '<div class="empty">There are no products yet. Add one on the Products page.</div>'; return; }
  const rows = await api(`/history?product_id=${encodeURIComponent(pid)}&limit=10`);
  $("recent").innerHTML = rows.length ? `<table><thead><tr><th>Date</th><th class="num">Stock added</th><th class="num">Units sold</th><th class="num">Stock left at the end of the day</th></tr></thead><tbody>` +
    rows.map((r) => `<tr><td>${esc(r.date)}</td><td class="num">${num(r.stock_in)}</td><td class="num">${num(r.stock_out)}</td><td class="num">${num(r.closing_stock)}</td></tr>`).join("") + "</tbody></table>"
    : '<div class="empty">No records yet for this product.</div>';
}

async function refresh() {
  products = await api("/products");
  const cur = $("product").value;
  $("product").innerHTML = products.map((p) => `<option value="${esc(p.product_id)}" ${p.product_id === cur ? "selected" : ""}>${esc(p.name)} (${esc(p.product_id)})</option>`).join("");
  showCurrent();
  await loadRecent();
}

async function move(kind, btn) {
  await busy(btn, async () => {
    const r = await api("/stock/" + kind, { json: { product_id: $("product").value, quantity: $("qty").value } });
    const what = kind === "in" ? "added to" : "removed from";
    toast(`${r.quantity} units were ${what} the stock. There are now ${r.new_quantity} units in stock.`);
    await refresh();
  });
}
$("btnIn").addEventListener("click", (e) => move("in", e.currentTarget));
$("btnOut").addEventListener("click", (e) => move("out", e.currentTarget));
$("product").addEventListener("change", () => { showCurrent(); loadRecent().catch((e) => toast(e.message, "error")); });
refresh().catch((e) => toast(e.message, "error"));
