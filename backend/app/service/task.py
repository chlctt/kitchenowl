import calendar
import random
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app import db

if TYPE_CHECKING:
    from app.models import Task

ROTATION_MODES = ("none", "ordered", "random")
REPEAT_UNITS = ("day", "week", "month")
MAX_REPEAT_EVERY = {"day": 365, "week": 52, "month": 24}


def add_interval(start: date, every: int, unit: str) -> date:
    """Add a repeat interval to a date. Months are calendar months, the day is
    clamped to the last day of the target month."""
    if unit == "day":
        return start + timedelta(days=every)
    if unit == "week":
        return start + timedelta(weeks=every)
    if unit == "month":
        month_index = start.month - 1 + every
        year = start.year + month_index // 12
        month = month_index % 12 + 1
        day = min(start.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
    raise ValueError("Unknown repeat unit")


def next_due_date(due: date, every: int, unit: str, today: date) -> date:
    """New due date after completion: advance from the old due date, but never
    land in the past (no catching up on backlog)."""
    new = add_interval(due, every, unit)
    if new < today:
        new = add_interval(today, every, unit)
    return new


def today_from_client(done_on: date | None) -> date:
    """The client's local date, only trusted within one day of the server's UTC date."""
    server = datetime.now(timezone.utc).date()
    if done_on is None or abs((done_on - server).days) > 1:
        return server
    return done_on


def renumber_participants(task: "Task", user_ids: list[int]) -> None:
    """Replace the participants of a task, keeping the given order (position 0..n).
    Done by deleting and re-creating rows, so no transient position conflicts."""
    from app.models import TaskParticipant

    task.participants.clear()
    db.session.flush()
    for position, user_id in enumerate(user_ids):
        task.participants.append(TaskParticipant(user_id=user_id, position=position))


def next_assignee(task: "Task") -> int | None:
    """Next responsible user according to the rotation mode, or the current one
    if the task does not rotate."""
    ids = [p.user_id for p in task.participants]
    if task.rotation_mode == "none" or not ids:
        return task.assigned_to
    if task.rotation_mode == "random":
        candidates = [i for i in ids if i != task.assigned_to] or ids
        return random.choice(candidates)
    # ordered
    if task.assigned_to in ids:
        return ids[(ids.index(task.assigned_to) + 1) % len(ids)]
    return ids[0]


def remove_user_from_task(task: "Task", user_id: int) -> None:
    """Remove a user from a task's rotation and assignment (no commit)."""
    ids = [p.user_id for p in task.participants]
    was_assigned = task.assigned_to == user_id
    if user_id not in ids:
        if was_assigned:
            task.assigned_to = None
        return

    old_index = ids.index(user_id)
    remaining = [i for i in ids if i != user_id]
    if len(remaining) < 2:
        # a rotation needs at least two participants: fall back to a fixed assignment
        task.participants.clear()
        task.rotation_mode = "none"
        if was_assigned:
            task.assigned_to = remaining[0] if remaining else None
        return

    renumber_participants(task, remaining)
    if was_assigned:
        if task.rotation_mode == "random":
            task.assigned_to = random.choice(remaining)
        else:
            task.assigned_to = remaining[old_index % len(remaining)]
