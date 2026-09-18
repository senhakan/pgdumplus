# pg_dumpplus tutorials

These examples use disposable PostgreSQL data and the release binaries. Replace
the connection settings with your own environment; never use production data in
a tutorial copy. Filters select rows, while masks transform selected columns in
the dump. They do not guarantee referential completeness or anonymization.

## 1. Tenant subset

Create a dump for one tenant and its dependent rows. Keep the relationship
filters explicit so the result can be restored consistently.

```sh
pg_dumpplus-18 \
  --dbname=app \
  --where='public.customers:tenant_id = 42' \
  --where='public.orders:tenant_id = 42' \
  --where='public.order_items:order_id IN (SELECT id FROM public.orders WHERE tenant_id = 42)' \
  --format=custom --file=tenant-42.dump
```

## 2. Date-range export

Use a narrow predicate for a support or analytics extract. The expression is
sent to PostgreSQL as a row filter; validate it against the source schema first.

```sh
pg_dumpplus-18 \
  --dbname=app \
  --where='public.events:created_at >= TIMESTAMPTZ '\''2026-01-01 00:00:00+00'\'' AND created_at < TIMESTAMPTZ '\''2026-02-01 00:00:00+00'\'' ' \
  --format=directory --file=events-2026-01
```

For a shell without complex quoting, put the command in a script or use a
single-quoted SQL expression with escaped inner quotes.

## 3. Masked customer extract

Export a support extract while retaining only safe representations of contact
fields. Invalid or incompatible mask rules fail before table data is exported.

```sh
pg_dumpplus-18 \
  --dbname=app \
  --where='public.customers:id <= 1000' \
  --mask='public.customers:email:email' \
  --mask='public.customers:phone:phone' \
  --mask='public.customers:full_name:name' \
  --format=custom --file=customer-support.dump
```

Review the restored output and constraints before sharing it. Partial masking is
not a legal compliance claim, and custom SQL expressions remain trusted input.
