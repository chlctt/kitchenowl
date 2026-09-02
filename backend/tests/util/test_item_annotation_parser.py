from datetime import date

import pytest

from app.util.item_annotation_parser import parse_item_annotations


class _FakeUser:
    def __init__(self, id: int, name: str, username: str):
        self.id = id
        self.name = name
        self.username = username


MEMBERS = [
    _FakeUser(1, "Sebastian Chilcott", "schilcott"),
    _FakeUser(2, "Anna Müller", "anna"),
]

REF = date(2026, 9, 2)  # Mittwoch


@pytest.mark.parametrize(
    "text,exp_name,exp_assignee,exp_due",
    [
        ("Milch", "Milch", None, None),
        ("Milch @anna", "Milch", 2, None),
        ("@anna Kaffee", "Kaffee", 2, None),
        ("Eier @sebastian", "Eier", 1, None),
        ("Tofu @chil", "Tofu", 1, None),  # unscharf
        ("Milch @unbekannt", "Milch @unbekannt", None, None),  # kein Treffer -> bleibt
        ("Brot 15.09", "Brot", None, date(2026, 9, 15)),
        ("Brot 15.9.2027", "Brot", None, date(2027, 9, 15)),
        ("Brot 2026-12-24", "Brot", None, date(2026, 12, 24)),
        ("Bananen morgen", "Bananen", None, date(2026, 9, 3)),
        ("Bananen übermorgen", "Bananen", None, date(2026, 9, 4)),
        ("Kaffee next monday", "Kaffee", None, date(2026, 9, 7)),
        ("Kaffee Freitag", "Kaffee", None, date(2026, 9, 4)),
        ("Wasser in 3 Tagen", "Wasser", None, date(2026, 9, 5)),
        ("Apfelsaft 20. Dezember", "Apfelsaft", None, date(2026, 12, 20)),
        ("2 Pizza @Anna am Freitag", "2 Pizza", 2, date(2026, 9, 4)),
        ("Salami am Stück", "Salami am Stück", None, None),
        ("tomatoes 09/15", "tomatoes", None, date(2026, 9, 15)),
    ],
)
def test_parse(text, exp_name, exp_assignee, exp_due):
    parsed = parse_item_annotations(text, MEMBERS, reference_date=REF)
    assert parsed.name == exp_name
    assert parsed.assigned_to_id == exp_assignee
    assert parsed.due_date == exp_due


def test_year_rolls_forward_for_past_dates():
    parsed = parse_item_annotations("Brot 01.01", MEMBERS, reference_date=REF)
    assert parsed.due_date == date(2027, 1, 1)


def test_description_is_scanned_but_not_returned_as_name():
    parsed = parse_item_annotations(
        "Milch", MEMBERS, description="2l @anna morgen", reference_date=REF
    )
    assert parsed.name == "Milch"
    assert parsed.assigned_to_id == 2
    assert parsed.due_date == date(2026, 9, 3)
