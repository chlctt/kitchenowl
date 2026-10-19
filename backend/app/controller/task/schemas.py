from marshmallow import fields, Schema, EXCLUDE, ValidationError
from marshmallow.validate import OneOf, Range

from app.service.task import ROTATION_MODES, REPEAT_UNITS


def validate_name(value: str) -> None:
    if not value.strip() or len(value) > 128:
        raise ValidationError("Name must not be empty and at most 128 characters")


class GetTasks(Schema):
    class Meta:
        unknown = EXCLUDE

    completed = fields.Boolean(load_default=False)


class AddTask(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(required=True, validate=validate_name)
    recurring = fields.Boolean(load_default=False)
    due_date = fields.Integer(allow_none=True)
    repeat_every = fields.Integer(allow_none=True, validate=Range(min=1))
    repeat_unit = fields.String(allow_none=True, validate=OneOf(REPEAT_UNITS))
    rotation_mode = fields.String(load_default="none", validate=OneOf(ROTATION_MODES))
    assigned_to = fields.Integer(allow_none=True)
    participants = fields.List(fields.Integer(), load_default=list)


class UpdateTask(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(validate=validate_name)
    recurring = fields.Boolean()
    due_date = fields.Integer(allow_none=True)
    repeat_every = fields.Integer(allow_none=True, validate=Range(min=1))
    repeat_unit = fields.String(allow_none=True, validate=OneOf(REPEAT_UNITS))
    rotation_mode = fields.String(validate=OneOf(ROTATION_MODES))
    assigned_to = fields.Integer(allow_none=True)
    participants = fields.List(fields.Integer())
    completed = fields.Boolean()


class DoneTask(Schema):
    class Meta:
        unknown = EXCLUDE

    # required: null means "expected to be open"
    expected_assigned_to = fields.Integer(required=True, allow_none=True)
    done_on = fields.Integer()


class GetTaskCompletions(Schema):
    class Meta:
        unknown = EXCLUDE

    page = fields.Integer(load_default=0, validate=Range(min=0))
