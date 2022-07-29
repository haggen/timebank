create table if not exists employees (
    id serial primary key,
    name text not null
);
create table if not exists entries (
    id serial primary key,
    employee_id integer not null,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    value integer not null,
    balance integer not null
);