"""Data quality report, data cleaning and feature engineering for the ML model."""
from datetime import date, timedelta

import numpy as np
import pandas as pd

NUMERIC = ["stock_in", "stock_out", "demand", "closing_stock"]
FEATURES = ["dow_sin", "dow_cos", "month_sin", "month_cos", "is_weekend",
            "t", "lag_1", "lag_7", "roll_7", "roll_28"]


# --------------------------------------------------------------------------
# Loading and quality report
# --------------------------------------------------------------------------
def load_history_raw(db, product_id=None):
    query = {"product_id": product_id} if product_id else {}
    rows = list(db.inventory_history.find(query, {"_id": 0}))
    cols = ["product_id", "date"] + NUMERIC
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    return df[cols]


def quality_report(db):
    """Counts the problems that cleaning will fix."""
    df = load_history_raw(db)
    if df.empty:
        return {"rows": 0, "products": 0, "duplicate_rows": 0, "missing_values": {},
                "negative_values": 0, "missing_days": 0, "first_date": None, "last_date": None}
    dup = int(df.duplicated(subset=["product_id", "date"], keep="first").sum())
    missing = {c: int(df[c].isna().sum()) for c in ["product_id", "date"] + NUMERIC}
    negatives = int((df[NUMERIC].apply(pd.to_numeric, errors="coerce") < 0).sum().sum())
    clean = clean_history(df, fill_calendar=False)
    gaps = 0
    for _, g in clean.groupby("product_id"):
        span = (g["date"].max() - g["date"].min()).days + 1
        gaps += span - len(g)
    return {
        "rows": int(len(df)),
        "products": int(df["product_id"].nunique()),
        "duplicate_rows": dup,
        "missing_values": {k: v for k, v in missing.items() if v},
        "negative_values": negatives,
        "missing_days": int(gaps),
        "first_date": str(df["date"].dropna().min()),
        "last_date": str(df["date"].dropna().max()),
    }


# --------------------------------------------------------------------------
# Cleaning
# --------------------------------------------------------------------------
def clean_history(df, fill_calendar=True, end_date=None):
    """Returns one tidy row per product per day.

    * drops rows without a product or a valid date
    * removes duplicate (product, date) rows
    * converts numbers, sets negative values to 0
    * fills missing values (demand falls back to stock_out, stock flows to 0,
      closing stock is carried forward)
    * (optional) inserts the days that have no record, with zero demand
    """
    cols = ["product_id", "date"] + NUMERIC
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["product_id", "date"])
    df["date"] = df["date"].dt.normalize()
    df = df.drop_duplicates(subset=["product_id", "date"], keep="last")
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce")
        df.loc[df[c] < 0, c] = 0
    df = df.sort_values(["product_id", "date"]).reset_index(drop=True)
    df["stock_in"] = df["stock_in"].fillna(0)
    df["stock_out"] = df["stock_out"].fillna(0)
    df["demand"] = df["demand"].fillna(df["stock_out"])
    df["closing_stock"] = df.groupby("product_id")["closing_stock"].ffill().fillna(0)

    if fill_calendar:
        end = pd.Timestamp(end_date) if end_date is not None else df["date"].max()
        parts = []
        for pid, g in df.groupby("product_id"):
            idx = pd.date_range(g["date"].min(), max(end, g["date"].max()), freq="D")
            g = g.set_index("date").reindex(idx)
            g.index.name = "date"
            g["product_id"] = pid
            g[["stock_in", "stock_out", "demand"]] = g[["stock_in", "stock_out", "demand"]].fillna(0)
            g["closing_stock"] = g["closing_stock"].ffill()
            parts.append(g.reset_index())
        df = pd.concat(parts, ignore_index=True)
    return df[cols].reset_index(drop=True)


