#!/bin/bash
# mask_verify_ci.sh — GitHub Actions servis konteynerindeki PostgreSQL 17'ye
# kars --mask + --where uctan uca dogrulama. PGPASSWORD ortamda olmali.
BIN=/opt/pgd/bin/pg_dumpplus
PSQL=/usr/bin/psql
export PGHOST=${PGHOST:-pg} PGPORT=5432 PGUSER=postgres
PASS=0; FAIL=0
chk() { if [ "$2" = "$3" ]; then echo "PASS $1"; PASS=$((PASS+1)); else echo "FAIL $1 (beklenen=$3 got=$2)"; FAIL=$((FAIL+1)); fi }
Q() { $PSQL -d "$1" -At -c "$2"; }
R() { $PSQL -d mask_testdb -q "$@" >/dev/null 2>&1; }

# M1 preset tc + restore dogrulama
$BIN -d testdb -t public.customers --mask='public.customers:ssn:tc' -f /tmp/m1.sql 2>/tmp/m1.err
chk "M1 exit" "$?" "0"
chk "M1 maskeli TC 5000" "$(grep -c '10\*\{7\}19' /tmp/m1.sql)" "5000"
grep -qE '	100000007919|^[[:space:]]*100000007919' /tmp/m1.sql && chk "M1 ham TC sizdi" "yes" "no" || chk "M1 ham TC yok" "ok" "ok"
R -f /tmp/m1.sql
chk "M1 restore degeri" "$(Q mask_testdb "SELECT ssn FROM public.customers WHERE id=1")" "10********19"
chk "M1 restore 5000 satir" "$(Q mask_testdb "SELECT count(*) FROM public.customers")" "5000"

# M2 coklu mask
$BIN -d testdb -t public.customers \
  --mask='public.customers:phone_number:phone' \
  --mask='public.customers:address:repeat(chr(42), length(address))' \
  --mask="public.customers:full_name:upper(left(full_name,2)) || '**'" \
  -f /tmp/m2.sql 2>/tmp/m2.err
chk "M2 exit" "$?" "0"
R -c "TRUNCATE public.customers"; R -f /tmp/m2.sql
# phone_number degeri 11 hane -> phone preseti 8 yildiz + son 3
chk "M2 degerler" "$(Q mask_testdb "SELECT phone_number||'|'||left(address,6)||'|'||full_name FROM public.customers WHERE id=2")" "********026|*****************|CU**"

# M3 where + mask
$BIN -d testdb -t public.customers \
  --where='public.customers:id <= 100' --mask='public.customers:ssn:all' \
  -f /tmp/m3.sql 2>/tmp/m3.err
chk "M3 exit" "$?" "0"
R -c "TRUNCATE public.customers"; R -f /tmp/m3.sql
chk "M3 filtre 100" "$(Q mask_testdb "SELECT count(*) FROM public.customers")" "100"
chk "M3 all preset" "$(Q mask_testdb "SELECT ssn FROM public.customers WHERE id=5")" "***********"

# M4 gecersiz kolon skip + uyari + veri ham
$BIN -d testdb -t public.customers --mask='public.customers:nonexistent_col:all' -f /tmp/m4.sql 2>/tmp/m4.err
chk "M4 exit=0" "$?" "0"
grep -q "not found in table" /tmp/m4.err && chk "M4 warning" "ok" "ok" || chk "M4 warning" "no" "ok"
if grep -q '100000007919' /tmp/m4.sql; then chk "M4 veri ham" "ok" "ok"; else chk "M4 veri ham degil" "no" "ok"; fi

# M5 --inserts + mask
$BIN -d testdb -t public.customers --inserts --mask='public.customers:ssn:tc' -f /tmp/m5.sql 2>/tmp/m5.err
chk "M5 exit" "$?" "0"
grep -q '11\*\{7\}' /tmp/m5.sql && chk "M5 INSERT maskeli" "ok" "ok" || chk "M5 maskesiz?" "no" "ok"
grep -q "'100000007919'" /tmp/m5.sql && chk "M5 INSERT ham TC (KOTU)" "yes" "no" || chk "M5 INSERT ham yok" "ok" "ok"

# M6 maskesiz dump: tam veri + ham TC korunur (bayt-kimligi ayni-major pg_dump
# ile test makinesinde kanitlandi; CI'da pg_dump 16 < sunucu 17 oldugu icin
# vanilla karsilastirma anlamsiz - davranis kontrolu yapilir)
$BIN -d testdb -t public.customers --no-owner --no-privileges -f /tmp/p6.sql 2>/dev/null
chk "M6 exit" "$?" "0"
R -c "DROP TABLE IF EXISTS public.customers"; R -f /tmp/p6.sql
chk "M6 maskesiz tam veri" "$(Q mask_testdb "SELECT count(*) FROM public.customers")" "5000"
grep -qE '	100000007919|^[[:space:]]*100000007919' /tmp/p6.sql && chk "M6 ham TC korundu" "ok" "ok" || chk "M6 ham TC yok (KOTU)" "no" "ok"

# M7 restore header gercek kolon adlarinda
grep -q "^COPY public.customers (id, full_name, ssn, phone_number, adres, birth_year) FROM stdin;" /tmp/m1.sql \
  && chk "M7 header temiz" "ok" "ok" || chk "M7 header" "no" "ok"

# M8 parallel -Fd + mask
rm -rf /tmp/par8d; $BIN -d testdb -j 4 -Fd -f /tmp/par8d \
  --mask='public.customers:ssn:tc' -t public.customers 2>/tmp/p8.err
chk "M8 parallel exit" "$?" "0"
FOUND=0
for f in /tmp/par8d/*.dat.gz; do gzip -dc "$f" 2>/dev/null | grep -q '11\*\{7\}' && FOUND=1; done
chk "M8 parallel maskeli" "$FOUND" "1"
if for f in /tmp/par8d/*.dat.gz; do gzip -dc "$f"; done | grep -q '100000007919'; then chk "M8 ham sizdi" "yes" "no"; else chk "M8 parallel temiz" "ok" "ok"; fi

# M9 --where regresyon (events)
$BIN -d testdb -t public.events --where='public.events:created_at >= now() - interval '"'"'1 hour'"'"'' -f /tmp/m9.sql 2>/tmp/m9.err
chk "M9 where exit" "$?" "0"
chk "M9 where satirlari" "$(grep -cP '^[0-9]+\t' /tmp/m9.sql)" "$(Q testdb "SELECT count(*) FROM public.events WHERE created_at >= now() - interval '1 hour'")"

if [ "$FAIL" -gt 0 ]; then
  echo "===== dump err dokumleri ====="
  for e in /tmp/m1.err /tmp/m2.err /tmp/m3.err /tmp/m4.err /tmp/m5.err /tmp/p8.err; do
    [ -s "$e" ] && { echo "-- $e --"; cat "$e"; }
  done
  echo "===== m1.sql restore denemesi (gorunur hatalar) ====="
  psql -d mask_testdb -c "DROP TABLE IF EXISTS public.customers" >/dev/null 2>&1
  psql -d mask_testdb -f /tmp/m1.sql 2>&1 | grep -iE 'error|invalid|denied|does not exist' | head -6
  echo "===== psql/pgDump server surumleri ====="
  psql --version; psql -d testdb -At -c "SHOW server_version"
fi
echo "MASK-OZET: PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
