"""Stock requirement, status classification, recommendations, dashboard and analytics."""
import math
from datetime import datetime

import numpy as np
import pandas as pd

from . import ml
from . import preprocessing as prep
from .errors import ApiError, clean_int, clean_product_id
from .products import get_product, list_products

STATUS_PRIORITY = {"Critical": 1, "Low Stock": 2, "OK": 3, "Overstock": 4}


# --------------------------------------------------------------------------
# Business rules
# --------------------------------------------------------------------------
def classify_status(stock, avg_daily, horizon_total, reorder_level, cfg):
    """Critical   : out of stock, or will run out before a supplier could deliver
                    (stock < demand expected during the lead time)
       Low Stock  : at or below the reorder level
       Overstock  : more than OVERSTOCK_FACTOR x the demand of the planning window,
                    plus the reorder level as a safety buffer
       OK         : everything else"""
    lead_demand = avg_daily * cfg["LEAD_TIME_DAYS"]
    if stock <= 0 or stock < lead_demand:
        return "Critical"
    if stock <= reorder_level:
        return "Low Stock"
    if stock > cfg["OVERSTOCK_FACTOR"] * horizon_total + reorder_level:
        return "Overstock"
    return "OK"


def stock_requirement(stock, horizon_total, reorder_level):
    """Target stock = predicted demand of the window + reorder level (safety buffer).
    Additional stock = target - current stock, never below zero."""
    target = horizon_total + reorder_level
    return target, max(0, math.ceil(round(target - stock, 6)))


def recommendation_text(status, additional, cover_days, days):
    cover = "no sales are expected" if cover_days is None else f"enough for about {cover_days:.0f} days of sales"
    if status == "Critical":
        return f"Urgent: order {additional} units now. The stock is likely to run out before a new delivery can arrive ({cover})."
    if status == "Low Stock":
        return f"Order {additional} units soon. The stock has reached the reorder level ({cover})."
    if status == "Overstock":
        return f"Do not order more. You have far more than the next {days} days need ({cover}). Consider a sale or discount."
    if additional > 0:
        return f"Stock is fine for now, but order {additional} units to be ready for the next {days} days."
    return f"No action needed ({cover})."


def build_item(product, fc, days, cfg):
    total = round(float(sum(fc["values"])), 2)
    avg = total / days
    stock = product["quantity"]
    status = classify_status(stock, avg, total, product["reorder_level"], cfg)
    target, additional = stock_requirement(stock, total, product["reorder_level"])
    cover = (stock / avg) if avg > 0 else None
    return {
        "product_id": product["product_id"], "name": product["name"], "category": product["category"],
        "price": product["price"], "current_stock": stock, "reorder_level": product["reorder_level"],
        "days": days, "predicted_total_demand": total, "predicted_avg_daily": round(avg, 2),
        "days_of_cover": None if cover is None else round(cover, 1),
        "target_stock": round(target, 2), "additional_stock_required": additional,
        "order_cost": round(additional * product["price"], 2),
        "status": status, "priority": STATUS_PRIORITY[status],
        "recommendation": recommendation_text(status, additional, cover, days),
        "model": fc["model"],
    }


def analyze_products(db, cfg, days=None, model_name=None, product_ids=None):
    days = days or cfg["FORECAST_HORIZON_DAYS"]
    products = list_products(db)
    if product_ids:
        products = [p for p in products if p["product_id"] in product_ids]
    if not products:
        return []
    fc = ml.forecast(db, cfg, [p["product_id"] for p in products], days, model_name, allow_baseline=True)
    items = [build_item(p, fc[p["product_id"]], days, cfg) for p in products]
    items.sort(key=lambda i: (i["priority"], -i["additional_stock_required"], i["product_id"]))
    return items


def parse_days(value, cfg):
    return clean_int(value if value not in (None, "") else cfg["FORECAST_HORIZON_DAYS"], "days",
                     minimum=1, maximum=cfg["MAX_FORECAST_DAYS"])


# --------------------------------------------------------------------------
# Single-product prediction (stored)
# --------------------------------------------------------------------------
def predict_product(db, cfg, payload):
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object.", 400)
    pid = clean_product_id(payload.get("product_id"))
    days = parse_days(payload.get("days"), cfg)
    model_name = payload.get("model") or None
    product = get_product(db, pid)
    fc = ml.forecast(db, cfg, [pid], days, model_name, allow_baseline=False)[pid]
    item = build_item(product, fc, days, cfg)
    daily = [{"date": d, "predicted_demand": v} for d, v in zip(fc["dates"], fc["values"])]
    doc = {
        "product_id": pid, "prediction_date": fc["dates"][0], "days_ahead": days,
        "predicted_demand": item["predicted_total_demand"], "daily": daily,
        "current_stock": item["current_stock"],
        "additional_stock_required": item["additional_stock_required"],
        "status": item["status"], "model": fc["model"],
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
    }
    db.predictions.insert_one(dict(doc))
    return {**item, "daily": daily}


