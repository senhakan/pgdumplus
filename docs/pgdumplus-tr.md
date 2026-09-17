# pg_dumpplus

**PostgreSQL verinizi seçerek dışa aktarın, hassas kolonları maskeyle koruyun.**

[İndir](https://github.com/senhakan/pgdumpplus/releases/latest) · [English](../README.md) · [Geri bildirim](https://github.com/senhakan/pgdumpplus/issues)

pg_dumpplus, PostgreSQL'in `pg_dump` aracına **satır filtreleme** ve **kolon
maskeleme** ekler. Yakın tarihli kayıtları veya belirli bir müşterinin verilerini
seçebilir, istediğiniz alanları dışa aktarım sırasında maskeleyebilirsiniz.
Alıştığınız dump biçimlerini ve geri yükleme araçlarını kullanmaya devam edersiniz.

```bash
pg_dumpplus -d mydb -Fc \
  --where="public.orders:created_at >= now() - interval '30 days'" \
  --mask='public.customers:email:all' \
  --mask='public.customers:phone:phone' \
  -f export.dump
```

Bu komut, siparişlerin yalnızca son 30 gününü ve müşteri tablosunun belirtilen
kolonlarını maskeli olarak dışa aktarır. Diğer tablo ve kolonlar normal şekilde
aktarılır.

## Neler sunar?

- **Satır seçimi:** Oracle Data Pump'ın `QUERY` seçeneğine benzer biçimde,
  `--where` ile SQL koşulları tanımlayın.
- **Kolon maskeleme:** Hazır kalıpları veya kendi SQL ifadelerinizi kullanın.
- **Tanıdık biçimler:** Custom (`-Fc`), düz SQL (`-Fp`), dizin (`-Fd`), paralel
  dump (`-j`) ve `--inserts` desteği.
- **Tutarlı veri görünümü:** Filtreleme ve maskeleme aynı dump snapshot'ı içinde
  çalışır.

pg_dumpplus, mevcut PostgreSQL araçlarınızın yanına ayrı bir komut olarak
kurulur. PostgreSQL'in `pg_dump` aracını temel alan bağımsız bir projedir.

## Kurulum

[Son sürümden](https://github.com/senhakan/pgdumpplus/releases/latest)
sisteminize uygun Linux **x86_64** paketini indirin.

| Platform | Paket |
| --- | --- |
| RHEL / Rocky Linux / AlmaLinux 8 | `.el8.x86_64.rpm` |
| Ubuntu 22.04 | `1u2204_amd64.deb` |
| Ubuntu 24.04 | `1u2404_amd64.deb` |
| Debian 12 | `1d12_amd64.deb` |

PostgreSQL 13 ve 17 için paketler sunulur. Bu sunucularda aynı ana sürümü,
14–16 sunucularında PostgreSQL 17 paketini seçin. Sunucunuzdan daha eski ana
sürüme sahip bir istemci kullanmayın.

Örneğin Ubuntu 24.04 üzerinde PostgreSQL 17 paketini kurmak için:

```bash
sudo apt install ./pgdumpplus-17_<version>-<revision>u2404_amd64.deb
pg_dumpplus --version
```

RPM paketleri için `sudo dnf install ./<paket.rpm>` kullanın. Paketler önceden
derlenmiş istemcileri ve özel bir `libpq` içerir; derleyici, Python veya
PostgreSQL sunucusu kurulumu gerekmez. Çalışma zamanı kütüphanelerini paket
yöneticisi kurar.

| Komut | İşlev |
| --- | --- |
| `pg_dumpplus-17` / `pg_dumpplus-13` | Belirli istemci sürümünü çalıştırır |
| `pg_dumpplus` | PostgreSQL 17 paketinin sağladığı varsayılan komut |
| `pg_restoreplus-17` / `pg_restoreplus-13` | Aynı sürümün geri yükleme aracı |

İki ana sürüm birlikte kurulabilir. Dosyalar `/opt/pgdumpplus/<major>/` altında,
komut bağlantıları `/usr/bin/` içinde bulunur. Sistemdeki `pg_dump` ve
`pg_restore` komutları değişmez. PG17 kaldırılınca sürümsüz komut da kaldırılır;
PG13 kuruluysa `pg_dumpplus-13` kullanılmaya devam eder.

Tarball arşivleri aynı `opt/` ve `usr/` yapısını kullanır. Özel bir dizine açıp
`<dizin>/usr/bin/pg_dumpplus-17` komutuyla da çalıştırabilirsiniz. İşletim
sisteminize uygun arşivi seçin; çalışma zamanı kütüphanelerini ayrıca kurun.

## Satır filtreleme

Tablo deseni ve SQL koşulunu, `WHERE` anahtar sözcüğünü eklemeden belirtin:

```bash
pg_dumpplus -d mydb -Fc \
  --where='public.orders:tenant_id = 42' \
  --where='public.order_items:order_id IN (SELECT id FROM public.orders WHERE tenant_id = 42)' \
  -f tenant.dump
```

Farklı tablolar için `--where` seçeneğini tekrarlayın. Desenler `pg_dump -t`
sözdizimini kullanır: `public.orders`, `public.*` gibi. Filtre uygulanmayan
tablolar tamamen aktarılır; yalnızca belirli tabloları almak için `-t` kullanın.

Örneğin ID sırasına göre son 1.000 siparişi almak için:

```bash
pg_dumpplus -d mydb -t public.orders -Fc \
  --where='public.orders:id IN (SELECT id FROM public.orders ORDER BY id DESC LIMIT 1000)' \
  -f recent_orders.dump
```

## Kolon maskeleme

Satırları okumadan ve dump dosyası oluşturmadan maskeleme planını önizleyin:

```bash
pg_dumpplus -d mydb --dry-run --plan-format=json \
  --mask='public.customers:email:email'
```

`--dry-run` yalnızca planı standart çıktıya yazar. JSON çıktısı
`schema_version: 1` kullanır; özel SQL ifadeleri raporlanır ancak çalıştırılmaz.

Değiştirilecek her kolon için `--mask='tablo:kolon:ifade'` kullanın:

```bash
pg_dumpplus -d mydb -Fc \
  --mask='public.customers:full_name:all' \
  --mask='public.customers:phone:phone' \
  --mask="public.customers:email:'redacted@example.com'" \
  -f masked.dump
```

| Kalıp | Davranış | Örnek |
| --- | --- | --- |
| `all` | Karakterleri `*` ile değiştirir | `Alice` → `*****` |
| `identity` | İlk iki ve son iki karakteri korur | `12345678901` → `12*******01` |
| `phone` | Son üç karakteri korur | `05551234567` → `********567` |
| `email` | İlk karakteri ve alan adını korur | `user@example.com` → `u***@example.com` |
| `name` | İlk karakteri korur | `Alice Smith` → `A**********` |
| `address` | Uzunluğu koruyarak tamamını maskeler | `Main Street 1` → `*************` |
| `iban` | İlk dört ve son dört karakteri korur | `DE89370400440532013000` → `DE89**************3000` |
| `card` | Son dört karakteri korur | `4111111111111111` → `************1111` |
| `uuid` | İlk sekiz ve son dört karakteri korur | `550e8400-e29b-41d4-a716-446655440000` → `550e8400**********************0000` |

Özel ifadeler PostgreSQL tarafından değerlendirilir. Sonuç, hedef kolonun veri
tipine ve kısıtlarına uygun olmalıdır. Hazır kalıplar metin döndürür. `--where`
ve `--mask` aynı dump içinde birlikte kullanılabilir.

Hazır kalıplar NULL ve boş değerleri korur. `identity`, dört karakter veya daha
kısa değerlerin tüm karakterlerini maskeler. `tc`, geriye dönük uyumluluk için
`identity` takma adı olarak desteklenir.

**Maskeleme kuralları veri aktarımından önce doğrulanır.** Olmayan, silinmiş,
üretilen, dışarıda bırakılmış, yinelenen veya tip ile uyumsuz bir maske komutu
başarısız kılar. Hata sonrasında oluşmuş kısmi çıktıyı kullanmayın. Maskeleme
yalnızca belirttiğiniz kolonları etkiler; veritabanını otomatik olarak anonimleştirmez.

## Geri yükleme

Custom veya dizin arşivini mevcut, boş bir veritabanına yükleyin:

```bash
pg_restoreplus-17 -d destination --no-owner export.dump
```

Düz SQL için `psql -X -v ON_ERROR_STOP=1 -d destination -f export.sql` kullanın.
Paket aynı sürümün geri yükleme aracını içerir. Dump sürümüyle uyumlu standart
`pg_restore` da kullanılabilir.

## Bilinmesi gerekenler

- Filtreler ilişkili kayıtları otomatik seçmez. Foreign key ile bağlı tabloları
  filtrelerken referans verilen üst kayıtları da dahil edin.
- Primary key, unique veya foreign key kolonlarını maskelemek kısıtları bozabilir.
- `-t` ile tablo seçmek, şema gibi tüm bağımlılıkları otomatik dahil etmez.
  Gerektiğinde bunları hedefte önceden hazırlayın.
- Hiçbir tabloyla eşleşmeyen desen veya geçersiz SQL, dump'ın hata vermesine
  neden olur.

## Geri bildirim ve katkı

Kullanım senaryolarınızı, özellik önerilerinizi ve hataları
[Issues](https://github.com/senhakan/pgdumpplus/issues) üzerinden paylaşabilirsiniz.
PostgreSQL sürümünüzü ve hassas bilgilerden arındırılmış kısa bir örneği ekleyin.
Pull request katkılarına açığız.

## Lisans

[PostgreSQL Lisansı](../LICENSE).
