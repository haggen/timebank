DROP TABLE IF EXISTS entries;

DROP TABLE IF EXISTS accounts;

DROP TABLE IF EXISTS organizations;

CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    domain TEXT NOT NULL UNIQUE,
    settings JSONB NOT NULL
);

CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    role TEXT NOT NULL DEFAULT 'employee',
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    picture TEXT
);

CREATE TABLE entries (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    happened_on DATE NOT NULL,
    expires_on DATE NOT NULL,
    value SMALLINT NOT NULL,
    residue SMALLINT NOT NULL,
    multiplier REAL NOT NULL
);