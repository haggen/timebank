create table if not exists employees (
    id serial primary key,
    name text not null
);
create table if not exists entries (
    id serial primary key,
    created_at timestamptz not null default now(),
    employee_id integer not null,
    happened_on date not null,
    expires_on date not null,
    value integer not null,
    balance integer not null
);