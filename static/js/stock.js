const { api, esc, num, toast, busy, productSelect } = App;
const $ = (id) => document.getElementById(id);
let products = [];

function showCurrent() {
  const p = products.find((x) => x.product_id === $("product").value);
  const box = $("current");
  if (!p) { box.hidden = true; return; }
  box.hidden = false;
  box.innerHTML = `Current stock: <b>${num(p.quantity)}</b> units &nbsp;·&nbsp; Reorder level: ${num(p.reorder_level)}`;
}

async function loadRecent() {
  const pid = $("product").value;
  if (!pid) { $("recent").innerHTML = '<div class="empty">No products yet.</div>'; return; }
  const rows = await api(`/history?product_id=${encodeURIComponent(pid)}&limit=10`);
  $("recent").innerHTML = rows.length ? `<table><thead><tr><th>Date</th><th class="num">In</th><th class="num">Out</th><th class="num">Closing</th></tr></thead><tbody>` +
    rows.map((r) => `<tr><td>${esc(r.date)}</td><td class="num">${num(r.stock_in)}</td><td class="num">${num(r.stock_out)}</td><td class="num">${num(r.closing_stock)}</td></tr>`).join("") + "</tbody></table>"
    : '<div class="empty">No history yet.</div>';
}

async function refresh() {
  products = await api("/products");
  const cur = $("product").value;
  $("product").innerHTML = products.map((p) => `<option value="${esc(p.product_id)}" ${p.product_id === cur ? "selected" : ""}>${esc(p.product_id)} – ${esc(p.name)}</option>`).join("");
  showCurrent();
  await loadRecent();
}

async function move(kind, btn) {
  await busy(btn, async () => {
    const r = await api("/stock/" + kind, { json: { product_id: $("product").value, quantity: $("qty").value } });
    toast(`${r.movement}: ${r.quantity} units. New stock: ${r.new_quantity}`);
    await refresh();
  });
}
$("btnIn").addEventListener("click", (e) => move("in", e.currentTarget));
$("btnOut").addEventListener("click", (e) => move("out", e.currentTarget));
$("product").addEventListener("change", () => { showCurrent(); loadRecent().catch((e) => toast(e.message, "error")); });
refresh().catch((e) => toast(e.message, "error"));