def list_predictions(db, product_id=None, limit=50):
    query = {"product_id": product_id.upper()} if product_id else {}
    return list(db.predictions.find(query, {"_id": 0, "daily": 0}).sort("created_at", -1).limit(int(limit)))


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
def dashboard(db, cfg, days=None):
    days = days or cfg["FORECAST_HORIZON_DAYS"]
    items = analyze_products(db, cfg, days)
    meta = ml.read_metadata(cfg)
    counts = {s: 0 for s in STATUS_PRIORITY}
    for i in items:
        counts[i["status"]] += 1
    return {
        "days": days,
        "total_products": len(items),
        "total_units": int(sum(i["current_stock"] for i in items)),
        "inventory_value": round(sum(i["current_stock"] * i["price"] for i in items), 2),
        "status_counts": counts,
        "critical_count": counts["Critical"], "low_stock_count": counts["Low Stock"],
        "total_predicted_demand": round(sum(i["predicted_total_demand"] for i in items), 2),
        "total_recommended_units": int(sum(i["additional_stock_required"] for i in items)),
        "total_recommended_cost": round(sum(i["order_cost"] for i in items), 2),
        "model_trained": meta is not None,
        "model_in_use": items[0]["model"] if items else None,
        "alerts": [i for i in items if i["status"] in ("Critical", "Low Stock")],
        "recommendations": [i for i in items if i["additional_stock_required"] > 0][:10],
        "items": items,
    }


# --------------------------------------------------------------------------
# Analytics (statistics, trends, charts)
# --------------------------------------------------------------------------
def _clean_history(db, today=None):
    return prep.completed_days_only(prep.clean_history(prep.load_history_raw(db)), today)


def demand_series(db, cfg, product_id, history_days=60, days=14, model_name=None):
    pid = clean_product_id(product_id)
    product = get_product(db, pid)
    history_days = clean_int(history_days, "history_days", minimum=7, maximum=730)
    days = parse_days(days, cfg)
    clean = _clean_history(db)
    g = clean[clean["product_id"] == pid].sort_values("date").tail(history_days)
    fc = ml.forecast(db, cfg, [pid], days, model_name, allow_baseline=True)[pid]
    return {
        "product_id": pid, "name": product["name"], "model": fc["model"],
        "history": {"dates": [d.date().isoformat() for d in g["date"]],
                    "demand": [float(v) for v in g["demand"]]},
        "forecast": {"dates": fc["dates"], "demand": fc["values"]},
    }


def statistics(db, window=90):
    clean = _clean_history(db)
    products = {p["product_id"]: p for p in list_products(db)}
    rows = []
    if not clean.empty:
        recent = clean[clean["date"] > clean["date"].max() - pd.Timedelta(days=window)]
        for pid, g in recent.groupby("product_id"):
            if pid not in products:
                continue
            d = g.sort_values("date")["demand"].to_numpy(dtype=float)
            slope = float(np.polyfit(np.arange(len(d)), d, 1)[0]) if len(d) > 2 else 0.0
            mean = float(d.mean())
            rows.append({
                "product_id": pid, "name": products[pid]["name"], "category": products[pid]["category"],
                "total_demand": float(d.sum()), "mean_daily": round(mean, 2), "std_daily": round(float(d.std()), 2),
                "max_daily": float(d.max()), "variability": round(float(d.std() / mean), 2) if mean > 0 else None,
                "trend_per_day": round(slope, 3),
                # change over the window relative to the average: >10% up or down counts as a trend
                "trend": ("rising" if mean > 0 and slope * (len(d) - 1) / mean > 0.10 else
                          "falling" if mean > 0 and slope * (len(d) - 1) / mean < -0.10 else "stable"),
            })
    rows.sort(key=lambda r: -r["total_demand"])
    return {"window_days": window, "products": rows}


def trends(db):
    clean = _clean_history(db)
    products = {p["product_id"]: p for p in list_products(db)}
    if clean.empty:
        return {"monthly": {"labels": [], "demand": []}, "weekday": {"labels": [], "avg_demand": []},
                "category": {"labels": [], "demand": []}, "top_products": []}
    clean = clean[clean["product_id"].isin(products)]
    m = clean.groupby(clean["date"].dt.to_period("M"))["demand"].sum()
    wd = clean.groupby(clean["date"].dt.weekday)["demand"].sum() / clean.groupby(clean["date"].dt.weekday)["date"].nunique()
    recent = clean[clean["date"] > clean["date"].max() - pd.Timedelta(days=90)].copy()
    recent["category"] = recent["product_id"].map(lambda p: products[p]["category"])
    cat = recent.groupby("category")["demand"].sum().sort_values(ascending=False)
    top = recent.groupby("product_id")["demand"].sum().sort_values(ascending=False).head(5)
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return {
        "monthly": {"labels": [p.strftime("%B %Y") for p in m.index], "demand": [round(float(v), 1) for v in m.values]},
        "weekday": {"labels": [names[i] for i in wd.index], "avg_demand": [round(float(v), 1) for v in wd.values]},
        "category": {"labels": list(cat.index), "demand": [round(float(v), 1) for v in cat.values]},
        "top_products": [{"product_id": p, "name": products[p]["name"], "demand_90d": round(float(v), 1)}
                         for p, v in top.items()],
    }


def inventory_value_by_category(db):
    totals = {}
    for p in list_products(db):
        totals[p["category"]] = totals.get(p["category"], 0) + p["quantity"] * p["price"]
    labels = sorted(totals, key=lambda k: -totals[k])
    return {"labels": labels, "value": [round(totals[k], 2) for k in labels]}
