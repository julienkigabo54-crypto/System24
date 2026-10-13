from tests.conftest import add_product


def qty(client, pid="P1"):
    return client.get(f"/api/products/{pid}").get_json()["quantity"]


def test_stock_in_increases_quantity(client):
    add_product(client)
    r = client.post("/api/stock/in", json={"product_id": "P1", "quantity": 5})
    assert r.status_code == 201
    assert r.get_json()["new_quantity"] == 15 and qty(client) == 15


def test_stock_out_decreases_quantity(client):
    add_product(client)
    r = client.post("/api/stock/out", json={"product_id": "P1", "quantity": 4})
    assert r.status_code == 201 and qty(client) == 6


def test_withdrawal_exceeding_stock_is_rejected(client):
    add_product(client)
    r = client.post("/api/stock/out", json={"product_id": "P1", "quantity": 11})
    assert r.status_code == 409
    assert "Insufficient stock" in r.get_json()["error"]
    assert qty(client) == 10  # unchanged
    # exactly the available amount is allowed
    assert client.post("/api/stock/out", json={"product_id": "P1", "quantity": 10}).status_code == 201
    assert qty(client) == 0


def test_invalid_movements(client):
    add_product(client)
    assert client.post("/api/stock/in", json={"product_id": "NOPE", "quantity": 1}).status_code == 404
    assert client.post("/api/stock/out", json={"product_id": "NOPE", "quantity": 1}).status_code == 404
    for bad in (0, -3, 2.5, "x", None):
        assert client.post("/api/stock/in", json={"product_id": "P1", "quantity": bad}).status_code == 400, bad
    assert client.post("/api/stock/in", json={"quantity": 1}).status_code == 400
    assert qty(client) == 10


def test_history_records_daily_totals(client):
    add_product(client, quantity=0)
    client.post("/api/stock/in", json={"product_id": "P1", "quantity": 20})
    client.post("/api/stock/out", json={"product_id": "P1", "quantity": 3})
    client.post("/api/stock/out", json={"product_id": "P1", "quantity": 2})
    rows = client.get("/api/history?product_id=P1").get_json()
    assert len(rows) == 1  # one row per product per day
    row = rows[0]
    assert (row["stock_in"], row["stock_out"], row["demand"], row["closing_stock"]) == (20, 5, 5, 15)


def test_history_filters_validate_dates(client):
    add_product(client)
    assert client.get("/api/history?start=2024-13-45").status_code == 400
    assert client.get("/api/history?limit=abc").status_code == 400
    assert client.get("/api/history?start=2000-01-01&end=2000-01-02").get_json() == []
