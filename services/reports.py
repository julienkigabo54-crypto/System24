"""Downloadable reports: inventory CSV and a Matplotlib demand chart (PNG)."""
import csv
import io

import matplotlib

matplotlib.use("Agg")  # no display needed on a server
import matplotlib.pyplot as plt  # noqa: E402

from . import analysis  # noqa: E402

COLUMNS = [
    ("product_id", "Product code"), ("name", "Product name"), ("category", "Category"),
    ("price", "Price per unit"), ("current_stock", "In stock now"), ("reorder_level", "Reorder level"),
    ("predicted_total_demand", "Expected sales"), ("days_of_cover", "Days the stock will last"),
    ("additional_stock_required", "Units to order"), ("order_cost", "Estimated cost of ordering"),
    ("status", "Status"), ("recommendation", "Advice"),
]


def inventory_csv(db, cfg, days):
    items = analysis.analyze_products(db, cfg, days)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([label for _, label in COLUMNS])
    for i in items:
        w.writerow(["" if i[k] is None else i[k] for k, _ in COLUMNS])
    return buf.getvalue()


def demand_chart_png(db, cfg, product_id, history_days=60, days=14):
    s = analysis.demand_series(db, cfg, product_id, history_days, days)
    fig, ax = plt.subplots(figsize=(9, 3.8), dpi=110)
    ax.plot(s["history"]["dates"], s["history"]["demand"], color="#2563eb", lw=1.6, label="Past sales")
    ax.plot(s["forecast"]["dates"], s["forecast"]["demand"], color="#ea580c", lw=1.8, ls="--", label="Predicted sales")
    ax.set_title(f"{s['name']} ({s['product_id']}): past sales and predicted sales")
    ax.set_ylabel("Units sold per day")
    n = len(s["history"]["dates"]) + len(s["forecast"]["dates"])
    all_dates = s["history"]["dates"] + s["forecast"]["dates"]
    ticks = list(range(0, n, max(1, n // 8)))
    ax.set_xticks([all_dates[i] for i in ticks])
    ax.tick_params(axis="x", rotation=30, labelsize=8)
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()
