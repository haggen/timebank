from sqlalchemy import (
    Column,
    Text,
    Integer,
    Float,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    selectinload,
    sessionmaker,
    UOWTransaction,
    Session as SyncSession,
)
from sqlalchemy.future import select
from sqlalchemy.event import listens_for
from datetime import datetime

import config

Base = declarative_base()
engine = create_async_engine(str(config.DATABASE_URL), echo=True, future=True)
Session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Organization(Base):
    __tablename__ = "organizations"

    default_settings = {
        "expires_in": 90,
        "holiday_multiplier": 1.0,
        "holiday_calendar": "",
    }

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    domain = Column(Text, nullable=False, unique=True, index=True)
    settings = Column(JSONB, nullable=False, default=default_settings)
    accounts = relationship("Account", back_populates="organization")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    organization_id = Column(None, ForeignKey("organizations.id"))
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    active = Column(Boolean, nullable=False, default=True)
    role = Column(Text, nullable=False, default="employee")
    email = Column(Text, nullable=False, unique=True, index=True)
    name = Column(Text, nullable=False)
    picture = Column(Text)
    organization = relationship("Organization", back_populates="accounts")
    entries = relationship("Entry", back_populates="account")


class Entry(Base):
    __tablename__ = "entries"

    id = Column(Integer, primary_key=True)
    account_id = Column(None, ForeignKey("accounts.id"))
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    happened_on = Column(Date, nullable=False, index=True)
    expires_on = Column(Date, nullable=False, index=True)
    value = Column(Integer, nullable=False)
    residue = Column(Integer, nullable=False)
    multiplier = Column(Float, nullable=False)
    account = relationship("Account", back_populates="entries")

    @classmethod
    def recalculate_residue(self, session: Session, entry: "Entry"):
        if entry.residue == 0:
            return

        involved_entries = session.scalars(
            select(Entry)
            .where(
                Entry.account_id == entry.account_id,
                Entry.expires_on > entry.happened_on,
                Entry.residue < 0 if entry.residue > 0 else Entry.residue > 0,
            )
            .order_by(Entry.happened_on, Entry.created_at)
        )

        for ie in involved_entries:
            residue = ie.residue + entry.residue

            if (residue > 0) == (ie.residue > 0):
                ie.residue = residue
                entry.residue = 0
                break
            else:
                ie.residue = 0
                entry.residue = residue


@listens_for(SyncSession, "before_flush")
def recalculate_residue(session: Session, flush_context: UOWTransaction, instances):
    for instance in session.new:
        if isinstance(instance, Entry):
            Entry.recalculate_residue(session, instance)

    for instance in session.dirty:
        if isinstance(instance, Entry):
            Entry.recalculate_residue(session, instance)
