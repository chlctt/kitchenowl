from marshmallow import fields, Schema, EXCLUDE


class GetShoppingLists(Schema):
    orderby = fields.Integer()
    recent_limit = fields.Integer(load_default=9, validate=lambda x: x > 0 and x <= 120)


class AddItemByName(Schema):
    name = fields.String(required=True)
    description = fields.String()
    # Automatische Erkennung von "@name" und Datum im Text unterdrücken
    parse_annotations = fields.Boolean(load_default=True)


class AddRecipeItems(Schema):
    class RecipeItem(Schema):
        class Meta:
            unknown = EXCLUDE

        id = fields.Integer(required=True)
        name = fields.String(required=True, validate=lambda a: a and not a.isspace())
        description = fields.String(load_default="")
        optional = fields.Boolean(load_default=True)

    items = fields.List(fields.Nested(RecipeItem))


class CreateList(Schema):
    name = fields.String(required=True, validate=lambda a: a and not a.isspace())


class UpdateList(Schema):
    name = fields.String(validate=lambda a: a and not a.isspace())


class GetItems(Schema):
    orderby = fields.Integer()


class GetRecentItems(Schema):
    # Align deprecated endpoint limit with list endpoint (<=120)
    limit = fields.Integer(load_default=9, validate=lambda x: x > 0 and x <= 120)


class UpdateDescription(Schema):
    description = fields.String(required=True)
    # Explizite Zuweisung / Datum von der Detailseite.
    # Feld weglassen = unverändert lassen; null = zurücksetzen.
    assigned_to = fields.Integer(allow_none=True)
    due_date = fields.Date(allow_none=True)
    # Bei true wird die Beschreibung zusätzlich nach "@name"/Datum durchsucht
    parse_annotations = fields.Boolean(load_default=False)


class RemoveItem(Schema):
    item_id = fields.Integer(
        required=True,
    )
    removed_at = fields.Integer()


class RemoveItems(Schema):
    class RecipeItem(Schema):
        class Meta:
            unknown = EXCLUDE

        item_id = fields.Integer(
            required=True,
        )
        removed_at = fields.Integer()

    items = fields.List(fields.Nested(RecipeItem))
