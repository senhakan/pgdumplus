-- testdb setup: --where and --mask validation
-- Usage: psql -U postgres -d testdb -f demo_setup.sql

\set ON_ERROR_STOP on
DROP DATABASE IF EXISTS testdb;
CREATE DATABASE testdb;

\c testdb

CREATE TABLE public.customers (
    id          serial PRIMARY KEY,
    name        text NOT NULL,
    ssn         varchar(11),
    phone       varchar(20),
    address     text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.events (
    id          bigserial PRIMARY KEY,
    customer_id int NOT NULL REFERENCES customers(id),
    payload     text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX events_created_idx ON events (created_at);

CREATE TABLE public.event_tags (
    event_id    bigint PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
    tag         text NOT NULL
);

CREATE TABLE public.audit_log (
    id          bigserial PRIMARY KEY,
    entity      text NOT NULL,
    action      text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- customers: 1,000 rows
INSERT INTO public.customers (name, ssn, phone, address)
SELECT 'customer-' || g,
       '1' || lpad((g * 7919 % 100000000000)::text, 11, '0'),
       '05' || lpad((g * 13 % 1000000000)::text, 9, '0'),
       'Address ' || (g % 50) || ', Street ' || (g % 300)
FROM generate_series(1, 1000) g;

-- events: 3,000,000 rows; ~720 in last 24 hours
INSERT INTO public.events (customer_id, payload, created_at)
SELECT (g % 1000) + 1,
       'payload-' || md5(g::text),
       now() - make_interval(mins => (3000000 - g) * 2)
FROM generate_series(1, 3000000) g;

-- event_tags: last 50,000 events
INSERT INTO public.event_tags (event_id, tag)
SELECT g, 'tag-' || (g % 97)
FROM generate_series(2950001, 3000000) g;

-- audit_log: 2,000,000 rows
INSERT INTO public.audit_log (entity, action, created_at)
SELECT 'entity-' || (g % 500),
       CASE WHEN g % 3 = 0 THEN 'update' ELSE 'insert' END,
       now() - make_interval(mins => (2000000 - g))
FROM generate_series(1, 2000000) g;

ANALYZE;

SELECT 'customers' AS table_name, count(*) FROM customers
UNION ALL SELECT 'events', count(*) FROM events
UNION ALL SELECT 'events_last_24h', count(*) FROM events WHERE created_at >= now() - interval '24 hours'
UNION ALL SELECT 'event_tags', count(*) FROM event_tags
UNION ALL SELECT 'audit_log', count(*) FROM audit_log;