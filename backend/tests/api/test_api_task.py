from datetime import date, datetime, timedelta, timezone

import pytest

from app.service.task import add_interval, next_due_date


def millis(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def from_millis(m: int) -> date:
    return datetime.fromtimestamp(m / 1000, timezone.utc).date()


def today() -> date:
    return datetime.now(timezone.utc).date()


# --- pure date logic -------------------------------------------------------------


@pytest.mark.parametrize(
    "start,every,unit,expected",
    [
        (date(2025, 1, 31), 1, "month", date(2025, 2, 28)),
        (date(2024, 1, 31), 1, "month", date(2024, 2, 29)),
        (date(2025, 11, 15), 3, "month", date(2026, 2, 15)),
        (date(2025, 12, 31), 12, "month", date(2026, 12, 31)),
        (date(2025, 1, 1), 2, "week", date(2025, 1, 15)),
        (date(2025, 12, 30), 3, "day", date(2026, 1, 2)),
    ],
)
def test_add_interval(start, every, unit, expected):
    assert add_interval(start, every, unit) == expected


def test_next_due_date_does_not_catch_up():
    # overdue by months: next date is relative to today, not the old due date
    assert next_due_date(date(2020, 1, 1), 1, "week", date(2025, 6, 1)) == date(
        2025, 6, 8
    )
    # still in the future: advance from the old due date
    assert next_due_date(date(2025, 6, 10), 1, "week", date(2025, 6, 1)) == date(
        2025, 6, 17
    )


# --- helpers ----------------------------------------------------------------------


def login(client, username, password):
    response = client.post(
        "/api/auth", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    client.environ_base["HTTP_AUTHORIZATION"] = (
        f"Bearer {response.get_json()['access_token']}"
    )


@pytest.fixture
def me(user_client_with_household):
    return user_client_with_household.get("/api/user").get_json()["id"]


@pytest.fixture
def second_user(
    user_client_with_household,
    household_id,
    username,
    password,
    admin_username,
    admin_password,
):
    """A second user that is a (non-admin) member of the household."""
    client = user_client_with_household
    login(client, admin_username, admin_password)
    response = client.post(
        "/api/user/new", json={"username": "second", "name": "Second", "password": "pw"}
    )
    assert response.status_code == 200
    login(client, "second", "pw")
    uid = client.get("/api/user").get_json()["id"]
    login(client, username, password)
    response = client.put(
        f"/api/household/{household_id}/member/{uid}", json={"admin": False}
    )
    assert response.status_code == 200
    return uid


def switch_to_second(client):
    login(client, "second", "pw")


def switch_to_first(client, username, password):
    login(client, username, password)


def create(client, household_id, **data):
    return client.post(f"/api/household/{household_id}/tasks", json=data)


# --- CRUD / validation -------------------------------------------------------------


def test_create_and_list_task(user_client_with_household, household_id, me):
    c = user_client_with_household
    response = create(c, household_id, name="Dishes")
    assert response.status_code == 200
    data = response.get_json()
    assert data["name"] == "Dishes"
    assert data["rotation_mode"] == "none"
    assert data["assigned_to"] is None
    assert data["created_by"] == me
    assert data["recurring"] is False
    assert data["participants"] == []

    tasks = c.get(f"/api/household/{household_id}/tasks").get_json()
    assert [t["name"] for t in tasks] == ["Dishes"]


def test_create_requires_name(user_client_with_household, household_id):
    assert create(user_client_with_household, household_id, name=" ").status_code == 400
    assert create(user_client_with_household, household_id).status_code == 400
    assert (
        create(user_client_with_household, household_id, name="x" * 129).status_code
        == 400
    )


@pytest.mark.parametrize(
    "data",
    [
        # repeat requires recurring and due date
        {"repeat_every": 1, "repeat_unit": "week", "recurring": True},
        {"repeat_every": 1, "repeat_unit": "week", "due_date": 1},
        # unit and every together
        {"repeat_every": 1, "recurring": True, "due_date": 1},
        # range per unit
        {
            "repeat_every": 25,
            "repeat_unit": "month",
            "recurring": True,
            "due_date": 1,
        },
        {"repeat_every": 0, "repeat_unit": "day", "recurring": True, "due_date": 1},
        {"repeat_every": 1, "repeat_unit": "year", "recurring": True, "due_date": 1},
        # rotation needs two distinct participants
        {"rotation_mode": "ordered"},
        {"rotation_mode": "ordered", "participants": [1]},
        {"rotation_mode": "random", "participants": [1, 1]},
        # assignee must be a member
        {"assigned_to": 9999},
    ],
)
def test_validation_matrix(user_client_with_household, household_id, data):
    response = create(user_client_with_household, household_id, name="x", **data)
    assert response.status_code == 400, response.get_json()


def test_rotation_participants_must_be_members(
    user_client_with_household, household_id, me
):
    response = create(
        user_client_with_household,
        household_id,
        name="x",
        rotation_mode="ordered",
        participants=[me, 9999],
    )
    assert response.status_code == 400


def test_update_and_delete(user_client_with_household, household_id, me):
    c = user_client_with_household
    t = create(c, household_id, name="Dishes").get_json()
    response = c.post(f"/api/tasks/{t['id']}", json={"name": "Wash", "assigned_to": me})
    assert response.status_code == 200
    assert response.get_json()["name"] == "Wash"
    assert response.get_json()["assigned_to"] == me
    assert c.get(f"/api/tasks/{t['id']}").status_code == 200
    assert c.delete(f"/api/tasks/{t['id']}").status_code == 200
    assert c.get(f"/api/tasks/{t['id']}").status_code == 404


def test_update_unrecurring_clears_repeat(user_client_with_household, household_id):
    c = user_client_with_household
    t = create(
        c,
        household_id,
        name="x",
        recurring=True,
        due_date=millis(today()),
        repeat_every=1,
        repeat_unit="day",
    ).get_json()
    data = c.post(f"/api/tasks/{t['id']}", json={"recurring": False}).get_json()
    assert data["repeat_every"] is None and data["repeat_unit"] is None
    t2 = create(
        c,
        household_id,
        name="y",
        recurring=True,
        due_date=millis(today()),
        repeat_every=1,
        repeat_unit="day",
    ).get_json()
    data = c.post(f"/api/tasks/{t2['id']}", json={"due_date": None}).get_json()
    assert data["due_date"] is None and data["repeat_every"] is None


def test_rotation_none_clears_participants(
    user_client_with_household, household_id, me, second_user
):
    c = user_client_with_household
    t = create(
        c,
        household_id,
        name="x",
        rotation_mode="ordered",
        participants=[me, second_user],
    ).get_json()
    assert t["participants"] == [me, second_user]
    data = c.post(f"/api/tasks/{t['id']}", json={"rotation_mode": "none"}).get_json()
    assert data["participants"] == []


# --- done --------------------------------------------------------------------------


def test_done_one_off_task_disappears(user_client_with_household, household_id):
    c = user_client_with_household
    t = create(c, household_id, name="Once", due_date=millis(today())).get_json()
    response = c.post(f"/api/tasks/{t['id']}/done", json={"expected_assigned_to": None})
    assert response.status_code == 200
    assert response.get_json()["completed_at"] is not None
    assert c.get(f"/api/household/{household_id}/tasks").get_json() == []
    done = c.get(f"/api/household/{household_id}/tasks?completed=true").get_json()
    assert [x["id"] for x in done] == [t["id"]]
    # already done
    assert (
        c.post(
            f"/api/tasks/{t['id']}/done", json={"expected_assigned_to": None}
        ).status_code
        == 400
    )
    # reopen
    response = c.post(f"/api/tasks/{t['id']}", json={"completed": False})
    assert response.status_code == 200
    assert response.get_json()["completed_at"] is None


def test_done_requires_expected_assigned_to(user_client_with_household, household_id):
    c = user_client_with_household
    t = create(c, household_id, name="x").get_json()
    assert c.post(f"/api/tasks/{t['id']}/done", json={}).status_code == 400


def test_done_conflict(user_client_with_household, household_id, me):
    c = user_client_with_household
    t = create(c, household_id, name="x", assigned_to=me).get_json()
    response = c.post(f"/api/tasks/{t['id']}/done", json={"expected_assigned_to": None})
    assert response.status_code == 409
    assert response.get_json()["task"]["assigned_to"] == me


def test_done_recurring_without_interval_stays(
    user_client_with_household, household_id, me
):
    c = user_client_with_household
    t = create(c, household_id, name="x", recurring=True, assigned_to=me).get_json()
    for _ in range(2):
        response = c.post(
            f"/api/tasks/{t['id']}/done", json={"expected_assigned_to": me}
        )
        assert response.status_code == 200
        assert response.get_json()["completed_at"] is None
        assert response.get_json()["assigned_to"] == me
    assert len(c.get(f"/api/household/{household_id}/tasks").get_json()) == 1


def test_done_advances_due_date(user_client_with_household, household_id):
    c = user_client_with_household
    due = today() + timedelta(days=3)
    t = create(
        c,
        household_id,
        name="x",
        recurring=True,
        due_date=millis(due),
        repeat_every=1,
        repeat_unit="week",
    ).get_json()
    data = c.post(
        f"/api/tasks/{t['id']}/done", json={"expected_assigned_to": None}
    ).get_json()
    assert from_millis(data["due_date"]) == due + timedelta(days=7)


def test_done_overdue_does_not_catch_up(user_client_with_household, household_id):
    c = user_client_with_household
    t = create(
        c,
        household_id,
        name="x",
        recurring=True,
        due_date=millis(today() - timedelta(days=100)),
        repeat_every=1,
        repeat_unit="day",
    ).get_json()
    data = c.post(
        f"/api/tasks/{t['id']}/done",
        json={"expected_assigned_to": None, "done_on": millis(today())},
    ).get_json()
    assert from_millis(data["due_date"]) == today() + timedelta(days=1)


def test_done_on_far_from_server_date_is_ignored(
    user_client_with_household, household_id
):
    c = user_client_with_household
    t = create(
        c,
        household_id,
        name="x",
        recurring=True,
        due_date=millis(today() - timedelta(days=10)),
        repeat_every=1,
        repeat_unit="day",
    ).get_json()
    data = c.post(
        f"/api/tasks/{t['id']}/done",
        json={
            "expected_assigned_to": None,
            "done_on": millis(today() + timedelta(days=30)),
        },
    ).get_json()
    assert from_millis(data["due_date"]) == today() + timedelta(days=1)


def test_ordered_rotation(user_client_with_household, household_id, me, second_user):
    c = user_client_with_household
    t = create(
        c,
        household_id,
        name="x",
        recurring=True,
        rotation_mode="ordered",
        participants=[me, second_user],
    ).get_json()
    assert t["assigned_to"] == me
    expected = [second_user, me, second_user]
    current = me
    for nxt in expected:
        data = c.post(
            f"/api/tasks/{t['id']}/done", json={"expected_assigned_to": current}
        ).get_json()
        assert data["assigned_to"] == nxt
        current = nxt


def test_random_rotation_never_repeats(
    user_client_with_household, household_id, me, second_user
):
    c = user_client_with_household
    t = create(
        c,
        household_id,
        name="x",
        recurring=True,
        rotation_mode="random",
        participants=[me, second_user],
    ).get_json()
    current = t["assigned_to"]
    for _ in range(6):
        data = c.post(
            f"/api/tasks/{t['id']}/done", json={"expected_assigned_to": current}
        ).get_json()
        assert data["assigned_to"] != current
        current = data["assigned_to"]


def test_completions_history(user_client_with_household, household_id, me):
    c = user_client_with_household
    t = create(c, household_id, name="x", recurring=True).get_json()
    c.post(f"/api/tasks/{t['id']}/done", json={"expected_assigned_to": None})
    history = c.get(f"/api/household/{household_id}/tasks/completions").get_json()
    assert len(history) == 1
    assert history[0]["done_by"] == me
    assert history[0]["task_name"] == "x"
    # history is gone when the task is deleted
    c.delete(f"/api/tasks/{t['id']}")
    assert c.get(f"/api/household/{household_id}/tasks/completions").get_json() == []


# --- household switch / permissions --------------------------------------------------


def test_only_assignee_switch(
    user_client_with_household,
    household_id,
    me,
    second_user,
    username,
    password,
):
    c = user_client_with_household
    t = create(c, household_id, name="x", recurring=True, assigned_to=me).get_json()

    # as the second (non-admin) member: allowed while the switch is off
    switch_to_second(c)
    assert (
        c.post(
            f"/api/tasks/{t['id']}/done", json={"expected_assigned_to": me}
        ).status_code
        == 200
    )

    # turn the switch on (household admin)
    switch_to_first(c, username, password)
    response = c.post(
        f"/api/household/{household_id}",
        json={"tasks_only_assignee_can_complete": True},
    )
    assert response.status_code == 200
    assert response.get_json()["tasks_only_assignee_can_complete"] is True

    # second user is not the assignee any more and not an admin
    switch_to_second(c)
    assert (
        c.post(
            f"/api/tasks/{t['id']}/done", json={"expected_assigned_to": me}
        ).status_code
        == 403
    )
    # nor may they reassign it
    assert (
        c.post(f"/api/tasks/{t['id']}", json={"assigned_to": second_user}).status_code
        == 403
    )

    # the assignee and the household admin may
    switch_to_first(c, username, password)
    assert (
        c.post(
            f"/api/tasks/{t['id']}/done", json={"expected_assigned_to": me}
        ).status_code
        == 200
    )


def test_open_task_can_be_completed_by_anyone_with_switch(
    user_client_with_household, household_id, second_user, username, password
):
    c = user_client_with_household
    c.post(
        f"/api/household/{household_id}",
        json={"tasks_only_assignee_can_complete": True},
    )
    t = create(c, household_id, name="x").get_json()
    switch_to_second(c)
    assert (
        c.post(
            f"/api/tasks/{t['id']}/done", json={"expected_assigned_to": None}
        ).status_code
        == 200
    )


def test_household_switch_requires_admin(
    user_client_with_household, household_id, second_user
):
    switch_to_second(user_client_with_household)
    response = user_client_with_household.post(
        f"/api/household/{household_id}", json={"tasks_feature": True}
    )
    assert response.status_code == 403


def test_feature_defaults_off(user_client_with_household, household_id):
    h = user_client_with_household.get(f"/api/household/{household_id}").get_json()
    assert h["tasks_feature"] is False
    assert h["tasks_only_assignee_can_complete"] is False


def test_tasks_not_accessible_for_other_households(
    user_client_with_household,
    household_id,
    admin_username,
    admin_password,
    username,
    password,
):
    c = user_client_with_household
    t = create(c, household_id, name="x").get_json()
    # a user without membership
    login(c, admin_username, admin_password)
    response = c.post(
        "/api/user/new", json={"username": "stranger", "name": "S", "password": "pw"}
    )
    assert response.status_code == 200
    login(c, "stranger", "pw")
    assert c.get(f"/api/tasks/{t['id']}").status_code == 403
    assert (
        c.post(
            f"/api/tasks/{t['id']}/done", json={"expected_assigned_to": None}
        ).status_code
        == 403
    )
    assert c.delete(f"/api/tasks/{t['id']}").status_code == 403
    assert c.get(f"/api/household/{household_id}/tasks").status_code == 403


# --- member removal -----------------------------------------------------------------


def test_member_removal_updates_rotation(
    user_client_with_household, household_id, me, second_user
):
    c = user_client_with_household
    t = create(
        c,
        household_id,
        name="x",
        recurring=True,
        rotation_mode="ordered",
        participants=[second_user, me],
        assigned_to=second_user,
    ).get_json()
    fixed = create(c, household_id, name="fixed", assigned_to=second_user).get_json()

    assert (
        c.delete(f"/api/household/{household_id}/member/{second_user}").status_code
        == 200
    )

    data = c.get(f"/api/tasks/{t['id']}").get_json()
    # a rotation needs two participants: falls back to a fixed assignment
    assert data["rotation_mode"] == "none"
    assert data["participants"] == []
    assert data["assigned_to"] == me
    assert c.get(f"/api/tasks/{fixed['id']}").get_json()["assigned_to"] is None


def test_member_removal_keeps_rotation_with_three(
    user_client_with_household,
    household_id,
    me,
    second_user,
    admin_username,
    admin_password,
    username,
    password,
):
    c = user_client_with_household
    login(c, admin_username, admin_password)
    c.post("/api/user/new", json={"username": "third", "name": "T", "password": "pw"})
    login(c, "third", "pw")
    third = c.get("/api/user").get_json()["id"]
    login(c, username, password)
    c.put(f"/api/household/{household_id}/member/{third}", json={"admin": False})

    t = create(
        c,
        household_id,
        name="x",
        recurring=True,
        rotation_mode="ordered",
        participants=[me, second_user, third],
        assigned_to=second_user,
    ).get_json()
    c.delete(f"/api/household/{household_id}/member/{second_user}")
    data = c.get(f"/api/tasks/{t['id']}").get_json()
    assert data["rotation_mode"] == "ordered"
    assert data["participants"] == [me, third]
    # the successor takes over
    assert data["assigned_to"] == third


def test_user_deletion_clears_references(
    user_client_with_household,
    household_id,
    me,
    second_user,
    admin_username,
    admin_password,
    username,
    password,
):
    c = user_client_with_household
    switch_to_second(c)
    t = create(
        c, household_id, name="x", recurring=True, assigned_to=second_user
    ).get_json()
    c.post(f"/api/tasks/{t['id']}/done", json={"expected_assigned_to": second_user})
    login(c, admin_username, admin_password)
    assert c.delete(f"/api/user/{second_user}").status_code == 200
    login(c, username, password)
    data = c.get(f"/api/tasks/{t['id']}").get_json()
    assert data["assigned_to"] is None
    assert data["created_by"] is None
    history = c.get(f"/api/household/{household_id}/tasks/completions").get_json()
    assert history[0]["done_by"] is None
