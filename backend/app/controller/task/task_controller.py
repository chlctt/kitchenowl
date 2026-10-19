from datetime import date, datetime, timezone

from flask import jsonify, Blueprint
from flask_jwt_extended import jwt_required, current_user

from app import db
from app.errors import ForbiddenRequest, InvalidUsage, NotFoundRequest
from app.helpers import validate_args, authorize_household
from app.models import Household, HouseholdMember, Task, TaskCompletion
from app.service.task import (
    MAX_REPEAT_EVERY,
    add_interval,
    next_assignee,
    next_due_date,
    renumber_participants,
    today_from_client,
)
from .schemas import (
    AddTask,
    DoneTask,
    GetTaskCompletions,
    GetTasks,
    UpdateTask,
)

taskHousehold = Blueprint("task", __name__)
task = Blueprint("task_by_id", __name__)


def millis_to_date(millis: int) -> date:
    try:
        return datetime.fromtimestamp(millis / 1000, timezone.utc).date()
    except OverflowError, OSError, ValueError:
        raise InvalidUsage("Invalid date")


def is_household_admin(household_id: int) -> bool:
    if current_user.admin:
        return True
    member = HouseholdMember.find_by_ids(household_id, current_user.id)
    return bool(member and (member.admin or member.owner))


def check_members(household_id: int, user_ids: list[int]) -> None:
    for user_id in user_ids:
        if not HouseholdMember.find_by_ids(household_id, user_id):
            raise InvalidUsage("User is not a member of the household")


def validate_and_apply(
    household_id: int, task: Task, args: dict, participants: list[int] | None
) -> None:
    """Validate the combination of fields (against the values the task will have
    after the update) and apply the participants."""
    if task.repeat_every is not None or task.repeat_unit is not None:
        if task.repeat_every is None or task.repeat_unit is None:
            raise InvalidUsage("repeat_every and repeat_unit must be set together")
        if task.repeat_every > MAX_REPEAT_EVERY[task.repeat_unit]:
            raise InvalidUsage("repeat_every is too large")
        if not task.recurring or task.due_date is None:
            raise InvalidUsage("A repeat interval requires recurring and a due date")

    if task.assigned_to is not None:
        check_members(household_id, [task.assigned_to])

    if task.rotation_mode == "none":
        if participants is not None or task.participants:
            renumber_participants(task, [])
    else:
        ids = (
            participants
            if participants is not None
            else [p.user_id for p in task.participants]
        )
        if len(ids) < 2 or len(set(ids)) != len(ids):
            raise InvalidUsage("A rotation needs at least two distinct participants")
        check_members(household_id, ids)
        if participants is not None:
            renumber_participants(task, ids)
        if task.assigned_to not in ids:
            task.assigned_to = ids[0]


def apply_fields(task: Task, args: dict) -> None:
    if "name" in args:
        task.name = args["name"].strip()
    if "recurring" in args:
        task.recurring = args["recurring"]
        if not task.recurring:
            task.repeat_every = None
            task.repeat_unit = None
    if "due_date" in args:
        task.due_date = (
            millis_to_date(args["due_date"]) if args["due_date"] is not None else None
        )
        if task.due_date is None:
            task.repeat_every = None
            task.repeat_unit = None
    if "repeat_every" in args:
        task.repeat_every = args["repeat_every"]
    if "repeat_unit" in args:
        task.repeat_unit = args["repeat_unit"]
    if "rotation_mode" in args:
        task.rotation_mode = args["rotation_mode"]
    if "assigned_to" in args:
        task.assigned_to = args["assigned_to"]


@taskHousehold.route("", methods=["GET"])
@jwt_required()
@authorize_household()
@validate_args(GetTasks)
def getAllTasks(args, household_id):
    tasks = Task.all_from_household(household_id, args["completed"])
    return jsonify([t.obj_to_full_dict() for t in tasks])


