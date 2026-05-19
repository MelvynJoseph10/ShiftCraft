def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_facility_manager(client, manager_token):
    resp = client.post("/facilities", json={"name": "Warehouse A", "opening_time": "08:00:00", "closing_time": "20:00:00"}, headers=auth(manager_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Warehouse A"
    assert data["id"] is not None


def test_list_facilities(client, manager_token):
    client.post("/facilities", json={"name": "Facility 1", "opening_time": "09:00:00", "closing_time": "17:00:00"}, headers=auth(manager_token))
    client.post("/facilities", json={"name": "Facility 2", "opening_time": "10:00:00", "closing_time": "18:00:00"}, headers=auth(manager_token))
    resp = client.get("/facilities", headers=auth(manager_token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_employee_cannot_create_facility(client, employee_token):
    resp = client.post("/facilities", json={"name": "Bad", "opening_time": "08:00:00", "closing_time": "16:00:00"}, headers=auth(employee_token))
    assert resp.status_code == 403


def test_closing_before_opening_returns_422(client, manager_token):
    resp = client.post("/facilities", json={"name": "Bad Times", "opening_time": "18:00:00", "closing_time": "08:00:00"}, headers=auth(manager_token))
    assert resp.status_code == 422


def test_closing_equal_opening_returns_422(client, manager_token):
    resp = client.post("/facilities", json={"name": "Same Time", "opening_time": "09:00:00", "closing_time": "09:00:00"}, headers=auth(manager_token))
    assert resp.status_code == 422
