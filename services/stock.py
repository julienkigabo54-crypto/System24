"""Stock-in / stock-out movements and the inventory history they produce."""
from datetime import date, datetime

from pymongo import ReturnDocument

from .errors import ApiError, clean_int, clean_product_id, label, require_json

PUBLIC = {"_id": 0}


def record_movement(db, payload, kind):
    """kind is 'in' or 'out'. Quantity changes atomically; a withdrawal larger
    than the available stock is rejected."""
    payload = require_json(payload)
    pid = clean_product_id(payload.get("product_id"))
    qty = clean_int(payload.get("quantity"), "quantity", minimum=1)
    now = datetime.now().replace(microsecond=0).isoformat()

    if kind == "in":
        product = db.products.find_one_and_update(
            {"product_id": pid},
            {"$inc": {"quantity": qty}, "$set": {"updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if not product:
            raise ApiError(f"Product '{pid}' was not found.", 404)
    else:
        # the quantity >= qty condition makes the check and the update one atomic step
        product = db.products.find_one_and_update(
            {"product_id": pid, "quantity": {"$gte": qty}},
            {"$inc": {"quantity": -qty}, "$set": {"updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if not product:
            existing = db.products.find_one({"product_id": pid})
            if not existing:
                raise ApiError(f"Product '{pid}' was not found.", 404)
            raise ApiError(
                f"Insufficient stock: you asked to remove {qty} units but only {existing['quantity']} are available.", 409,
                {"requested": qty, "available": existing["quantity"]},
            )

    db.inventory_history.update_one(
        {"product_id": pid, "date": date.today().isoformat()},
        {"$inc": {"stock_in": qty if kind == "in" else 0,
                  "stock_out": qty if kind == "out" else 0,
                  "demand": qty if kind == "out" else 0},
         "$set": {"closing_stock": product["quantity"]}},
        upsert=True,
    )
    return {
        "product_id": pid,
        "movement": "stock-in" if kind == "in" else "stock-out",
        "quantity": qty,
        "new_quantity": product["quantity"],
        "date": date.today().isoformat(),
    }


def get_history(db, product_id=None, start=None, end=None, limit=500):
    query = {}
    if product_id:
        query["product_id"] = str(product_id).upper()
    date_filter = {}
    for key, value, op in (("start", start, "$gte"), ("end", end, "$lte")):
        if value:
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                raise ApiError(f"{label(key)} must be a valid date.", 400)
            date_filter[op] = value
    if date_filter:
        query["date"] = date_filter
    limit = clean_int(limit, "limit", minimum=1, maximum=5000)
    rows = list(db.inventory_history.find(query, PUBLIC).sort("date", -1).limit(limit))
    for r in rows:
        for k in ("stock_in", "stock_out", "demand", "closing_stock"):
            r.setdefault(k, None)
    return rows
