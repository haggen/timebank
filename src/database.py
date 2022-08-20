from databases import Database
from typing import Literal
from sqlalchemy import (
    MetaData,
    Table,
    Column,
    String,
    Text,
    Integer,
    Float,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, date

import typing
import config
import json

database = Database(config.DATABASE_URL)

metadata = MetaData()


class ModelType(type):
    def __getattr__(self, name: str):
        if name in self.table.columns:
            return self.table.columns[name]
        return self.__dict__[name]


class Model:
    table = None

    @classmethod
    async def create(self, **values):
        return await database.fetch_one(self.table.insert(values).returning(self.table))

    @classmethod
    async def get(self, *args):
        return await database.fetch_one(self.table.select().where(*args))


class Organization(Model, metaclass=ModelType):
    default_settings = {
        "expires_in": 90,
        "holiday_multiplier": 1.0,
        "holiday_calendar": "",
    }

    table = Table(
        "organizations",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("created_at", DateTime, nullable=False, default=datetime.now),
        Column("domain", Text, nullable=False, unique=True, index=True),
        Column("settings", JSONB, nullable=False),
    )


class Account(Model, metaclass=ModelType):
    table = table = Table(
        "accounts",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("organization_id", None, ForeignKey("organizations.id")),
        Column("created_at", DateTime, nullable=False, default=datetime.now),
        Column("active", Boolean, nullable=False, default=True),
        Column("role", Text, nullable=False, default="employee"),
        Column("email", Text, nullable=False, unique=True, index=True),
        Column("name", Text, nullable=False),
        Column("picture", Text),
    )

    @classmethod
    async def get(self, *args):
        account = await super().get(*args)
        if not account:
            return None
        account.organization = await Organization.get(
            Organization.id == account.organization_id
        )
        return account


class Entry(Model, metaclass=ModelType):
    @classmethod
    async def create(
        self,
        account_id: int,
        happened_on: datetime.date,
        expires_on: datetime.date,
        value: int,
        multiplier: float,
    ):
        values = {
            "account_id": account_id,
            "happened_on": happened_on,
            "expires_on": expires_on,
            "value": value,
            "multiplier": multiplier,
        }

        async with database.transaction():
            await database.fetch_one(
                query="""
                    INSERT INTO entries (account_id, happened_on, expires_on, value, residue, multiplier)
                    VALUES (:account_id, :happened_on, :expires_on, :value, :value, :multiplier)
                    RETURNING *
                """,
                values=values,
            )

            entries = await database.fetch_all(
                query="""
                    SELECT id, happened_on, expires_on, residue
                    FROM entries 
                    WHERE account_id = :account_id AND expires_on > :happened_on AND residue != 0 
                    ORDER BY happened_on;
                """,
                values={
                    "account_id": account_id,
                    "happened_on": happened_on,
                },
            )

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

                    # Flag for update.
                    a.changed = True
                    b.changed = True

            await database.execute_many(
                """
                UPDATE entries SET residue = :residue WHERE id = :id;
                """,
                values=(
                    {"residue": e.residue, "id": e.id} for e in entries if e.changed
                ),
            )

    @classmethod
    async def get(self):
        return await database.fetch_all(
            query="SELECT * FROM entries ORDER BY happened_on DESC, created_at DESC",
        )
