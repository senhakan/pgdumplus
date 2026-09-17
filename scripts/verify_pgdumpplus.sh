#!/usr/bin/env bash
# verify_pgdumpplus.sh — pg_dumpplus --where uctan uca test (postgres kullanicisi ile calisir).
# Kullanim: sudo -u postgres bash /var/tmp/pgdptest/verify_pgdumpplus.sh <pg_dumpplus> [pg_bin]
set -uo pipefail
PP=$1
PGBP=${2:-/usr/pgsql-17/bin}
export PATH="$PGBP:$PATH" PGCONNECT_TIMEOUT=10
OUT=$(mktemp -d /var/tmp/pgdptest.XXXX)
PASS=0; FAIL=0
chk() { if [[ "$2" == "$3" ]]; then echo "PASS: $1 (=$3)"; PASS=$((PASS+1)); else echo "FAIL: $1 beklenen=[$2] gercek=[$3]"; FAIL=$((FAIL+1)); fi; }
q() { psql -X -Aqt -d "$1" -c "$2" | tr -d '[:space:]'; }
restore_dir() { # <db> <Fc dosyasi|dizin>
  drop_create "$1" || return 1
  pg_restore -d "$1" --no-owner "$2"
}
drop_create() { # <db> -> psql ile (superuser, FORCE) — dropdb/createdb'in onay/izin tuzağı yok
  psql -X -q -v ON_ERROR_STOP=1 -d postgres -c "DROP DATABASE IF EXISTS \"$1\" WITH (FORCE)" \
      -c "CREATE DATABASE \"$1\"" || return 1
}

# Sabit zaman siniri (dump ile sayim ayni referansi kullansin; tirlak: SQL literal)
B=$(q testdb "SELECT replace((now() - make_interval(hours => 25))::timestamp(0)::text, ' ', 'T')")
NF="created_at >= '$B'::timestamp"   # pg_dump --where icine gidecek SQL (cift-tirnak icinde tek-tirnak litaraldir)
E24=$(q testdb "SELECT count(*) FROM events WHERE created_at >= '$B'::timestamp")
EALL=$(q testdb "SELECT count(*) FROM events")
AALL=$(q testdb "SELECT count(*) FROM audit_log")
TEG=$(q testdb "SELECT count(*) FROM event_tags et JOIN events e ON e.id=et.event_id WHERE e.created_at >= '$B'::timestamp")
CUS=$(q testdb "SELECT count(*) FROM customers")
echo "== beklenenler: bound=$B events25h=$E24 eventsAll=$EALL audit=$AALL tagsEsop=$TEG customers=$CUS =="

echo "=== 1) Tarih filtresi (son ~24s) -Fc + FK uyumlu baglam ==="
"$PP" -d testdb -Fc --no-owner \
  --where="public.events:$NF" \
  --where="public.event_tags:event_id IN (SELECT id FROM public.events WHERE $NF)" \
  -f "$OUT/test1.dump"
restore_dir test1 "$OUT/test1.dump"
chk "test1.events-filtreli" "$E24" "$(q test1 "SELECT count(*) FROM events")"
chk "test1.event_tags-filtreli" "$TEG" "$(q test1 'SELECT count(*) FROM event_tags')"
chk "test1.customers-tam" "$CUS" "$(q test1 'SELECT count(*) FROM customers')"
chk "test1.audit-tam" "$AALL" "$(q test1 'SELECT count(*) FROM audit_log')"
chk "test1.fk-orphan-yok" "0" "$(q test1 'SELECT count(*) FROM event_tags et LEFT JOIN events e ON e.id=et.event_id WHERE e.id IS NULL')"

echo "=== 2) Son 1.000.000 audit kaydi (id IN subquery, --inserts plain SQL) ==="
"$PP" -d testdb --no-owner --inserts --rows-per-insert=1000 \
  --where="public.audit_log:id IN (SELECT id FROM public.audit_log ORDER BY id DESC LIMIT 1000000)" \
  -f "$OUT/test2.sql"
drop_create test2
psql -X -q -v ON_ERROR_STOP=1 -d test2 -f "$OUT/test2.sql"
chk "test2.audit-1M" "1000000" "$(q test2 'SELECT count(*) FROM audit_log')"
chk "test2.events-tam" "$EALL" "$(q test2 'SELECT count(*) FROM events')"

