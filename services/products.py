"""Product registration, search, update and deletion."""
import re
from datetime import datetime, date

from pymongo.errors import DuplicateKeyError

from .errors import (ApiError, clean_float, clean_int, clean_product_id, clean_text,
                     require_json)

PUBLIC = {"_id": 0}


def _now():
    return datetime.now().replace(microsecond=0).isoformat()


def next_product_id(db):
    """P0001, P0002, ... one higher than the largest existing P-number."""
    highest = 0
    for doc in db.products.find({}, {"product_id": 1, "_id": 0}):
        m = re.fullmatch(r"P(\d+)", doc["product_id"])
        if m:
            highest = max(highest, int(m.group(1)))
    return f"P{highest + 1:04d}"


def create_product(db, payload):
    payload = require_json(payload)
    product_id = payload.get("product_id")
    product_id = clean_product_id(product_id) if product_id not in (None, "") else next_product_id(db)
    quantity = clean_int(payload.get("quantity", 0), "quantity")
    doc = {
        "product_id": product_id,
        "name": clean_text(payload.get("name"), "name", 100),
        "category": clean_text(payload.get("category"), "category", 50),
        "price": clean_float(payload.get("price"), "price"),
        "quantity": quantity,
        "reorder_level": clean_int(payload.get("reorder_level", 0), "reorder_level"),
        "created_at": _now(),
        "updated_at": _now(),
    }
    try:
        db.products.insert_one(doc)
    except DuplicateKeyError:
        raise ApiError(f"Product code '{product_id}' already exists. Please choose a different code.", 409)
    if quantity > 0:  # opening stock is part of the inventory history
        db.inventory_history.update_one(
            {"product_id": product_id, "date": date.today().isoformat()},
            {"$inc": {"stock_in": quantity, "stock_out": 0, "demand": 0},
             "$set": {"closing_stock": quantity}},
            upsert=True,
        )
    doc.pop("_id", None)
    return doc


def get_product(db, product_id):
    doc = db.products.find_one({"product_id": str(product_id).upper()}, PUBLIC)
    if not doc:
        raise ApiError(f"Product '{product_id}' was not found.", 404)
    return doc


def list_products(db, q=None, category=None, limit=1000):
    query = {}
    if q:
        pattern = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"product_id": pattern}, {"name": pattern}, {"category": pattern}]
    if category:
        query["category"] = category
    return list(db.products.find(query, PUBLIC).sort("product_id", 1).limit(int(limit)))


def categories(db):
    return sorted({d["category"] for d in db.products.find({}, {"category": 1, "_id": 0})})


def update_product(db, product_id, payload):
    payload = require_json(payload)
    get_product(db, product_id)  # 404 if missing
    if "quantity" in payload:
        raise ApiError("The quantity cannot be edited here. Use the Add or Remove Stock page instead.", 400)
    if "product_id" in payload and str(payload["product_id"]).upper() != str(product_id).upper():
        raise ApiError("The product code cannot be changed.", 400)
    changes = {}
    if "name" in payload:
        changes["name"] = clean_text(payload["name"], "name", 100)
    if "category" in payload:
        changes["category"] = clean_text(payload["category"], "category", 50)
    if "price" in payload:
        changes["price"] = clean_float(payload["price"], "price")
    if "reorder_level" in payload:
        changes["reorder_level"] = clean_int(payload["reorder_level"], "reorder_level")
    if not changes:
        raise ApiError("Nothing to update. You can change the name, category, price or reorder level.", 400)
    changes["updated_at"] = _now()
    db.products.update_one({"product_id": str(product_id).upper()}, {"$set": changes})
    return get_product(db, product_id)


def delete_product(db, product_id):
    pid = str(product_id).upper()
    get_product(db, pid)
    db.products.delete_one({"product_id": pid})
    # remove the product's own history and predictions too, so no orphan data is left
    h = db.inventory_history.delete_many({"product_id": pid})
    p = db.predictions.delete_many({"product_id": pid})
    return {"deleted": pid, "history_rows_removed": h.deleted_count,
            "predictions_removed": p.deleted_count}
