# pg_dumpplus kurulum ve kullanım kılavuzu

Bu kılavuz, derlenmiş `pg_dumpplus` istemcisinin Ubuntu ve Rocky Linux üzerinde kurulmasını ve günlük yedekleme komutlarını açıklar. İstemci tarafında derleyici, Python veya PostgreSQL sunucusu gerekmez.

## Desteklenen paketler

Paketler yalnızca `x86_64` mimarisi için yayımlanır. PostgreSQL sunucu major sürümüyle eşleşen istemciyi seçin.

| İşletim sistemi | Paket adı deseni |
|---|---|
| Rocky/RHEL/AlmaLinux 8 | `pgdumpplus-<major>-<version>-<revision>.el8.x86_64.rpm` |
| Rocky/RHEL/AlmaLinux 9 | `pgdumpplus-<major>-<version>-<revision>.el9.x86_64.rpm` |
| Rocky/RHEL/AlmaLinux 10 | `pgdumpplus-<major>-<version>-<revision>.el10.x86_64.rpm` |
| Ubuntu 22.04 | `pgdumpplus-<major>_<version>-<revision>u2204_amd64.deb` |
| Ubuntu 24.04 | `pgdumpplus-<major>_<version>-<revision>u2404_amd64.deb` |

PostgreSQL 13 legacy, 14–18 maintained sürümlerdir. Paketler GitHub [Latest Release](https://github.com/senhakan/pgdumpplus/releases/latest) sayfasından indirilir.

## Otomatik kurulum scripti

Script işletim sistemi, mimari ve PostgreSQL major sürümünü algılar; uygun
paketi GitHub Release API üzerinden seçer, mevcut kurulumu bildirir, kullanıcı
onayı alır ve kurulum sonrası binary doğrulaması yapar. Desteklenmeyen dağıtım
veya mimaride güvenli şekilde durur.

Önce kuru çalışma ile planı görün:

```bash
curl -fsSL https://github.com/senhakan/pgdumpplus/releases/latest/download/install-pgdumpplus.sh \
  | bash -s -- --dry-run --pg-major 17
```

Etkileşimli kurulum:

```bash
curl -fsSL https://github.com/senhakan/pgdumpplus/releases/latest/download/install-pgdumpplus.sh \
  | bash -s --
```

`wget` ve otomasyon kullanımı:

```bash
wget -qO- https://github.com/senhakan/pgdumpplus/releases/latest/download/install-pgdumpplus.sh \
  | bash -s -- --yes
```

Bu release-asset adresi, uzun `raw.githubusercontent.com` adresine göre daha
kısadır ve `latest` release değiştiğinde sabit kalır. Scriptin kaynak sürümü
[`scripts/install-pgdumpplus.sh`](../scripts/install-pgdumpplus.sh) dosyasındadır.

Script seçenekleri: `--yes`, `--dry-run`, `--version 2.1.0`, `--pg-major 17`.
Üretim otomasyonunda mümkünse release sürümünü `--version` ile sabitleyin ve
scripti çalıştırmadan önce inceleyin.

## Paketi indirme ve doğrulama

Release sayfasındaki gerçek sürüm ve dosya adını kullanın:

```bash
VERSION=2.1.1
MAJOR=17
BASE_URL="https://github.com/senhakan/pgdumpplus/releases/download/v${VERSION}"

# Örnek Ubuntu 24.04
curl -fL -o "pgdumpplus-${MAJOR}_${VERSION}-2u2404_amd64.deb" \
  "${BASE_URL}/pgdumpplus-${MAJOR}_${VERSION}-2u2404_amd64.deb"

# Release sayfasındaki checksum dosyasından beklenen değeri karşılaştırın.
sha256sum "pgdumpplus-${MAJOR}_${VERSION}-2u2404_amd64.deb"
```

Checksum doğrulaması başarısızsa paketi kurmayın. RPM için aynı yöntemde `.rpm` dosya adını kullanın.

## Ubuntu kurulumu

Ubuntu 22.04 için `u2204`, Ubuntu 24.04 için `u2404` paketini seçin:

```bash
sudo apt update
sudo apt install ./pgdumpplus-17_2.1.1-2u2404_amd64.deb

pg_dumpplus --version
pg_dumpplus --build-info
command -v pg_dumpplus
```

Belirli bir major sürümü kullanmak için:

```bash
pg_dumpplus-17 --version
pg_restoreplus-17 --version
```

Eksik bağımlılık durumunda yerel paketi tekrar `apt install ./paket.deb` ile kurun; APT gerekli runtime paketlerini tamamlar.

## Rocky Linux 8, 9 ve 10 kurulumu

İşletim sistemi major sürümüne uygun RPM kullanın:

```bash
# Rocky Linux 8
sudo dnf install ./pgdumpplus-17-2.1.1-2.el8.x86_64.rpm

# Rocky Linux 9
sudo dnf install ./pgdumpplus-17-2.1.1-2.el9.x86_64.rpm

# Rocky Linux 10
sudo dnf install ./pgdumpplus-17-2.1.1-2.el10.x86_64.rpm

pg_dumpplus --version
pg_dumpplus --build-info
command -v pg_dumpplus
```

Paket önceden derlenmiştir; istemci makinesinde GCC, Python veya PostgreSQL server kurulumu gerekmez. Kurulum yalnızca runtime bağımlılıklarını getirir.

## Temel bağlantı ve dump komutları

Komutlar PostgreSQL istemci seçeneklerini korur:

```bash
# Custom format, önerilen arşiv formatı
pg_dumpplus -v -Fc -Z 5 \
  -U postgres -h 127.0.0.1 -p 5432 -d appdb \
  > backup-$(date +%Y%m%d-%H%M%S).dump \
  2> backup-$(date +%Y%m%d-%H%M%S).log

# Plain SQL
pg_dumpplus -v -Fp \
  -U postgres -d appdb \
  -f appdb.sql

# Directory format; büyük veritabanlarında paralel restore için uygundur
pg_dumpplus -v -Fd -j 4 \
  -U postgres -d appdb \
  -f appdb-directory
```

`-Fc -Z 5` ile oluşturulan dosya PostgreSQL custom archive'dır; dosya adında `.gz` bulunsa bile `gunzip` ile açılmaz. Doğrudan `pg_restoreplus-<major>` kullanılır.

## Son iki yıl filtresi

Tek tablo için komut satırından:

```bash
pg_dumpplus -v -Fc -Z 5 -U postgres -d appdb \
  --where="public.orders:created_at >= make_date(2024,9,18)" \
  -f orders-last-2-years.dump
```

Birden fazla koşulu tekrar ederek ekleyebilirsiniz:

```bash
pg_dumpplus -v -Fc -Z 5 -U postgres -d appdb \
  --where="public.orders:created_at >= make_date(2024,9,18)" \
  --where="public.order_items:created_at >= make_date(2024,9,18)" \
  -f recent.dump
```

Tekrarlanabilir kullanım için filtreleri JSON profile dosyasına koyun:

```json
{
  "schema_version": 1,
  "filters": [
    {"table": "public.orders", "where": "created_at >= make_date(2024,9,18)"},
    {"table": "public.order_items", "where": "created_at >= make_date(2024,9,18)"}
  ]
}
```

```bash
pg_dumpplus -v -Fc -Z 5 -U postgres -d appdb \
  --profile=recent-profile.json \
  -f recent.dump
```

`pg_dumpplus` için ayrı bir `--where-file` seçeneği yoktur; dosya tabanlı filtreleme `--profile=FILE` ile yapılır. Profile içindeki SQL ifadeleri güvenilir girdidir ve dosya erişimi korunmalıdır.

## Maskeleme ile birlikte kullanım

```bash
pg_dumpplus -v -Fc -Z 5 -U postgres -d appdb \
  --where="public.orders:created_at >= make_date(2024,9,18)" \
  --mask="public.customers:email:email" \
  --mask="public.customers:phone:phone" \
  -f masked-recent.dump
```

Filtre ve maske kurallarını aynı JSON profile dosyasında da tanımlayabilirsiniz.

## Restore ve doğrulama

Önce hedef veritabanını oluşturun, sonra major sürümü eşleşen restore istemcisini kullanın:

```bash
createdb -U postgres appdb_restore_test

pg_restoreplus-17 -v --exit-on-error \
  --no-owner --no-privileges -j 4 \
  -U postgres -d appdb_restore_test \
  backup.dump \
  > restore.log 2>&1

# Arşiv yalnızca okunabilir mi?
pg_restoreplus-17 -l backup.dump > archive.list
```

Restore sonrası kritik tabloları ve satır sayılarını karşılaştırın. Test tamamlandıktan sonra geçici veritabanını kaldırın:

```bash
dropdb -U postgres appdb_restore_test
```

## Paket güncelleme ve kaldırma

```bash
# Ubuntu
sudo apt install ./pgdumpplus-17_<new-version>-<revision>u2404_amd64.deb
sudo apt remove pgdumpplus-17

# Rocky Linux
sudo dnf upgrade ./pgdumpplus-17-<new-version>-<revision>.el9.x86_64.rpm
sudo dnf remove pgdumpplus-17
```

Paket kaldırıldığında veritabanları, dump dosyaları ve kullanıcı profile dosyaları silinmez.

## Sürüm seçimi

Sunucu major sürümüyle aynı istemciyi kullanın:

```text
PostgreSQL 13 → pg_dumpplus-13
PostgreSQL 14 → pg_dumpplus-14
PostgreSQL 15 → pg_dumpplus-15
PostgreSQL 16 → pg_dumpplus-16
PostgreSQL 17 → pg_dumpplus-17
PostgreSQL 18 → pg_dumpplus-18 / varsayılan pg_dumpplus
```

İstemci major sürümünü sunucudan eski seçmeyin. Farklı major sürümler arasında restore PostgreSQL tarafından bazı durumlarda desteklense de hedef sistem ayrıca doğrulanmalıdır.
