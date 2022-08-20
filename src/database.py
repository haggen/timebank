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
from sqlalchemy.orm import declarative_base, relationship, selectinload, sessionmaker
from sqlalchemy.future import select
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
    async def create(self, session: AsyncSession, **values):
        entry = Entry(**values)
        session.add(entry)

        entries = (
            await session.scalars(
                select(Entry)
                .where(
                    Entry.account_id == entry.account_id,
                    Entry.expires_on > entry.happened_on,
                    Entry.residue != 0,
                )
                .order_by(Entry.happened_on, Entry.id)
            )
        ).all()

        for a in entries:
            # If there's no residue, skip.
            if a.residue == 0:
                continue

            # For each entry a we're checking if entry b should've changed it.
            for b in entries:
                # If they're the same entry, skip.
                if a == b:
                    continue

                # If entry b happened after entry a expires, then we're done with entry a.
                if a.expires_on < b.happened_on:
                    break

                # If they're the same type, skip.
                if (a.residue > 0) == (b.residue > 0):
                    continue

                # Calculate new residue.
                residue = a.residue + b.residue

                # If new residue has the same sign as entry a, then entry a must still has residue left.
                if residue > 0:
                    b.residue = 0
                    a.residue = residue
                # Otherwise entry b still has residue left.
                else:
                    b.residue = residue
                    a.residue = 0

        session.commit()
