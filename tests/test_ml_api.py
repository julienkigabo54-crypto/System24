"""Machine learning, prediction, recommendations and reporting (uses sample data)."""
from datetime import date, timedelta

from tests.conftest import add_product


def train(client, path="/api/ml/train"):
    r = client.post(path, json={})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def test_predict_before_training_gives_clear_error(seeded):
    r = seeded.post("/api/predict", json={"product_id": "P0001", "days": 7})
    assert r.status_code == 409
    assert "Train the model" in r.get_json()["error"]


def test_training_needs_enough_history(client):
    add_product(client)
    r = client.post("/api/ml/train", json={})
    assert r.status_code == 422


def test_train_evaluates_and_saves_models(seeded, seeded_app):
    result = train(seeded)
    for model in ("linear_regression", "random_forest"):
        m = result["metrics"][model]
        assert set(m) == {"mae", "mse", "rmse", "r2"}
        assert m["rmse"] >= m["mae"] >= 0
        assert m["r2"] > 0.3          # clearly better than guessing the average
    assert result["active_model"] == "linear_regression"
    models_dir = seeded_app.config["MODEL_DIR"]
    assert (models_dir / "linear_regression.joblib").exists()
    assert (models_dir / "random_forest.joblib").exists()
    status = seeded.get("/api/ml/status").get_json()
    assert status["trained"] and len(status["runs"]) == 1


def test_retraining_after_new_data_logs_a_second_run(seeded):
    train(seeded)
    seeded.post("/api/stock/out", json={"product_id": "P0001", "quantity": 1})
    result = train(seeded, "/api/ml/retrain")
    assert result["previous"]["metrics"] is not None and "improvement" in result
    assert len(seeded.get("/api/ml/status").get_json()["runs"]) == 2


def test_switching_active_model(seeded):
    train(seeded)
    assert seeded.post("/api/ml/active", json={"model": "random_forest"}).status_code == 200
    assert seeded.get("/api/ml/status").get_json()["active_model"] == "random_forest"
    assert seeded.post("/api/ml/active", json={"model": "magic"}).status_code == 400


def test_prediction_returns_daily_and_total_and_is_stored(seeded):
    train(seeded)
    r = seeded.post("/api/predict", json={"product_id": "p0001", "days": 10})
    assert r.status_code == 200
    body = r.get_json()
    assert len(body["daily"]) == 10
    assert body["daily"][0]["date"] == (date.today() + timedelta(days=1)).isoformat()
    assert all(d["predicted_demand"] >= 0 for d in body["daily"])
    assert abs(sum(d["predicted_demand"] for d in body["daily"]) - body["predicted_total_demand"]) < 0.05
    assert body["status"] in ("Critical", "Low Stock", "OK", "Overstock")
    stored = seeded.get("/api/predictions?product_id=P0001").get_json()
    assert len(stored) == 1 and stored[0]["days_ahead"] == 10
    assert stored[0]["additional_stock_required"] == body["additional_stock_required"]


def test_prediction_input_validation(seeded):
    train(seeded)
    assert seeded.post("/api/predict", json={"product_id": "NOPE", "days": 5}).status_code == 404
    for days in (0, -1, 91, "x", 2.5):
        assert seeded.post("/api/predict", json={"product_id": "P0001", "days": days}).status_code == 400, days
    assert seeded.post("/api/predict", json={"days": 5}).status_code == 400
    assert seeded.post("/api/predict", json={"product_id": "P0001", "days": 5, "model": "x"}).status_code == 400


