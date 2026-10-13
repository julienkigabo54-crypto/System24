"""REST API (JSON). All routes live under /api."""
from flask import Blueprint, Response, current_app, jsonify, request

from db import get_db
from services import analysis, ml, preprocessing as prep, products, reports, stock
from services.errors import ApiError

api = Blueprint("api", __name__, url_prefix="/api")


def cfg():
    return current_app.config


def body():
    """JSON body, or a clear 400 if it is missing / malformed."""
    data = request.get_json(silent=True)
    if data is None:
        raise ApiError("Request body must be valid JSON (Content-Type: application/json).", 400)
    return data


@api.get("/health")
def health():
    if not cfg().get("USE_MOCK_DB"):
        get_db().command("ping")  # raises -> clean 503 if MongoDB is unreachable
    return jsonify({"status": "ok"})


# ---- Products -------------------------------------------------------------
@api.post("/products")
def create_product():
    return jsonify(products.create_product(get_db(), body())), 201


@api.get("/products")
def list_products():
    return jsonify(products.list_products(get_db(), request.args.get("q"), request.args.get("category")))


@api.get("/products/categories")
def list_categories():
    return jsonify(products.categories(get_db()))


@api.get("/products/<product_id>")
def get_product(product_id):
    return jsonify(products.get_product(get_db(), product_id))


@api.put("/products/<product_id>")
def update_product(product_id):
    return jsonify(products.update_product(get_db(), product_id, body()))


@api.delete("/products/<product_id>")
def delete_product(product_id):
    return jsonify(products.delete_product(get_db(), product_id))


# ---- Stock movements and history -------------------------------------------
@api.post("/stock/in")
def stock_in():
    return jsonify(stock.record_movement(get_db(), body(), "in")), 201


@api.post("/stock/out")
def stock_out():
    return jsonify(stock.record_movement(get_db(), body(), "out")), 201


@api.get("/history")
def history():
    return jsonify(stock.get_history(
        get_db(), request.args.get("product_id"), request.args.get("start"),
        request.args.get("end"), request.args.get("limit", 500)))


# ---- Data preparation -------------------------------------------------------
@api.get("/data/quality")
def data_quality():
    return jsonify(prep.quality_report(get_db()))


@api.post("/data/clean")
def data_clean():
    return jsonify(prep.clean_database(get_db()))


# ---- Machine learning -------------------------------------------------------
@api.post("/ml/train")
def ml_train():
    data = request.get_json(silent=True) or {}
    return jsonify(ml.train(get_db(), cfg(), active=data.get("active_model"), trigger="train"))


@api.post("/ml/retrain")
def ml_retrain():
    data = request.get_json(silent=True) or {}
    return jsonify(ml.train(get_db(), cfg(), active=data.get("active_model"), trigger="retrain"))


@api.get("/ml/status")
def ml_status():
    return jsonify(ml.status(get_db(), cfg()))


@api.post("/ml/active")
def ml_active():
    data = body()
    return jsonify(ml.set_active_model(cfg(), data.get("model")))


# ---- Prediction, requirement and recommendations ----------------------------
@api.post("/predict")
def predict():
    return jsonify(analysis.predict_product(get_db(), cfg(), body()))


@api.get("/predictions")
def predictions():
    return jsonify(analysis.list_predictions(get_db(), request.args.get("product_id"),
                                             request.args.get("limit", 50)))


@api.get("/recommendations")
def recommendations():
    days = analysis.parse_days(request.args.get("days"), cfg())
    items = analysis.analyze_products(get_db(), cfg(), days)
    return jsonify({"days": days, "items": items})


@api.get("/alerts")
def alerts():
    items = analysis.analyze_products(get_db(), cfg())
    return jsonify([i for i in items if i["status"] in ("Critical", "Low Stock")])


# ---- Dashboard and analytics ----------------------------------------------------
@api.get("/dashboard")
def dashboard():
    days = analysis.parse_days(request.args.get("days"), cfg())
    return jsonify(analysis.dashboard(get_db(), cfg(), days))


@api.get("/analytics/demand-series")
def demand_series():
    return jsonify(analysis.demand_series(
        get_db(), cfg(), request.args.get("product_id"), request.args.get("history_days", 60),
        request.args.get("days"), request.args.get("model") or None))


@api.get("/analytics/statistics")
def statistics():
    return jsonify(analysis.statistics(get_db()))


@api.get("/analytics/trends")
def trends():
    return jsonify(analysis.trends(get_db()))


@api.get("/analytics/inventory-value")
def inventory_value():
    return jsonify(analysis.inventory_value_by_category(get_db()))


# ---- Reports ----------------------------------------------------------------------
@api.get("/reports/inventory.csv")
def report_csv():
    days = analysis.parse_days(request.args.get("days"), cfg())
    return Response(reports.inventory_csv(get_db(), cfg(), days), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=inventory_report.csv"})


@api.get("/reports/demand-chart/<product_id>.png")
def report_chart(product_id):
    png = reports.demand_chart_png(get_db(), cfg(), product_id)
    return Response(png, mimetype="image/png")
