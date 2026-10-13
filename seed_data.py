"""Generates SAMPLE data so the system can be demonstrated end to end.

    python seed_data.py              # 15 products, 365 days of history (resets the DB)
    python seed_data.py --days 540   # longer history
    python seed_data.py --no-dirty   # skip the deliberate data-quality problems

The history is synthetic (weekday pattern + seasonality + trend + random noise) and
is NOT real sales data. By default a few duplicate rows, missing values and missing
days are injected on purpose, so the data-cleaning step has something to fix.
The current stock of the products is set up so that all four statuses
(Critical, Low Stock, OK, Overstock) appear on the dashboard.
"""
import argparse
import math
import random
from datetime import date, timedelta

import numpy as np

# name, category, price, average daily demand, weekend factor, trend % per year, scenario
PRODUCTS = [
    ("Wireless Mouse",        "Electronics", 18.50, 14, 0.8,  12, "ok"),
    ("USB-C Cable 1m",        "Electronics",  6.99, 30, 0.9,   5, "low"),
    ("Bluetooth Speaker",     "Electronics", 45.00,  6, 1.4,  25, "critical"),
    ("Phone Charger 20W",     "Electronics", 15.00, 18, 1.0,   8, "ok"),
    ("A4 Paper Ream",         "Stationery",   4.80, 40, 0.3,   0, "ok"),
    ("Ballpoint Pens (10)",   "Stationery",   3.20, 35, 0.4,  -5, "over"),
    ("Notebook A5",           "Stationery",   2.50, 28, 0.5,  10, "low"),
    ("Rice 5kg",              "Groceries",   12.00, 22, 1.3,   2, "ok"),
    ("Cooking Oil 2L",        "Groceries",    7.80, 17, 1.2,   4, "critical"),
    ("Sugar 1kg",             "Groceries",    1.90, 45, 1.1,   0, "ok"),
    ("Bottled Water 12-pack", "Groceries",    5.50, 25, 1.5,  30, "ok"),
    ("Laundry Detergent 3L",  "Household",   11.20, 12, 1.1,   3, "over"),
    ("Dish Soap 750ml",       "Household",    2.90, 20, 1.0,   0, "ok"),
    ("LED Bulb 9W",           "Household",    3.50, 16, 0.9, -10, "low"),
    ("Hand Sanitizer 500ml",  "Household",    4.10,  9, 0.9, -20, "ok"),
]


def simulate_product(rng, days, base, weekend, trend_pct, reorder, end_day, scenario):
    """Returns a list of (date, stock_in, stock_out, demand, closing) rows."""
    start = end_day - timedelta(days=days - 1)
    demand = []
    for i in range(days):
        d = start + timedelta(days=i)
        season = 1 + 0.18 * math.sin(2 * math.pi * (d.timetuple().tm_yday - 60) / 365)
        trend = 1 + (trend_pct / 100) * (i / 365)
        wk = weekend if d.weekday() >= 5 else 1.0
        mean = base * season * trend * wk
        value = max(0, int(round(rng.normal(mean, math.sqrt(mean) * 1.1))))
        if rng.random() < 0.02:               # occasional promotion spike
            value = int(value * rng.uniform(1.5, 2.2))
        demand.append(value)

    order_up_to = int(base * 16)
    stock = order_up_to
    rows = []
    window = 10                                # last days: behaviour depends on the scenario
    for i, d_ in enumerate(demand):
        d = start + timedelta(days=i)
        stock_in = 0
        in_window = i >= days - window
        if scenario in ("low", "critical") and in_window:
            if i == days - window:             # one last delivery, then none: stock drains
                target = int(base * (0.3 if scenario == "critical" else 5.0))
                needed = target + sum(demand[days - window:]) - stock
                stock_in = max(0, needed)
        elif stock - d_ < reorder:
            stock_in = max(order_up_to - stock + d_, 0)
        stock += stock_in
        if stock < d_:                         # emergency delivery so demand is never lost
            extra = d_ - stock
            stock_in += extra
            stock += extra
        stock -= d_
        if scenario == "over" and i == days - 1:
            boost = int(base * 40)
            stock_in += boost
            stock += boost
        rows.append((d, int(stock_in), int(d_), int(d_), int(stock)))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-dirty", action="store_true", help="do not inject duplicates / missing values")
    parser.add_argument("--keep", action="store_true", help="do not delete existing data first")
    args = parser.parse_args()

    from app import create_app
    app = create_app()
    run(app, args.days, args.seed, not args.no_dirty, args.keep)


def run(app, days=365, seed=42, dirty=True, keep=False):
    from db import get_db

    rng = np.random.default_rng(seed)
    py_rng = random.Random(seed)
    end_day = date.today() - timedelta(days=1)       # history ends yesterday
    with app.app_context():
        db = get_db()
        if not keep:
            for name in ("products", "inventory_history", "predictions", "model_runs"):
                db[name].delete_many({})
        docs, history = [], []
        for n, (name, cat, price, base, wk, trend, scenario) in enumerate(PRODUCTS, start=1):
            pid = f"P{n:04d}"
            reorder = int(base * 7)                  # about one week of demand
            rows = simulate_product(rng, days, base, wk, trend, reorder, end_day, scenario)
            quantity = rows[-1][4]
            docs.append({"product_id": pid, "name": name, "category": cat, "price": price,
                         "quantity": quantity, "reorder_level": reorder,
                         "created_at": rows[0][0].isoformat() + "T08:00:00",
                         "updated_at": end_day.isoformat() + "T18:00:00"})
            for d, s_in, s_out, dem, close in rows:
                history.append({"product_id": pid, "date": d.isoformat(), "stock_in": s_in,
                                "stock_out": s_out, "demand": dem, "closing_stock": close})
        injected = {"duplicates": 0, "missing_values": 0, "missing_days": 0}
        if dirty:
            n = len(history)
            drop = set(py_rng.sample(range(n), 8))                      # days with no record
            history = [h for i, h in enumerate(history) if i not in drop]
            injected["missing_days"] = len(drop)
            for h in py_rng.sample(history, 12):                        # missing numeric values
                h[py_rng.choice(["demand", "stock_in", "closing_stock"])] = None
                injected["missing_values"] += 1
            for h in py_rng.sample(history, 10):                        # exact duplicate rows
                history.append(dict(h))
                injected["duplicates"] += 1
        db.products.insert_many(docs)
        db.inventory_history.insert_many(history)
        print(f"Inserted {len(docs)} products and {len(history)} history rows "
              f"({days} days up to {end_day}). Injected problems: {injected}")
    return docs


if __name__ == "__main__":
    main()
