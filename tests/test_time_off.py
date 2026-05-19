def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_employee_submits_time_off(client, employee_token):
    resp = client.post("/time-off", json={
        "start_date": "2024-03-01",
        "end_date": "2024-03-05",
        "reason": "Family vacation"
    }, headers=auth(employee_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["reason"] == "Family vacation"


def test_manager_can_approve_time_off(client, manager_token, employee_token):
    create_resp = client.post("/time-off", json={
        "start_date": "2024-04-01",
        "end_date": "2024-04-03",
        "reason": "Medical leave"
    }, headers=auth(employee_token))
    req_id = create_resp.json()["id"]

    approve_resp = client.put(f"/time-off/{req_id}/approve", headers=auth(manager_token))
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"


def test_only_manager_can_approve(client, employee_token):
    create_resp = client.post("/time-off", json={
        "start_date": "2024-05-01",
        "end_date": "2024-05-02",
        "reason": "Personal"
    }, headers=auth(employee_token))
    req_id = create_resp.json()["id"]

    resp = client.put(f"/time-off/{req_id}/approve", headers=auth(employee_token))
    assert resp.status_code == 403
