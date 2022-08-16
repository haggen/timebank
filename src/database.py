from databases import Database
from typing import Literal

import datetime
import config
import json

# Create database instance.
database = Database(config.DATABASE_URL)


organization_default_settings = json.dumps(
    {
        "expires_in": 90,
        "holiday_multiplier": 1.0,
        "holiday_calendar": "",
    }
)


async def create_organization(domain: str):
    return await database.fetch_one(
        query="""
            INSERT INTO organizations (domain, settings) 
            VALUES (:domain, :settings) RETURNING *
        """,
        values={"domain": domain, "settings": organization_default_settings},
    )


async def find_organization(id: int = None, domain: str = None):
    if domain:
        return await database.fetch_one(
            query="SELECT * FROM organizations WHERE domain = :domain LIMIT 1",
            values={"domain": domain},
        )
    return await database.fetch_one(
        query="SELECT * FROM organizations WHERE id = :id LIMIT 1",
        values={"id": id},
    )


async def create_account(
    organization_id: int,
    email: str,
    name: str,
    role: Literal["employee", "manager"],
    picture: str = None,
):
    return await database.fetch_one(
        query="""
            INSERT INTO accounts (organization_id, email, name, role, picture) 
            VALUES (:organization_id, :email, :name, :role, :picture) RETURNING *
        """,
        values={
            "organization_id": organization_id,
            "email": email,
            "name": name,
            "role": role,
            "picture": picture,
        },
    )


async def find_account(id: int = None, email: str = None):
    if email:
        return await database.fetch_one(
            query="SELECT * FROM accounts WHERE email = :email LIMIT 1",
            values={"email": email},
        )
    return await database.fetch_one(
        query="SELECT * FROM accounts WHERE id = :id LIMIT 1",
        values={"id": id},
    )


async def find_authenticated_user(email: str = None):
    return await database.fetch_one(
        query="""
            SELECT accounts.*, domain, settings FROM accounts 
            JOIN organizations ON organizations.id = organization_id
            WHERE email = :email AND active LIMIT 1
        """,
        values={"email": email},
    )


async def create_entry(
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
            values=({"residue": e.residue, "id": e.id} for e in entries if e.changed),
        )


async def find_entries():
    return await database.fetch_all(
        query="SELECT * FROM entries ORDER BY happened_on DESC, created_at DESC",
    )
