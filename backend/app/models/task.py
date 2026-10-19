from __future__ import annotations
from typing import Any, Self, List, TYPE_CHECKING, cast
from datetime import date, datetime, timezone
from app import db
from app.helpers import DbModelAuthorizeMixin
from sqlalchemy.orm import Mapped

Model = db.Model
if TYPE_CHECKING:
    from app.models import Household, User
    from app.helpers.db_model_base import DbModelBase

    Model = DbModelBase


def date_to_millis(d: date | None) -> int | None:
    if d is None:
        return None
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


class Task(Model, DbModelAuthorizeMixin):
    __tablename__ = "task"

    id: Mapped[int] = db.Column(db.Integer, primary_key=True)
    household_id: Mapped[int] = db.Column(
        db.Integer, db.ForeignKey("household.id"), nullable=False, index=True
    )
    name: Mapped[str] = db.Column(db.String(128), nullable=False)
    recurring: Mapped[bool] = db.Column(db.Boolean(), nullable=False, default=False)
    due_date: Mapped[date | None] = db.Column(db.Date())
    repeat_every: Mapped[int | None] = db.Column(db.Integer())
    repeat_unit: Mapped[str | None] = db.Column(db.String(16))
    rotation_mode: Mapped[str] = db.Column(
        db.String(16), nullable=False, default="none"
    )
    assigned_to: Mapped[int | None] = db.Column(
        db.Integer, db.ForeignKey("user.id"), index=True
    )
    created_by: Mapped[int | None] = db.Column(db.Integer, db.ForeignKey("user.id"))
    completed_at: Mapped[datetime | None] = db.Column(db.DateTime())
    last_done_at: Mapped[datetime | None] = db.Column(db.DateTime())

    household: Mapped["Household"] = cast(
        Mapped["Household"],
        db.relationship("Household", back_populates="tasks"),
    )
    participants: Mapped[List["TaskParticipant"]] = cast(
        Mapped[List["TaskParticipant"]],
        db.relationship(
            "TaskParticipant",
            back_populates="task",
            cascade="all, delete-orphan",
            order_by="TaskParticipant.position",
        ),
    )
    completions: Mapped[List["TaskCompletion"]] = cast(
        Mapped[List["TaskCompletion"]],
        db.relationship(
            "TaskCompletion",
            back_populates="task",
            cascade="all, delete-orphan",
        ),
    )

    def obj_to_dict(
        self,
        skip_columns: list[str] | None = None,
        include_columns: list[str] | None = None,
    ) -> dict[str, Any]:
        res = super().obj_to_dict(skip_columns, include_columns)
        res["due_date"] = date_to_millis(self.due_date)
        return res

    def obj_to_full_dict(self) -> dict[str, Any]:
        res = self.obj_to_dict()
        res["participants"] = [p.user_id for p in self.participants]
        return res

    @classmethod
    def all_from_household(
        cls, household_id: int, completed: bool = False
    ) -> list[Self]:
        query = cls.query.filter(cls.household_id == household_id)
        if completed:
            query = query.filter(cls.completed_at.isnot(None))
        else:
            query = query.filter(cls.completed_at.is_(None))
        return query.order_by(cls.name).all()

    @classmethod
    def remove_user(cls, household_id: int | None, user_id: int) -> None:
        """
        Remove a user from all tasks (of one household, or of all households if
        household_id is None): participants are removed and renumbered,
        the assignment moves on, authorship references are cleared.
        Commits the session.
        """
        from app.service.task import remove_user_from_task

        query = cls.query
        if household_id is not None:
            query = query.filter(cls.household_id == household_id)
        for task in query.all():
            remove_user_from_task(task, user_id)
        for t in cls.query.filter(cls.created_by == user_id).all():
            t.created_by = None
        for c in TaskCompletion.query.filter(TaskCompletion.done_by == user_id).all():
            c.done_by = None
        db.session.commit()


class TaskParticipant(Model):
    __tablename__ = "task_participant"

    task_id: Mapped[int] = db.Column(
        db.Integer, db.ForeignKey("task.id"), primary_key=True
    )
    user_id: Mapped[int] = db.Column(
        db.Integer, db.ForeignKey("user.id"), primary_key=True, index=True
    )
    position: Mapped[int] = db.Column(db.Integer, nullable=False)

    task: Mapped["Task"] = cast(
        Mapped["Task"], db.relationship("Task", back_populates="participants")
    )


class TaskCompletion(Model):
    __tablename__ = "task_completion"

    id: Mapped[int] = db.Column(db.Integer, primary_key=True)
    task_id: Mapped[int] = db.Column(
        db.Integer, db.ForeignKey("task.id"), nullable=False, index=True
    )
    household_id: Mapped[int] = db.Column(
        db.Integer, db.ForeignKey("household.id"), nullable=False, index=True
    )
    task_name: Mapped[str] = db.Column(db.String(128), nullable=False)
    done_by: Mapped[int | None] = db.Column(db.Integer, db.ForeignKey("user.id"))
    done_at: Mapped[datetime] = db.Column(
        db.DateTime(), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    previous_assigned_to: Mapped[int | None] = db.Column(db.Integer)

    task: Mapped["Task"] = cast(
        Mapped["Task"], db.relationship("Task", back_populates="completions")
    )

    @classmethod
    def all_from_household(
        cls, household_id: int, page: int = 0, page_size: int = 50
    ) -> list[Self]:
        return (
            cls.query.filter(cls.household_id == household_id)
            .order_by(cls.done_at.desc(), cls.id.desc())
            .offset(page * page_size)
            .limit(page_size)
            .all()
        )
