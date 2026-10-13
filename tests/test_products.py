from tests.conftest import add_product


def test_create_and_get_product(client):
    r = add_product(client)
    assert r.status_code == 201
    assert r.get_json()["product_id"] == "P1"
    got = client.get("/api/products/p1").get_json()  # ids are case-insensitive
    assert got["name"] == "Widget" and got["quantity"] == 10


def test_duplicate_product_id_rejected(client):
    add_product(client)
    r = add_product(client, name="Other")
    assert r.status_code == 409
    assert "already exists" in r.get_json()["error"]


def test_auto_generated_ids(client):
    first = client.post("/api/products", json={"name": "A", "category": "C", "price": 1}).get_json()
    second = client.post("/api/products", json={"name": "B", "category": "C", "price": 1}).get_json()
    assert first["product_id"] == "P0001" and second["product_id"] == "P0002"


def test_validation_errors(client):
    for bad in ({"name": ""}, {"price": -1}, {"price": "abc"}, {"quantity": -5},
                {"quantity": 1.5}, {"reorder_level": -1}, {"product_id": "bad id!"}, {"category": None}):
        r = add_product(client, **bad)
        assert r.status_code == 400, bad
        assert "error" in r.get_json()


def test_non_json_body_rejected(client):
    r = client.post("/api/products", data="not json", content_type="text/plain")
    assert r.status_code == 400


def test_search_and_category_filter(client):
    add_product(client, product_id="A1", name="Blue Pen", category="Stationery")
    add_product(client, product_id="B1", name="Red Mug", category="Kitchen")
    assert [p["product_id"] for p in client.get("/api/products?q=pen").get_json()] == ["A1"]
    assert [p["product_id"] for p in client.get("/api/products?q=b1").get_json()] == ["B1"]
    assert len(client.get("/api/products?category=Kitchen").get_json()) == 1
    assert client.get("/api/products?q=.*").get_json() == []  # regex characters are escaped


def test_update_product(client):
    add_product(client)
    r = client.put("/api/products/P1", json={"name": "Gadget", "price": 9.99, "reorder_level": 3})
    assert r.status_code == 200
    body = r.get_json()
    assert (body["name"], body["price"], body["reorder_level"]) == ("Gadget", 9.99, 3)


def test_update_cannot_change_quantity_or_id(client):
    add_product(client)
    assert client.put("/api/products/P1", json={"quantity": 99}).status_code == 400
    assert client.put("/api/products/P1", json={"product_id": "X"}).status_code == 400
    assert client.put("/api/products/P1", json={}).status_code == 400
    assert client.put("/api/products/NOPE", json={"name": "x"}).status_code == 404


def test_delete_removes_product_and_its_history(client):
    add_product(client)
    client.post("/api/stock/out", json={"product_id": "P1", "quantity": 2})
    r = client.delete("/api/products/P1")
    assert r.status_code == 200
    assert r.get_json()["history_rows_removed"] >= 1
    assert client.get("/api/products/P1").status_code == 404
    assert client.get("/api/history?product_id=P1").get_json() == []
    assert client.delete("/api/products/P1").status_code == 404
