def auth(token):
    return {"Authorization": f"Bearer {token}"}


def make_facility(client, token):
    resp = client.post("/facilities", json={"name": "Test Facility", "opening_time": "08:00:00", "closing_time": "20:00:00"}, headers=auth(token))
    return resp.json()["id"]


def make_employee(client, token, email="worker@test.com"):
    resp = client.post("/employees", json={
        "name": "Worker",
        "email": email,
        "password": "pass123",
        "role": "employee"
    }, headers=auth(token))
    return resp.json()["id"]


def test_create_shift(client, manager_token):
    fac_id = make_facility(client, manager_token)
    emp_id = make_employee(client, manager_token)
    resp = client.post("/schedules", json={
        "facility_id": fac_id,
        "user_id": emp_id,
        "start_time": "2024-01-15T08:00:00",
        "end_time": "2024-01-15T16:00:00"
    }, headers=auth(manager_token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "scheduled"
    assert data["facility_id"] == fac_id


def test_inactive_employee_cannot_be_assigned_shift(client, manager_token):
    fac_id = make_facility(client, manager_token)
    emp_id = make_employee(client, manager_token, email="inactive@test.com")
    client.delete(f"/employees/{emp_id}", headers=auth(manager_token))

    resp = client.post("/schedules", json={
        "facility_id": fac_id,
        "user_id": emp_id,
        "start_time": "2024-01-15T08:00:00",
        "end_time": "2024-01-15T16:00:00"
    }, headers=auth(manager_token))
    assert resp.status_code == 400


def test_get_employee_schedule_by_week(client, manager_token):
    fac_id = make_facility(client, manager_token)
    emp_id = make_employee(client, manager_token, email="weekworker@test.com")

    # Create shift in week 3 of 2024 (Mon 2024-01-15)
    client.post("/schedules", json={
        "facility_id": fac_id,
        "user_id": emp_id,
        "start_time": "2024-01-15T08:00:00",
        "end_time": "2024-01-15T16:00:00"
    }, headers=auth(manager_token))

    # Create shift in a different week
    client.post("/schedules", json={
        "facility_id": fac_id,
        "user_id": emp_id,
        "start_time": "2024-01-22T08:00:00",
        "end_time": "2024-01-22T16:00:00"
    }, headers=auth(manager_token))

    resp = client.get(f"/employees/{emp_id}/schedule?week=2024-W03", headers=auth(manager_token))
    assert resp.status_code == 200
    shifts = resp.json()
    assert len(shifts) == 1
    assert "2024-01-15" in shifts[0]["start_time"]
