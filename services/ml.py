"""Demand forecasting: training, evaluation, saving, retraining and prediction.

Approach
--------
Every product-day is one training example. The target is that day's demand.
Features are calendar information (weekday, month, weekend, a time trend) and the
product's recent demand (yesterday, 7 days ago, 7- and 28-day averages).

* Linear Regression is the main model (required by the brief).
* Random Forest is trained alongside it for comparison (optional in the brief).
* The newest 20% of dates are held out and used only for the MAE / MSE / RMSE / R2
  scores, so the scores measure how well the model predicts the *future*.
* After scoring, the model is refitted on all data before it is saved.
* To predict several days ahead the model predicts one day, feeds that result back
  in as "yesterday", and repeats (recursive forecasting).
"""
import json
from datetime import date, datetime, timedelta

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from . import preprocessing as prep
from .errors import ApiError

MODEL_LABELS = {"linear_regression": "Linear Regression", "random_forest": "Random Forest"}
_cache = {}


def _new_model(name):
    if name == "linear_regression":
        return LinearRegression()
    if name == "random_forest":
        return RandomForestRegressor(n_estimators=150, min_samples_leaf=2, random_state=42, n_jobs=-1)
    raise ApiError(f"Unknown model '{name}'. Use one of: {', '.join(MODEL_LABELS)}.", 400)


def _paths(cfg):
    d = cfg["MODEL_DIR"]
    d.mkdir(parents=True, exist_ok=True)
    return d, d / "metadata.json"


# --------------------------------------------------------------------------
# Metadata
# --------------------------------------------------------------------------
def read_metadata(cfg):
    _, meta_path = _paths(cfg)
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text())


def set_active_model(cfg, name):
    if name not in MODEL_LABELS:
        raise ApiError(f"Unknown model '{name}'. Use one of: {', '.join(MODEL_LABELS)}.", 400)
    meta = read_metadata(cfg)
    if not meta or name not in meta.get("metrics", {}):
        raise ApiError("That model has not been trained yet.", 409)
    meta["active_model"] = name
    _paths(cfg)[1].write_text(json.dumps(meta, indent=2))
    return meta


def _load_bundle(cfg, name):
    path = _paths(cfg)[0] / f"{name}.joblib"
    if not path.exists():
        raise ApiError("No trained model found. Train the model first (open the Prediction Model page).", 409)
    key = (str(path), path.stat().st_mtime_ns)
    if key not in _cache:
        _cache.clear()
        _cache[key] = joblib.load(path)
    return _cache[key]


# --------------------------------------------------------------------------
# Training / retraining
# --------------------------------------------------------------------------
def _metrics(y_true, y_pred):
    mse = mean_squared_error(y_true, y_pred)
    return {"mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
            "mse": round(float(mse), 4),
            "rmse": round(float(np.sqrt(mse)), 4),
            "r2": round(float(r2_score(y_true, y_pred)), 4)}


def prepare_dataset(db, today=None):
    raw = prep.load_history_raw(db)
    clean = prep.completed_days_only(prep.clean_history(raw), today)
    if clean.empty:
        raise ApiError("There is no inventory history to learn from yet.", 422)
    n_days = clean["date"].nunique()
    return clean, n_days


def train(db, cfg, active=None, trigger="train", today=None):
    """Trains both models, evaluates them on held-out recent data, saves them."""
    if active is not None and active not in MODEL_LABELS:
        raise ApiError(f"Unknown model '{active}'. Use one of: {', '.join(MODEL_LABELS)}.", 400)
    clean, n_days = prepare_dataset(db, today)
    if n_days < cfg["MIN_TRAINING_DAYS"]:
        raise ApiError(
            f"Not enough history to train: {n_days} days found, at least "
            f"{cfg['MIN_TRAINING_DAYS']} are needed.", 422)

    frame, origin = prep.build_training_frame(clean)
    if len(frame) < 50:
        raise ApiError("Not enough usable rows after feature preparation to train a model.", 422)

    dates = np.sort(frame["date"].unique())
    cut = dates[int(len(dates) * (1 - cfg["TEST_FRACTION"]))]
    train_df, test_df = frame[frame["date"] < cut], frame[frame["date"] >= cut]
    if train_df.empty or test_df.empty:
        raise ApiError("History is too short to split into training and test sets.", 422)

    previous = read_metadata(cfg)
    X_tr, y_tr = train_df[prep.FEATURES], train_df["demand"]
    X_te, y_te = test_df[prep.FEATURES], test_df["demand"]

    metrics, importance, test_pred = {}, {}, {}
    for name in MODEL_LABELS:
        model = _new_model(name).fit(X_tr, y_tr)
        pred = np.clip(model.predict(X_te), 0, None)
        metrics[name] = _metrics(y_te, pred)
        test_pred[name] = pred
        # final model: refit on ALL data so the newest history is used
        final = _new_model(name).fit(frame[prep.FEATURES], frame["demand"])
        if name == "linear_regression":
            # coefficient x spread of the feature, so features measured in different units can be compared
            spread = frame[prep.FEATURES].std().to_numpy()
            importance[name] = {f: round(float(abs(c) * sd), 4) for f, c, sd in zip(prep.FEATURES, final.coef_, spread)}
        else:
            importance[name] = {f: round(float(c), 4) for f, c in zip(prep.FEATURES, final.feature_importances_)}
        joblib.dump({"model": final, "features": prep.FEATURES, "origin": str(origin.date()),
                     "name": name}, _paths(cfg)[0] / f"{name}.joblib")

    curve = test_df[["date", "demand"]].copy()
    for name, p in test_pred.items():
        curve[name] = p
    curve = curve.groupby("date").sum().tail(60)

    chosen = active or (previous or {}).get("active_model") or cfg["DEFAULT_MODEL"]
    meta = {
        "trained_at": datetime.now().replace(microsecond=0).isoformat(),
        "active_model": chosen,
        "metrics": metrics,
        "feature_importance": importance,
        "n_rows": int(len(frame)), "n_train": int(len(train_df)), "n_test": int(len(test_df)),
        "n_products": int(clean["product_id"].nunique()),
        "history_days": int(n_days),
        "history_start": str(clean["date"].min().date()),
        "history_end": str(clean["date"].max().date()),
        "test_start": str(pd.Timestamp(cut).date()),
        "features": prep.FEATURES,
        "test_curve": {"dates": [str(d.date()) for d in curve.index],
                       "actual": [round(float(v), 2) for v in curve["demand"]],
                       "linear_regression": [round(float(v), 2) for v in curve["linear_regression"]],
                       "random_forest": [round(float(v), 2) for v in curve["random_forest"]]},
    }
    _paths(cfg)[1].write_text(json.dumps(meta, indent=2))
    best = min(metrics, key=lambda n: metrics[n]["rmse"])
    meta["best_model_by_rmse"] = best

    db.model_runs.insert_one({
        "run_at": meta["trained_at"], "trigger": trigger, "active_model": chosen,
        "metrics": metrics, "n_rows": meta["n_rows"], "history_end": meta["history_end"],
    })
    result = {k: v for k, v in meta.items() if k != "test_curve"}
    result["best_model_by_rmse"] = best
    if trigger == "retrain" and previous:
        prev_m = previous.get("metrics", {}).get(chosen)
        result["previous"] = {"trained_at": previous.get("trained_at"), "n_rows": previous.get("n_rows"),
                              "metrics": prev_m}
        result["improvement"] = (round(prev_m["rmse"] - metrics[chosen]["rmse"], 4) if prev_m else None)
    return result