def clean_database(db):
    """Permanently repairs the stored history: removes duplicate rows and fills
    missing numeric fields. Returns what was changed."""
    before = quality_report(db)
    seen, removed = set(), 0
    for doc in db.inventory_history.find({}).sort([("product_id", 1), ("date", 1)]):
        key = (doc.get("product_id"), doc.get("date"))
        if None in key or key in seen:
            db.inventory_history.delete_one({"_id": doc["_id"]})
            removed += 1
            continue
        seen.add(key)
        fix = {}
        for c in ("stock_in", "stock_out"):
            if doc.get(c) is None or doc.get(c) < 0:
                fix[c] = 0
        if doc.get("demand") is None or doc.get("demand") < 0:
            fix["demand"] = doc.get("stock_out") if (doc.get("stock_out") or 0) > 0 else 0
        if doc.get("closing_stock") is None or doc.get("closing_stock") < 0:
            fix["closing_stock"] = 0
        if fix:
            db.inventory_history.update_one({"_id": doc["_id"]}, {"$set": fix})
    after = quality_report(db)
    return {"duplicates_removed": removed, "before": before, "after": after}


# --------------------------------------------------------------------------
# Feature engineering (shared by training and forecasting)
# --------------------------------------------------------------------------
def calendar_features(d, origin):
    """Features that depend only on the date. d: pandas Timestamp / datetime."""
    dow, month = d.weekday(), d.month
    return {
        "dow_sin": np.sin(2 * np.pi * dow / 7), "dow_cos": np.cos(2 * np.pi * dow / 7),
        "month_sin": np.sin(2 * np.pi * month / 12), "month_cos": np.cos(2 * np.pi * month / 12),
        "is_weekend": 1.0 if dow >= 5 else 0.0,
        "t": float((pd.Timestamp(d) - pd.Timestamp(origin)).days),
    }


def lag_features(history):
    """history: list of daily demand values (oldest first, most recent last).
    Defines the lag features exactly as build_training_frame does."""
    h = np.asarray(history, dtype=float)
    lag_1 = h[-1] if len(h) >= 1 else 0.0
    lag_7 = h[-7] if len(h) >= 7 else (h.mean() if len(h) else 0.0)
    roll_7 = h[-7:].mean() if len(h) else 0.0
    roll_28 = h[-28:].mean() if len(h) else 0.0
    return {"lag_1": lag_1, "lag_7": lag_7, "roll_7": roll_7, "roll_28": roll_28}


def build_training_frame(clean, origin=None):
    """Adds the features to every product-day and drops rows without enough past."""
    if clean.empty:
        return clean.assign(**{f: [] for f in FEATURES}), pd.Timestamp(date.today())
    origin = pd.Timestamp(origin) if origin is not None else clean["date"].min()
    parts = []
    for pid, g in clean.groupby("product_id"):
        g = g.sort_values("date").copy()
        d = g["demand"]
        g["lag_1"] = d.shift(1)
        g["lag_7"] = d.shift(7)
        g["roll_7"] = d.shift(1).rolling(7, min_periods=7).mean()
        g["roll_28"] = d.shift(1).rolling(28, min_periods=7).mean()
        parts.append(g)
    df = pd.concat(parts, ignore_index=True)
    dates = df["date"]
    dow = dates.dt.weekday
    month = dates.dt.month
    df["dow_sin"] = np.sin(2 * np.pi * dow / 7)
    df["dow_cos"] = np.cos(2 * np.pi * dow / 7)
    df["month_sin"] = np.sin(2 * np.pi * month / 12)
    df["month_cos"] = np.cos(2 * np.pi * month / 12)
    df["is_weekend"] = (dow >= 5).astype(float)
    df["t"] = (dates - origin).dt.days.astype(float)
    df = df.dropna(subset=["lag_1", "lag_7", "roll_7", "roll_28"])
    return df.reset_index(drop=True), origin


def completed_days_only(clean, today=None):
    """Today's record is still being written, so it is not used for learning."""
    today = pd.Timestamp(today or date.today())
    return clean[clean["date"] < today].reset_index(drop=True)
