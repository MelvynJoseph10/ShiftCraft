def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_employee(client, manager_token):
    resp = client.post("/employees", json={
        "name": "Alice Smith",
        "email": "alice@test.com",
        "password": "pass123",
        "role": "employee",
        "employee_role": "junior"
    }, headers=auth(manager_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Alice Smith"
    assert data["is_active"] is True


def test_soft_delete_employee(client, manager_token):
    create_resp = client.post("/employees", json={
        "name": "Bob Jones",
        "email": "bob@test.com",
        "password": "pass123",
        "role": "employee"
    }, headers=auth(manager_token))
    emp_id = create_resp.json()["id"]

    del_resp = client.delete(f"/employees/{emp_id}", headers=auth(manager_token))
    assert del_resp.status_code == 200
    assert del_resp.json()["is_active"] is False


def test_deleted_employee_not_in_active_list(client, manager_token):
    create_resp = client.post("/employees", json={
        "name": "Carol Lee",
        "email": "carol@test.com",
        "password": "pass123",
        "role": "employee"
    }, headers=auth(manager_token))
    emp_id = create_resp.json()["id"]

    client.delete(f"/employees/{emp_id}", headers=auth(manager_token))

    list_resp = client.get("/employees", headers=auth(manager_token))
    ids = [e["id"] for e in list_resp.json()]
    assert emp_id not in ids
