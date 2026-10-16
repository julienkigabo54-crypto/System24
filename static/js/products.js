const { api, esc, num, money, toast, busy } = App;
let editing = null;
const $ = (id) => document.getElementById(id);

async function loadCategories() {
  const cats = await api("/products/categories");
  $("cats").innerHTML = cats.map((c) => `<option value="${esc(c)}">`).join("");
  const cur = $("catFilter").value;
  $("catFilter").innerHTML = '<option value="">All categories</option>' + cats.map((c) => `<option ${c === cur ? "selected" : ""}>${esc(c)}</option>`).join("");
}

async function loadList() {
  const params = new URLSearchParams();
  if ($("q").value.trim()) params.set("q", $("q").value.trim());
  if ($("catFilter").value) params.set("category", $("catFilter").value);
  try {
    const items = await api("/products?" + params);
    $("list").innerHTML = items.length ? `<table><thead><tr><th>Code</th><th>Product name</th><th>Category</th><th class="num">Price per unit</th><th class="num">In stock</th><th class="num">Reorder level</th><th class="num">Actions</th></tr></thead><tbody>` +
      items.map((p) => `<tr><td>${esc(p.product_id)}</td><td><b>${esc(p.name)}</b></td><td>${esc(p.category)}</td><td class="num">${money(p.price)}</td><td class="num">${num(p.quantity)}</td><td class="num">${num(p.reorder_level)}</td>
        <td class="num"><div class="button-row" style="justify-content:flex-end"><button class="small" data-edit="${esc(p.product_id)}">Change</button><button class="small danger" data-del="${esc(p.product_id)}">Delete</button></div></td></tr>`).join("") + "</tbody></table>"
      : '<div class="empty">No products match. Add a product above, or clear the search.</div>';
    window._products = Object.fromEntries(items.map((p) => [p.product_id, p]));
  } catch (e) { toast(e.message, "error"); }
}

$("addForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  await busy(ev.submitter, async () => {
    const body = { name: $("f_name").value, category: $("f_cat").value, price: $("f_price").value,
      quantity: $("f_qty").value || 0, reorder_level: $("f_reorder").value || 0 };
    if ($("f_id").value.trim()) body.product_id = $("f_id").value.trim();
    const p = await api("/products", { json: body });
    toast(`${p.name} was added with the code ${p.product_id}.`);
    $("addForm").reset(); $("f_qty").value = 0; $("f_reorder").value = 0;
    await Promise.all([loadCategories(), loadList()]);
  });
});

$("list").addEventListener("click", async (ev) => {
  const edit = ev.target.closest("[data-edit]"), del = ev.target.closest("[data-del]");
  if (edit) {
    const p = window._products[edit.dataset.edit]; editing = p.product_id;
    $("e_idLabel").textContent = p.name;
    $("e_name").value = p.name; $("e_cat").value = p.category; $("e_price").value = p.price; $("e_reorder").value = p.reorder_level;
    $("editDlg").showModal();
  } else if (del) {
    const p = window._products[del.dataset.del];
    if (!confirm(`Delete "${p.name}" (${p.product_id})?\n\nIts stock history and saved predictions will also be deleted. This cannot be undone.`)) return;
    await busy(del, async () => {
      await api("/products/" + encodeURIComponent(p.product_id), { method: "DELETE" });
      toast(`${p.name} was deleted.`);
      await Promise.all([loadCategories(), loadList()]);
    });
  }
});

$("e_cancel").addEventListener("click", () => $("editDlg").close());
$("editForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  await busy(ev.submitter, async () => {
    await api("/products/" + encodeURIComponent(editing), { method: "PUT", json: {
      name: $("e_name").value, category: $("e_cat").value, price: $("e_price").value, reorder_level: $("e_reorder").value } });
    $("editDlg").close(); toast("The changes were saved.");
    await Promise.all([loadCategories(), loadList()]);
  });
});

let timer;
$("q").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(loadList, 250); });
$("catFilter").addEventListener("change", loadList);
loadCategories().then(loadList).catch((e) => toast(e.message, "error"));