@taskHousehold.route("", methods=["POST"])
@jwt_required()
@authorize_household()
@validate_args(AddTask)
def addTask(args, household_id):
    t = Task()
    t.household_id = household_id
    t.created_by = current_user.id
    t.name = args["name"].strip()
    t.recurring = False
    t.rotation_mode = "none"
    apply_fields(t, args)
    db.session.add(t)
    try:
        validate_and_apply(household_id, t, args, args["participants"])
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return jsonify(t.obj_to_full_dict())


@task.route("/<int:id>", methods=["GET"])
@jwt_required()
def getTaskById(id):
    t = Task.find_by_id(id)
    if not t:
        raise NotFoundRequest()
    t.checkAuthorized()
    return jsonify(t.obj_to_full_dict())


@task.route("/<int:id>", methods=["POST"])
@jwt_required()
@validate_args(UpdateTask)
def updateTask(args, id):
    t = Task.find_by_id(id)
    if not t:
        raise NotFoundRequest()
    t.checkAuthorized()
    household = Household.find_by_id(t.household_id)
    if (
        "assigned_to" in args
        and args["assigned_to"] != t.assigned_to
        and household
        and household.tasks_only_assignee_can_complete
        and t.assigned_to is not None
        and t.assigned_to != current_user.id
        and not is_household_admin(t.household_id)
    ):
        raise ForbiddenRequest()
    if t.completed_at is not None:
        if "completed" not in args or args["completed"]:
            raise InvalidUsage("Task is completed")
        t.completed_at = None
    elif args.get("completed"):
        raise InvalidUsage("Use /done to complete a task")

    try:
        apply_fields(t, args)
        validate_and_apply(t.household_id, t, args, args.get("participants"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return jsonify(t.obj_to_full_dict())


@task.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def deleteTaskById(id):
    t = Task.find_by_id(id)
    if not t:
        raise NotFoundRequest()
    t.checkAuthorized()
    t.delete()
    return jsonify({"msg": "DONE"})


@task.route("/<int:id>/done", methods=["POST"])
@jwt_required()
@validate_args(DoneTask)
def doneTask(args, id):
    t = Task.find_by_id(id)
    if not t:
        raise NotFoundRequest()
    t.checkAuthorized()
    household = Household.find_by_id(t.household_id)
    if (
        household
        and household.tasks_only_assignee_can_complete
        and t.assigned_to is not None
        and t.assigned_to != current_user.id
        and not is_household_admin(t.household_id)
    ):
        raise ForbiddenRequest()
    if t.completed_at is not None:
        raise InvalidUsage("Task is already completed")
    if args["expected_assigned_to"] != t.assigned_to:
        return jsonify({"msg": "Task was changed", "task": t.obj_to_full_dict()}), 409

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today = today_from_client(
        millis_to_date(args["done_on"]) if "done_on" in args else None
    )
    try:
        db.session.add(
            TaskCompletion(
                task_id=t.id,
                household_id=t.household_id,
                task_name=t.name,
                done_by=current_user.id,
                done_at=now,
                previous_assigned_to=t.assigned_to,
            )
        )
        t.last_done_at = now
        if not t.recurring:
            t.completed_at = now
        else:
            t.assigned_to = next_assignee(t)
            if t.due_date is not None and t.repeat_every and t.repeat_unit:
                try:
                    t.due_date = next_due_date(
                        t.due_date, t.repeat_every, t.repeat_unit, today
                    )
                except OverflowError, ValueError:
                    raise InvalidUsage("Due date out of range")
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return jsonify(t.obj_to_full_dict())


@taskHousehold.route("/completions", methods=["GET"])
@jwt_required()
@authorize_household()
@validate_args(GetTaskCompletions)
def getTaskCompletions(args, household_id):
    completions = TaskCompletion.all_from_household(household_id, args["page"])
    return jsonify([c.obj_to_dict() for c in completions])