echo "=== 3) Wildcard tablo deseni + -Fd paralel (-j 4) ==="
rm -rf "$OUT/test3.dir"; "$PP" -d testdb --no-owner -j 4 -Fd -f "$OUT/test3.dir" \
  --where="a*:id % 100 = 0"
restore_dir test3 "$OUT/test3.dir"
EXP=$(q testdb 'SELECT count(*) FROM audit_log WHERE id % 100 = 0')
chk "test3.audit-wildcard-mod" "$EXP" "$(q test3 'SELECT count(*) FROM audit_log')"

echo "=== 4) Vanilla pg_dump ile esdegerlik (filtresiz) ==="
pg_dump -d testdb --no-owner -Fc -f "$OUT/van0.dump"
"$PP" -d testdb --no-owner -Fc -f "$OUT/p0.dump"
restore_dir van0 "$OUT/van0.dump"; restore_dir p0 "$OUT/p0.dump"
chk "test4.satir-esitligi" "$(q van0 'SELECT count(*) FROM events')" "$(q p0 'SELECT count(*) FROM events')"
chk "test4.obje-sayisi" "$(q van0 "SELECT count(*) FROM pg_class WHERE relnamespace='public'::regnamespace")" "$(q p0 "SELECT count(*) FROM pg_class WHERE relnamespace='public'::regnamespace")"

echo "=== 5) Hata senaryolari ==="
"$PP" -d testdb --where="public.events:nonexistent_col >= 5" -f "$OUT/err1.sql" 2>"$OUT/err1.log"; rc=$?
[[ $rc -ne 0 ]] && { echo "PASS: bozuk SQL nonzero exit ($rc): $(grep -m1 -oE 'column .* does not exist' "$OUT/err1.log" | head -c 70)"; PASS=$((PASS+1)); } || { echo "FAIL: bozuk SQL sessiz gecti"; FAIL=$((FAIL+1)); }
"$PP" -d testdb --where="nonexistent_table:id<10" -f "$OUT/err2.sql" 2>"$OUT/err2.log"; rc=$?
[[ $rc -ne 0 ]] && { echo "PASS: eslesmeyen desen nonzero exit ($rc)"; PASS=$((PASS+1)); } || { echo "FAIL: eslesmeyen desen sessiz"; FAIL=$((FAIL+1)); }
"$PP" -d testdb --where="public.events" -f "$OUT/err3.sql" 2>"$OUT/err3.log"; rc=$?
[[ $rc -ne 0 ]] && grep -qi "missing" "$OUT/err3.log" && { echo "PASS: ':' eksik -> net hata"; PASS=$((PASS+1)); } || { echo "FAIL: ':' eksik rc=$rc: $(head -1 "$OUT/err3.log")"; FAIL=$((FAIL+1)); }

echo "=== 6) --version / --help ==="
"$PP" --version | grep -q "pg_dumpplus" && { echo "PASS: version: $("$PP" --version)"; PASS=$((PASS+1)); } || { echo "FAIL: version"; FAIL=$((FAIL+1)); }
"$PP" --help | grep -q -- "--where" && { echo "PASS: help'te --where"; PASS=$((PASS+1)); } || { echo "FAIL: help"; FAIL=$((FAIL+1)); }

echo "=== 7) Tirlimli tablo/kolon adlari ==="
psql -X -q -d testdb -c 'DROP TABLE IF EXISTS "Audit:Log" CASCADE; CREATE TABLE "Audit:Log" (id int, "a:b" int); INSERT INTO "Audit:Log" SELECT g, g*2 FROM generate_series(1,100) g;'
"$PP" -d testdb --no-owner --where='"Audit:Log":"a:b" >= 100' -Fc -f "$OUT/test7.dump"
restore_dir test7 "$OUT/test7.dump"
chk "test7.quoted-filtre" "51" "$(q test7 'SELECT count(*) FROM "Audit:Log"')"

echo ""
echo "=== SONUC: PASS=$PASS FAIL=$FAIL  (ciktilar: $OUT) ==="
[[ $FAIL -eq 0 ]]