def status(db, cfg):
    meta = read_metadata(cfg)
    runs = list(db.model_runs.find({}, {"_id": 0}).sort("run_at", -1).limit(20))
    if not meta:
        return {"trained": False, "runs": runs}
    best = min(meta["metrics"], key=lambda n: meta["metrics"][n]["rmse"])
    return {"trained": True, **meta, "best_model_by_rmse": best, "runs": runs,
            "labels": MODEL_LABELS}


# --------------------------------------------------------------------------
# Forecasting
# --------------------------------------------------------------------------
def forecast(db, cfg, product_ids, days, model_name=None, allow_baseline=False, today=None):
    """Predicts daily demand for each product for the next `days` days (from tomorrow).

    Returns {product_id: {"dates": [...], "values": [...], "model": name}}.
    allow_baseline=True falls back to a moving average when no model exists yet.
    """
    if not 1 <= days <= cfg["MAX_FORECAST_DAYS"]:
        raise ApiError(f"'days' must be between 1 and {cfg['MAX_FORECAST_DAYS']}.", 400)
    if model_name is not None and model_name not in MODEL_LABELS:
        raise ApiError(f"Unknown model '{model_name}'. Use one of: {', '.join(MODEL_LABELS)}.", 400)
    today = pd.Timestamp(today or date.today())
    meta = read_metadata(cfg)
    bundle, used = None, "baseline_moving_average"
    name = model_name or (meta or {}).get("active_model") or cfg["DEFAULT_MODEL"]
    if meta is not None or not allow_baseline:
        try:
            bundle = _load_bundle(cfg, name)
            used = name
        except ApiError:
            if not allow_baseline:
                raise

    clean = prep.completed_days_only(prep.clean_history(prep.load_history_raw(db)), today)
    last = clean["date"].max() if not clean.empty else None
    histories = {}
    for pid in product_ids:
        g = clean[clean["product_id"] == pid]
        histories[pid] = list(g.sort_values("date")["demand"].tail(28)) if not g.empty else []

    out_dates = [(today + timedelta(days=i)).date().isoformat() for i in range(1, days + 1)]
    results = {pid: [] for pid in product_ids}
    if last is None:  # no history at all
        return {pid: {"dates": out_dates, "values": [0.0] * days, "model": "no_history"}
                for pid in product_ids}

    gap = max((today - last).days, 0)           # unseen days between the data and today
    origin = bundle["origin"] if bundle else None
    for step in range(gap + days):
        d = last + timedelta(days=step + 1)
        if bundle is not None:
            rows = []
            for pid in product_ids:
                feats = prep.calendar_features(d, origin)
                feats.update(prep.lag_features(histories[pid]))
                rows.append([feats[f] for f in bundle["features"]])
            preds = np.clip(bundle["model"].predict(pd.DataFrame(rows, columns=bundle["features"])), 0, None)
        else:
            preds = [float(np.mean(histories[pid][-28:])) if histories[pid] else 0.0 for pid in product_ids]
        for pid, p in zip(product_ids, preds):
            p = round(float(p), 2)
            histories[pid].append(p)
            histories[pid] = histories[pid][-28:]
            if step >= gap:
                results[pid].append(p)
    return {pid: {"dates": out_dates, "values": results[pid], "model": used} for pid in product_ids}
