CREATE TABLE organizations IF NOT EXISTS (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    domain TEXT NOT NULL UNIQUE,
);

CREATE TABLE accounts IF NOT EXISTS (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    picture_url TEXT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'employee',
);

CREATE TABLE entries IF NOT EXISTS (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    happened_on DATE NOT NULL,
    expires_on DATE NOT NULL,
    value INTEGER NOT NULL,
    residue INTEGER NOT NULL,
    multiplier INTEGER NOT NULL,
);