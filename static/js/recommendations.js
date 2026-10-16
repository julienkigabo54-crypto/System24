const { api, esc, num, toast, itemsTable } = App;
const $ = (id) => document.getElementById(id);
let items = [];

function render() {
  const f = $("filter").value;
  const shown = items.filter((i) => !f || (f === "order" ? i.additional_stock_required > 0 : i.status === f));
  $("rows").innerHTML = shown.length ? itemsTable(shown, { days: $("days").value, showReorder: true, showCategory: true })
    : '<div class="empty">No products match this choice.</div>';
}

async function load() {
  const days = $("days").value;
  $("csv").href = `/api/reports/inventory.csv?days=${days}`;
  try {
    const r = await api(`/recommendations?days=${days}`);
    items = r.items;
    const crit = items.filter((i) => i.status === "Critical").length, low = items.filter((i) => i.status === "Low Stock").length;
    $("alertBox").innerHTML = crit || low
      ? `<div class="notice warn"><b>${num(crit)}</b> ${crit === 1 ? "product is" : "products are"} critical and <b>${num(low)}</b> ${low === 1 ? "product is" : "products are"} low on stock. These need your attention first.</div>` : "";
    render();
  } catch (e) { toast(e.message, "error"); }
}
$("days").addEventListener("change", load);
$("filter").addEventListener("change", render);
load();
