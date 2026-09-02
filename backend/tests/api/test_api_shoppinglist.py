import pytest


def test_get_shopping_lists(user_client_with_household, household_id):
    response = user_client_with_household.get(
        f"/api/household/{household_id}/shoppinglist",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert "household_id" in data[0]
    assert data[0]["household_id"] == household_id
    assert "id" in data[0]
    assert "name" in data[0]


def test_add_item_by_name(user_client_with_household, shoppinglist_id, item_name):
    data = {"name": item_name}
    response = user_client_with_household.post(
        f"/api/shoppinglist/{shoppinglist_id}/add-item-by-name", json=data
    )
    assert response.status_code == 200


def test_get_items(user_client_with_household, shoppinglist_id_with_item, item_name):
    response = user_client_with_household.get(
        f"/api/shoppinglist/{shoppinglist_id_with_item}/items"
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert "name" in data[0]
    assert data[0]["name"] == item_name


def test_remove_item(user_client_with_household, shoppinglist_id_with_item, item_id):
    data = {"item_id": item_id}
    response = user_client_with_household.delete(
        f"/api/shoppinglist/{shoppinglist_id_with_item}/item", json=data
    )
    assert response.status_code == 200
    response = user_client_with_household.get(
        f"/api/shoppinglist/{shoppinglist_id_with_item}/items"
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 0


def _user_id(client):
    response = client.get("/api/user")
    assert response.status_code == 200
    return response.get_json()["id"]


def test_add_item_parses_assignee(user_client_with_household, shoppinglist_id, name):
    response = user_client_with_household.post(
        f"/api/shoppinglist/{shoppinglist_id}/add-item-by-name",
        json={"name": f"Milk @{name}"},
    )
    assert response.status_code == 200

    items = user_client_with_household.get(
        f"/api/shoppinglist/{shoppinglist_id}/items"
    ).get_json()
    assert len(items) == 1
    assert items[0]["name"] == "Milk"
    assert items[0]["assigned_to"] == _user_id(user_client_with_household)


def test_add_item_parses_due_date(user_client_with_household, shoppinglist_id):
    response = user_client_with_household.post(
        f"/api/shoppinglist/{shoppinglist_id}/add-item-by-name",
        json={"name": "Bread 2099-12-24"},
    )
    assert response.status_code == 200

    items = user_client_with_household.get(
        f"/api/shoppinglist/{shoppinglist_id}/items"
    ).get_json()
    assert items[0]["name"] == "Bread"
    assert items[0]["due_date"] is not None


def test_add_item_parse_annotations_disabled(user_client_with_household, shoppinglist_id):
    response = user_client_with_household.post(
        f"/api/shoppinglist/{shoppinglist_id}/add-item-by-name",
        json={"name": "Bread 2099-12-24", "parse_annotations": False},
    )
    assert response.status_code == 200
    items = user_client_with_household.get(
        f"/api/shoppinglist/{shoppinglist_id}/items"
    ).get_json()
    assert items[0]["name"] == "Bread 2099-12-24"
    assert items[0]["due_date"] is None


def test_update_item_sets_assignee_and_due_date(
    user_client_with_household, shoppinglist_id_with_item, item_id
):
    uid = _user_id(user_client_with_household)
    response = user_client_with_household.put(
        f"/api/shoppinglist/{shoppinglist_id_with_item}/item/{item_id}",
        json={"description": "1", "assigned_to": uid, "due_date": "2099-01-02"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["assigned_to"] == uid
    assert body["due_date"] is not None

    # null clears them again
    response = user_client_with_household.put(
        f"/api/shoppinglist/{shoppinglist_id_with_item}/item/{item_id}",
        json={"description": "1", "assigned_to": None, "due_date": None},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["assigned_to"] is None
    assert body["due_date"] is None