def test_stock_requirement_matches_the_formula(seeded):
    train(seeded)
    p = seeded.post("/api/predict", json={"product_id": "P0001", "days": 14}).get_json()
    expected = max(0, -(-int((p["predicted_total_demand"] + p["reorder_level"] - p["current_stock"]) * 1000) // 1000))
    assert abs(p["additional_stock_required"] - expected) <= 1


def test_dashboard_and_recommendations(seeded):
    train(seeded)
    d = seeded.get("/api/dashboard").get_json()
    assert d["total_products"] == 15
    assert sum(d["status_counts"].values()) == 15
    assert d["inventory_value"] > 0 and d["model_trained"] is True
    assert set(d["status_counts"]) == {"Critical", "Low Stock", "OK", "Overstock"}
    assert all(a["status"] in ("Critical", "Low Stock") for a in d["alerts"])
    items = seeded.get("/api/recommendations?days=14").get_json()["items"]
    priorities = [i["priority"] for i in items]
    assert priorities == sorted(priorities)            # most urgent first
    assert seeded.get("/api/recommendations?days=0").status_code == 400
    assert len(seeded.get("/api/alerts").get_json()) == len(d["alerts"])


def test_dashboard_works_without_a_trained_model(seeded):
    d = seeded.get("/api/dashboard").get_json()
    assert d["model_trained"] is False and d["total_products"] == 15
    assert d["model_in_use"] == "baseline_moving_average"


def test_data_quality_and_cleaning(seeded):
    before = seeded.get("/api/data/quality").get_json()
    assert before["duplicate_rows"] > 0 and before["missing_values"]
    after = seeded.post("/api/data/clean").get_json()["after"]
    assert after["duplicate_rows"] == 0 and after["missing_values"] == {}


def test_analytics_and_reports(seeded):
    train(seeded)
    s = seeded.get("/api/analytics/demand-series?product_id=P0001&history_days=30&days=7").get_json()
    assert len(s["history"]["dates"]) == 30 and len(s["forecast"]["dates"]) == 7
    assert seeded.get("/api/analytics/trends").get_json()["monthly"]["labels"]
    assert seeded.get("/api/analytics/statistics").get_json()["products"]
    assert seeded.get("/api/analytics/inventory-value").get_json()["labels"]
    csv = seeded.get("/api/reports/inventory.csv")
    assert csv.status_code == 200 and csv.mimetype == "text/csv"
    assert csv.get_data(as_text=True).startswith("Product code,Product name")
    png = seeded.get("/api/reports/demand-chart/P0001.png")
    assert png.status_code == 200 and png.data[:4] == b"\x89PNG"


def test_general_error_handling(client):
    assert client.get("/api/nothing-here").status_code == 404
    assert client.get("/api/nothing-here").get_json()["error"]
    assert client.delete("/api/products").status_code == 405
    assert client.get("/api/health").get_json() == {"status": "ok"}


def test_every_page_renders_and_the_dashboard_is_the_start_page(client):
    for url in ("/", "/products", "/stock", "/history", "/predict", "/recommendations", "/analytics", "/model"):
        r = client.get(url)
        assert r.status_code == 200 and b"Intelligent" in r.data, url
    assert b"Dashboard" in client.get("/").data
    assert client.get("/dashboard").status_code == 301          # old address forwards to the start page
    menu = client.get("/").get_data(as_text=True)
    assert 'href="/dashboard"' not in menu and ">Home<" not in menu   # no separate home page


def test_screen_text_uses_full_words():
    """No technical abbreviations in the text people read on screen."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    banned = re.compile(r"\b(MAE|RMSE|MSE|CSV|PNG|ML|SKU|KPI|Qty|Std|R\u00b2)\b")
    for path in list((root / "templates").glob("*.html")) + list((root / "static" / "js").glob("*.js")):
        hits = banned.findall(path.read_text(encoding="utf-8"))
        assert not hits, f"{path.name} contains abbreviations: {hits}"


def test_forecast_bridges_a_gap_between_history_and_today(seeded, seeded_app):
    """If the data ends days ago, the model still predicts starting tomorrow."""
    from db import get_db
    from services import ml
    train(seeded)
    later = date.today() + timedelta(days=6)
    with seeded_app.app_context():
        fc = ml.forecast(get_db(), seeded_app.config, ["P0001"], 5, today=later)["P0001"]
    assert fc["dates"][0] == (later + timedelta(days=1)).isoformat()
    assert len(fc["values"]) == 5 and all(v >= 0 for v in fc["values"])


def test_new_product_without_history_can_be_predicted(seeded):
    train(seeded)
    add_product(seeded, product_id="NEW1", quantity=0, reorder_level=5)
    r = seeded.post("/api/predict", json={"product_id": "NEW1", "days": 7})
    assert r.status_code == 200
    assert r.get_json()["status"] == "Critical"        # no stock at all
