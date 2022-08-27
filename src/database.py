from sqlalchemy import (
    Column,
    Text,
    Integer,
    Float,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    column_property,
    sessionmaker,
    UOWTransaction,
    Session as SyncSession,
)
from sqlalchemy.future import select
from sqlalchemy.event import listens_for
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method

from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request

import datetime
import config

# Base model.
Base = declarative_base()

# Database engine.
engine = create_async_engine(str(config.DATABASE_URL), echo=True, future=True)

# Database session.
Session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def all(self, query):
    """
    Shortcut to (await session.scalars(query)).all().
    """
    return (await self.scalars(query)).all()


AsyncSession.all = all


class DatabaseMiddleware:
    """
    Begin a database session per request and handle commit/rollback.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not scope["type"] in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        if not "state" in scope:
            scope["state"] = {}

        async with Session() as session:
            async with session.begin():
                scope["state"]["database"] = session

                try:
                    await self.app(scope, receive, send)
                except:
                    await session.rollback()
                    raise
                else:
                    await session.commit()


Request.db = property(lambda self: self.state.database, doc="Database session.")


class Organization(Base):
    """
    Organization model.
    """

    __tablename__ = "organizations"

    # Organizations default settings.
    # - `expires_in` is the expiration window for new entries, in days.
    # - `holiday_multiplier` is the factor by which the value of entries that happened on holidays are multiplied by.
    # - `holiday_calendar` is the identifier of the calendar in Google Calendar that holds holidays.
    default_settings = {
        "expires_in": 90,
        "holiday_multiplier": 1.0,
        "holiday_calendar": "",
    }

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now)
    domain = Column(Text, nullable=False, unique=True, index=True)
    settings = Column(JSONB, nullable=False, default=default_settings)
    accounts = relationship("Account", back_populates="organization")


class Account(Base):
    """
    Account model.
    """

    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    organization_id = Column(None, ForeignKey("organizations.id"))
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now)
    active = Column(Boolean, nullable=False, default=True)
    role = Column(Text, nullable=False, default="employee")
    email = Column(Text, nullable=False, unique=True, index=True)
    name = Column(Text, nullable=False)
    picture = Column(Text)
    organization = relationship("Organization", back_populates="accounts")
    entries = relationship("Entry", back_populates="account")
    is_manager = column_property(role == "manager")

    @property
    def is_authenticated(self):
        return bool(self.id)

    @property
    def display_name(self):
        return self.name

    @hybrid_method
    def expiring_balance(self):
        raise NotImplemented

    @expiring_balance.expression
    def expiring_balance(self, a, b):
        return func.coalesce(
            func.sum(Entry.residue).filter(
                Entry.not_expired, Entry.expires_on >= a, Entry.expires_on < b
            ),
            0,
        ).label("expiring_balance")

    @hybrid_method
    def of_organization(self, organization_id: int):
        return self.organization_id == organization_id

    @hybrid_property
    def by_name(self):
        return (self.active.desc(), self.name)


class Entry(Base):
    """
    Entry model.
    """

    __tablename__ = "entries"

    id = Column(Integer, primary_key=True)
    account_id = Column(None, ForeignKey("accounts.id"))
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now)
    happened_on = Column(Date, nullable=False, index=True)
    expires_on = Column(Date, nullable=False, index=True)
    value = Column(Integer, nullable=False)
    residue = Column(Integer, nullable=False)
    multiplier = Column(Float, nullable=False)
    account = relationship("Account", back_populates="entries")

    @hybrid_method
    def of_account(self, account_id: int):
        return self.account_id == account_id

    @hybrid_property
    def is_expired(self):
        return self.expires_on < datetime.date.today()

    @hybrid_property
    def has_residue(self):
        return self.residue != 0

    @hybrid_property
    def not_expired(self):
        return self.expires_on >= datetime.date.today()

    @hybrid_property
    def active(self):
        return self.has_residue and self.not_expired

    @active.expression
    def active(self):
        return self.has_residue & self.not_expired

    @hybrid_property
    def by_date(self):
        return (self.happened_on.desc(), self.created_at.desc())

    @hybrid_property
    def by_expiration(self):
        return (self.expires_on, self.created_at)

    def recalculate_residue(self, session: Session):
        """
        Recalculate entry's residue.
        """

        if self.residue == 0:
            return

        entries = session.scalars(
            select(Entry)
            .where(
                Entry.account_id == self.account_id,
                Entry.happened_on < self.expires_on,
                Entry.expires_on > self.happened_on,
                Entry.residue < 0 if self.residue > 0 else Entry.residue > 0,
            )
            .order_by(Entry.happened_on, Entry.created_at)
        )

        for entry in entries:
            residue = entry.residue + self.residue

            if (residue > 0) == (entry.residue > 0):
                entry.residue, self.residue = residue, 0
                break

            entry.residue, self.residue = 0, residue


@listens_for(SyncSession, "before_flush")
def recalculate_residue(session: Session, flush_context: UOWTransaction, instances):
    """
    Recalculate residue for all created or changed entries.
    """

    for instance in session.new:
        if isinstance(instance, Entry):
            instance.recalculate_residue(session)

    for instance in session.dirty:
        if isinstance(instance, Entry):
            instance.recalculate_residue(session)


Account.balance = column_property(
    func.coalesce(func.sum(Entry.residue).filter(Entry.active), 0).label("balance"),
    deferred=True,
    raiseload=True,
)
