create table if not exists employees (
    id serial primary key,
    name text not null
);
create table if not exists entries (
    id serial primary key,
    employee_id integer not null,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    initial_value integer not null,
    spare_value integer not null
);