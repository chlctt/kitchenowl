from datetime import datetime
from typing import Any, Self, List, TYPE_CHECKING, cast
from app import db
from app.helpers import DbModelAuthorizeMixin
from sqlalchemy.orm import Mapped

Model = db.Model
if TYPE_CHECKING:
    from app.models import Household, History, Item, Shoppinglist, User
    from app.helpers.db_model_base import DbModelBase

    Model = DbModelBase


class Shoppinglist(Model, DbModelAuthorizeMixin):
    __tablename__ = "shoppinglist"

    id: Mapped[int] = db.Column(db.Integer, primary_key=True)
    name: Mapped[str] = db.Column(db.String(128))

    household_id: Mapped[int] = db.Column(
        db.Integer, db.ForeignKey("household.id"), nullable=False, index=True
    )

    household: Mapped["Household"] = cast(
        Mapped["Household"],
        db.relationship(
            "Household",
            uselist=False,
        ),
    )
    items: Mapped[List["ShoppinglistItems"]] = cast(
        Mapped[List["ShoppinglistItems"]],
        db.relationship(
            "ShoppinglistItems",
            cascade="all, delete-orphan",
        ),
    )

    history: Mapped[List["History"]] = cast(
        Mapped[List["History"]],
        db.relationship(
            "History",
            back_populates="shoppinglist",
            cascade="all, delete-orphan",
        ),
    )

    @classmethod
    def getDefault(cls, household_id: int) -> Self:
        return cast(
            Self,
            cls.query.filter(cls.household_id == household_id).order_by(cls.id).first(),
        )

    def isDefault(self) -> bool:
        return self.id == self.getDefault(self.household_id).id


class ShoppinglistItems(Model):
    __tablename__ = "shoppinglist_items"

    shoppinglist_id: Mapped[int] = db.Column(
        db.Integer, db.ForeignKey("shoppinglist.id"), primary_key=True
    )
    item_id: Mapped[int] = db.Column(
        db.Integer, db.ForeignKey("item.id"), primary_key=True
    )
    description: Mapped[str] = db.Column(db.String)
    created_by: Mapped[int | None] = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True
    )
    # Mitglied, dem dieser Artikel zugewiesen wurde (z.B. per "@name")
    assigned_to: Mapped[int | None] = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True
    )
    # Datum (UTC-Mitternacht), an dem der Artikel eingekauft werden soll.
    # Als DateTime gespeichert, weil der JSON-Provider nur datetime serialisiert.
    due_date: Mapped["datetime | None"] = db.Column(db.DateTime, nullable=True)

    item: Mapped["Item"] = cast(
        Mapped["Item"],
        db.relationship(
            "Item",
            back_populates="shoppinglists",
        ),
    )
    shoppinglist: Mapped["Shoppinglist"] = cast(
        Mapped["Shoppinglist"],
        db.relationship(
            "Shoppinglist",
            back_populates="items",
        ),
    )
    created_by_user: Mapped["User"] = cast(
        Mapped["User"],
        db.relationship(
            "User",
            foreign_keys=[created_by],
            uselist=False,
        ),
    )
    assigned_to_user: Mapped["User"] = cast(
        Mapped["User"],
        db.relationship(
            "User",
            foreign_keys=[assigned_to],
            uselist=False,
        ),
    )

    def obj_to_item_dict(self) -> dict[str, Any]:
        res = self.item.obj_to_dict()
        res["description"] = getattr(self, "description")
        res["created_at"] = getattr(self, "created_at")
        res["updated_at"] = getattr(self, "updated_at")
        res["created_by"] = getattr(self, "created_by")
        res["assigned_to"] = getattr(self, "assigned_to")
        res["due_date"] = getattr(self, "due_date")
        return res

    @classmethod
    def find_by_ids(cls, shoppinglist_id: int, item_id: int) -> Self | None:
        return cls.query.filter(
            cls.shoppinglist_id == shoppinglist_id, cls.item_id == item_id
        ).first()
