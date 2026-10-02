# PRD — Integrasi Telegram PPPoE Offline ke MikroTik Traffic Monitor

## 1. Informasi Produk

**Nama aplikasi:** MikroTik Traffic Monitor
**Modul baru:** Telegram PPPoE Client Monitor
**Versi:** 1.1.0
**Platform:** Ubuntu Server / STB Linux
**Bahasa:** Python 3
**Framework existing:** FastAPI
**Database:** SQLite
**Koneksi MikroTik:** MikroTik RouterOS API non-SSL
**Interface pengguna tambahan:** Telegram Bot

---

# 2. Latar Belakang

Aplikasi saat ini merupakan aplikasi web sederhana untuk monitoring trafik interface MikroTik.

Struktur aplikasi existing:

```text
.
├── app
│   ├── api
│   │   ├── routes_config.py
│   │   ├── routes_interfaces.py
│   │   ├── routes_status.py
│   │   └── routes_traffic.py
│   ├── core
│   │   ├── config.py
│   │   ├── duration.py
│   │   ├── logging.py
│   │   └── __init__.py
│   ├── database
│   │   ├── database.py
│   │   ├── models.py
│   │   └── repository.py
│   ├── main.py
│   ├── mikrotik
│   │   ├── client.py
│   │   └── collector.py
│   └── services
│       └── traffic_service.py
├── data
├── frontend
├── index.html
├── README.md
├── requirements.txt
├── systemd
│   └── mikrotik-traffic-monitor.service
└── tests
```

Aplikasi akan dikembangkan dengan menambahkan fitur monitoring status pelanggan PPPoE melalui Telegram.

User menggunakan **RADIUS pihak ketiga**, sehingga daftar username PPPoE tidak dapat dianggap sebagai database lokal MikroTik.

Karena itu diperlukan database lokal untuk menyimpan data pelanggan.

Ketika user menjalankan:

```text
/cek_off
```

Telegram Bot akan:

1. mengambil daftar username PPPoE pelanggan dari database lokal;
2. mengambil daftar PPPoE yang sedang aktif dari MikroTik;
3. membandingkan kedua data tersebut;
4. menentukan pelanggan mana yang OFF;
5. mengirimkan daftar pelanggan OFF ke Telegram.

---

# 3. Tujuan

Fitur ini bertujuan untuk menyediakan sistem sederhana untuk:

* menyimpan database pelanggan PPPoE;
* melakukan import pelanggan menggunakan Excel;
* menyediakan template Excel melalui Telegram;
* meng-export database pelanggan ke Excel;
* memperbarui data pelanggan menggunakan Excel;
* mengecek pelanggan PPPoE yang sedang offline;
* menggunakan MikroTik sebagai sumber status koneksi;
* menggunakan database lokal sebagai sumber daftar pelanggan;
* mengintegrasikan semuanya ke aplikasi existing.

---

# 4. Prinsip Arsitektur

## WAJIB

Jangan membuat aplikasi Python baru yang terpisah.

Fitur Telegram harus menjadi modul tambahan pada aplikasi existing.

Gunakan kembali:

```text
app/core
app/database
app/mikrotik
app/main.py
```

sebisa mungkin.

Jangan membuat koneksi MikroTik kedua apabila `app/mikrotik/client.py` yang sudah ada dapat digunakan kembali.

---

# 5. Arsitektur Sistem

```text
                    INTERNET
                       │
                       ▼
                Telegram User
                       │
                       ▼
                Telegram Bot
                       │
                       ▼
              Telegram Service
                       │
            ┌──────────┴──────────┐
            │                     │
            ▼                     ▼
      Customer Database      MikroTik API
            │                     │
            │                     ▼
            │              Active PPPoE Users
            │                     │
            └──────────┬──────────┘
                       ▼
                Comparison Engine
                       │
                       ▼
                 Offline Users
                       │
                       ▼
                 Telegram Reply
```

---

# 6. Sumber Data

## 6.1 Database Pelanggan

Database lokal menyimpan daftar pelanggan yang harus dipantau.

Contoh:

```text
username
nama pelanggan
nomor pelanggan
alamat
nomor telepon
paket
status monitoring
catatan
```

Username PPPoE merupakan identifier utama.

---

## 6.2 MikroTik

MikroTik hanya digunakan untuk mendapatkan status PPPoE yang sedang aktif.

Gunakan:

```text
RouterOS API
```

bukan API-SSL.

Konfigurasi existing:

```env
MIKROTIK_HOST=192.168.1.1
MIKROTIK_PORT=8728
MIKROTIK_USERNAME=monitor
MIKROTIK_PASSWORD=password
MIKROTIK_USE_SSL=false
MIKROTIK_VERIFY_SSL=false
```

Jangan mengubah konfigurasi API existing menjadi API-SSL.

---

# 7. Logika Deteksi PPPoE OFF

## 7.1 Konsep

Database:

```text
pelanggan A
pelanggan B
pelanggan C
pelanggan D
```

MikroTik aktif:

```text
pelanggan A
pelanggan C
```

Maka:

```text
OFF:
pelanggan B
pelanggan D
```

Secara logika:

```python
offline_users = database_users - active_users
```

---

# 8. Identifikasi PPPoE Aktif

Gunakan MikroTik API untuk membaca:

```text
/ppp/active/print
```

Field utama:

```text
name
service
caller-id
address
uptime
```

Username PPPoE menggunakan field:

```text
name
```

Contoh response:

```text
name=pelanggan01
service=pppoe
caller-id=AA:BB:CC:DD:EE:FF
address=10.10.10.10
uptime=2h15m
```

Sistem cukup menggunakan:

```text
name
```

sebagai pembanding dengan username database.

---

# 9. Database Pelanggan

Tambahkan tabel:

```text
customers
```

Struktur minimal:

```text
id
customer_code
username
customer_name
phone
address
package
monitoring_enabled
notes
created_at
updated_at
```

### Field

| Field              | Type     | Keterangan       |
| ------------------ | -------- | ---------------- |
| id                 | INTEGER  | Primary key      |
| customer_code      | TEXT     | ID pelanggan     |
| username           | TEXT     | Username PPPoE   |
| customer_name      | TEXT     | Nama pelanggan   |
| phone              | TEXT     | Nomor HP         |
| address            | TEXT     | Alamat           |
| package            | TEXT     | Paket internet   |
| monitoring_enabled | BOOLEAN  | Apakah dipantau  |
| notes              | TEXT     | Catatan          |
| created_at         | DATETIME | Waktu dibuat     |
| updated_at         | DATETIME | Waktu diperbarui |

---

# 10. Unique Constraint

Username PPPoE harus unik.

```text
UNIQUE(username)
```

Customer code juga sebaiknya unik:

```text
UNIQUE(customer_code)
```

Tujuannya agar import Excel tidak menghasilkan pelanggan duplikat.

---

# 11. Import Excel

User dapat mengirim file Excel melalui Telegram.

Flow:

```text
Telegram
   │
   ▼
/import_pelanggan
   │
   ▼
Bot meminta file Excel
   │
   ▼
User upload Excel
   │
   ▼
Validasi Excel
   │
   ▼
Preview hasil import
   │
   ▼
User konfirmasi
   │
   ▼
Database diperbarui
```

---

# 12. Format Excel

Template Excel harus memiliki kolom:

```text
customer_code
username
customer_name
phone
address
package
monitoring_enabled
notes
```

Contoh:

| customer_code | username | customer_name | phone  | address   | package | monitoring_enabled | notes |
| ------------- | -------- | ------------- | ------ | --------- | ------- | ------------------ | ----- |
| C001          | faiz001  | Faizul        | 081xxx | Kambingan | 10M     | 1                  | -     |
| C002          | ahmad002 | Ahmad         | 082xxx | Lenteng   | 20M     | 1                  | -     |

---

# 13. Template Excel

Telegram harus menyediakan tombol:

```text
📥 Download Template Excel
```

File template harus:

* memiliki header;
* memiliki contoh data;
* memiliki keterangan setiap kolom;
* dapat langsung digunakan untuk import;
* menggunakan format `.xlsx`.

---

# 14. Export Data Pelanggan

Telegram menyediakan tombol:

```text
📤 Download Data Pelanggan
```

Bot membuat file:

```text
pelanggan.xlsx
```

yang memiliki struktur sama dengan template import.

Tujuannya agar file tersebut dapat:

1. didownload;
2. diedit;
3. diupload kembali;
4. digunakan untuk update database.

---

# 15. Mekanisme Update Excel

File Excel yang diexport dapat diedit kemudian diupload kembali.

Sistem melakukan upsert berdasarkan:

```text
username
```

Contoh:

Database:

```text
C001 | faiz001 | Faizul
```

Excel:

```text
C001 | faiz001 | Faizul Amali
```

Setelah import:

```text
C001 | faiz001 | Faizul Amali
```

Data pelanggan diperbarui.

---

# 16. Jangan Langsung Menimpa Database

Import Excel harus menggunakan mekanisme:

```text
Upload
   ↓
Parse
   ↓
Validate
   ↓
Preview
   ↓
Confirmation
   ↓
Transaction
   ↓
Commit
```

Jangan melakukan perubahan database sebelum user melakukan konfirmasi.

---

# 17. Validasi Excel

Sistem harus memvalidasi:

### Required

```text
username
customer_name
```

### Optional

```text
customer_code
phone
address
package
monitoring_enabled
notes
```

### Validasi username

Tidak boleh:

```text
kosong
NULL
duplikat
```

Jika terdapat duplikat dalam Excel:

```text
❌ Import dibatalkan.

Ditemukan username duplikat:

- faiz001
- ahmad002
```

---

# 18. Preview Import

Setelah upload:

```text
📊 HASIL VALIDASI EXCEL

Total baris       : 120
Data baru         : 10
Data diperbarui   : 105
Data dilewati     : 3
Error             : 2

Error:
1. Baris 14 - username kosong
2. Baris 88 - username duplikat

Silakan perbaiki file sebelum import.
```

Jika tidak ada error:

```text
📊 DATA SIAP DIIMPORT

Total data : 120
Data baru  : 10
Update     : 110

Apakah ingin melanjutkan?

[✅ IMPORT]
[❌ BATAL]
```

---

# 19. Command Telegram

Minimal command:

```text
/start
/menu
/cek_off
```

Tambahkan:

```text
/pelanggan
```

untuk membuka menu pelanggan.

---

# 20. Telegram Menu Utama

Gunakan Inline Keyboard.

Contoh:

```text
🤖 MikroTik Monitor

[🔴 Cek PPPoE OFF]
[👥 Data Pelanggan]
[📊 Traffic Monitor]
```

Menu pelanggan:

```text
👥 DATA PELANGGAN

[📥 Download Template]
[📤 Download Data Pelanggan]
[📋 Import Excel]
[🔄 Refresh]
```

---

# 21. Command /cek_off

Ketika user mengetik:

```text
/cek_off
```

Bot menjalankan proses:

```text
1. Validasi koneksi MikroTik
2. Ambil customers monitoring_enabled=1
3. Ambil /ppp/active/print
4. Ambil username aktif
5. Compare
6. Generate report
7. Kirim ke Telegram
```

---

# 22. Contoh Hasil /cek_off

```text
🔴 PPPoE OFF

Waktu: 02-10-2026 21:10

Total pelanggan dipantau : 120
Online                   : 108
Offline                  : 12

Daftar Offline:

1. C001
   Username : faiz001
   Nama     : Faizul
   Paket    : 10M

2. C017
   Username : ahmad002
   Nama     : Ahmad
   Paket    : 20M

3. C025
   Username : user025
   Nama     : Budi
   Paket    : 10M

...

Total OFF: 12 pelanggan
```

---

# 23. Jika Tidak Ada Pelanggan OFF

Tampilkan:

```text
🟢 SEMUA PELANGGAN ONLINE

Total pelanggan dipantau : 120
Online                   : 120
Offline                  : 0

Tidak ditemukan pelanggan PPPoE yang OFF.
```

---

# 24. Jika MikroTik Tidak Bisa Dihubungi

Jangan menganggap semua pelanggan OFF.

Tampilkan:

```text
⚠️ GAGAL MENGECEK PPPoE

MikroTik tidak dapat dihubungi.

Host:
192.168.1.1:8728

Status:
Connection failed

Data pelanggan TIDAK diubah.
```

Ini sangat penting.

Jika API gagal, sistem tidak boleh menghasilkan false offline.

---

# 25. Jika Database Kosong

Tampilkan:

```text
⚠️ DATABASE PELANGGAN KOSONG

Belum terdapat pelanggan yang dapat diperiksa.

Silakan upload data pelanggan melalui:

[📥 Download Template]
[📤 Import Excel]
```

---

# 26. Filtering

Hanya pelanggan:

```text
monitoring_enabled = 1
```

yang masuk ke `/cek_off`.

Pelanggan:

```text
monitoring_enabled = 0
```

diabaikan.

---

# 27. Arsitektur Modul Baru

Tambahkan:

```text
app
├── telegram
│   ├── __init__.py
│   ├── bot.py
│   ├── handlers.py
│   ├── keyboards.py
│   └── excel.py
│
├── services
│   ├── traffic_service.py
│   └── pppoe_service.py
│
└── database
    ├── database.py
    ├── models.py
    └── repository.py
```

Jika diperlukan:

```text
app/core/config.py
```

diperluas untuk konfigurasi Telegram.

---

# 28. Tanggung Jawab Modul

## telegram/bot.py

Bertanggung jawab:

* membuat Telegram Bot;
* menjalankan polling;
* lifecycle bot;
* error handling.

---

## telegram/handlers.py

Menangani:

```text
/start
/menu
/cek_off
/pelanggan
```

dan callback button.

---

## telegram/keyboards.py

Menyediakan:

* menu utama;
* menu pelanggan;
* tombol konfirmasi;
* tombol download;
* tombol batal.

---

## telegram/excel.py

Menangani:

* generate template;
* export database;
* membaca Excel;
* validasi Excel;
* menghasilkan preview import.

---

## services/pppoe_service.py

Menangani:

```text
get_active_pppoe()
get_offline_customers()
```

Contoh konsep:

```python
def get_offline_customers():
    customers = repository.get_monitored_customers()
    active_users = mikrotik.get_active_pppoe_users()

    active_set = set(active_users)

    return [
        customer
        for customer in customers
        if customer.username not in active_set
    ]
```

---

# 29. Reuse MikroTik Client

Existing:

```text
app/mikrotik/client.py
```

harus digunakan kembali.

Tambahkan method jika diperlukan:

```python
get_active_pppoe()
```

Jangan membuat library MikroTik connection baru jika existing client dapat digunakan.

---

# 30. Reuse Database

Existing:

```text
app/database/database.py
app/database/models.py
app/database/repository.py
```

harus tetap digunakan.

Tambahkan model:

```text
Customer
```

dan repository:

```text
create_customer()
update_customer()
upsert_customer()
delete_customer()
get_customer()
get_customers()
get_monitored_customers()
```

---

# 31. Database Migration

Karena aplikasi existing sudah menggunakan SQLite, perubahan schema harus aman.

Jangan menghapus database:

```text
data/traffic.db
```

Jangan membuat database kedua seperti:

```text
customer.db
```

Data pelanggan harus berada dalam database aplikasi existing.

---

# 32. Konfigurasi .env

Tambahkan:

```env
# ==============================
# TELEGRAM BOT
# ==============================
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=ISI_BOT_TOKEN
TELEGRAM_ALLOWED_CHAT_IDS=
```

`TELEGRAM_ALLOWED_CHAT_IDS` digunakan untuk membatasi siapa yang boleh menggunakan bot.

Format:

```env
TELEGRAM_ALLOWED_CHAT_IDS=123456789,987654321
```

Jika kosong, implementasi default harus aman dan tidak membuka bot untuk publik. Sebaiknya bot menolak user yang tidak terdaftar.

---

# 33. Dependency

Tambahkan dependency Telegram:

```text
python-telegram-bot
```

Tambahkan dependency Excel:

```text
openpyxl
```

Requirements menjadi kurang lebih:

```text
fastapi>=0.100.0
uvicorn[standard]>=0.22.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
pytest>=7.0.0
httpx>=0.24.0
python-telegram-bot>=21.0
openpyxl>=3.1.0
```

Gunakan versi yang kompatibel dengan Python yang tersedia di STB.

---

# 34. Telegram File Handling

Bot harus dapat:

### Download

Mengirim:

```text
template_pelanggan.xlsx
pelanggan.xlsx
```

### Upload

Menerima:

```text
.xlsx
```

File selain `.xlsx` ditolak.

Contoh:

```text
❌ Format file tidak didukung.

Silakan upload file Excel:
.xlsx
```

---

# 35. Keamanan Telegram

Semua command harus melalui authorization.

Contoh:

```python
if chat_id not in ALLOWED_CHAT_IDS:
    return
```

User tidak terdaftar mendapatkan:

```text
⛔ Anda tidak memiliki akses ke bot ini.
```

Jangan pernah menampilkan:

```text
MIKROTIK_PASSWORD
TELEGRAM_BOT_TOKEN
```

ke Telegram.

---

# 36. Logging

Gunakan sistem logging existing:

```text
app/core/logging.py
```

Log aktivitas penting:

```text
Telegram bot started
Telegram user authorized
Excel uploaded
Excel validation failed
Customer import started
Customer import completed
PPPoE check started
PPPoE check completed
MikroTik connection failed
```

Jangan log password.

---

# 37. Error Handling

Bot tidak boleh crash ketika:

* MikroTik mati;
* API timeout;
* Excel rusak;
* Excel format salah;
* database error;
* Telegram API error;
* user upload file bukan Excel.

Semua error harus ditangani dan dicatat melalui logging.

---

# 38. Timeout MikroTik

Pengecekan PPPoE harus memiliki timeout.

Jika MikroTik tidak merespons dalam waktu tertentu:

```text
timeout
```

dan proses dibatalkan.

Jangan menunggu tanpa batas.

---

# 39. Optimasi

Untuk `/cek_off`, jangan melakukan query MikroTik satu per satu untuk setiap pelanggan.

SALAH:

```text
customer 1 → API
customer 2 → API
customer 3 → API
...
```

BENAR:

```text
1 request:
 /ppp/active/print

kemudian comparison dilakukan di Python.
```

Hal ini penting karena jumlah pelanggan dapat mencapai ratusan atau ribuan.

---

# 40. Status PPPoE

Untuk menentukan online/offline gunakan:

```text
/ppp/active/print
```

Jangan menggunakan:

```text
/ppp/secret/print
```

untuk menentukan status koneksi.

Karena user menggunakan RADIUS pihak ketiga, database lokal hanya berfungsi sebagai daftar pelanggan yang harus dipantau.

---

# 41. Perbedaan Data RADIUS

Sistem tidak perlu mengelola:

```text
PPP Secret
```

di MikroTik.

Database lokal:

```text
Customer Database
```

berisi daftar pelanggan.

MikroTik:

```text
Active PPPoE Sessions
```

menjadi sumber status realtime.

---

# 42. Format Username

Username harus dibandingkan secara konsisten.

Gunakan:

```python
username.strip()
```

dan hindari perbedaan:

```text
FAIZ001
faiz001
```

Jika sistem ingin case-sensitive, gunakan case-sensitive secara konsisten.

Default yang disarankan:

```text
username dianggap case-sensitive
```

karena username RADIUS dapat membedakan huruf besar/kecil.

---

# 43. Data Pelanggan Export

Export harus menggunakan kolom yang sama dengan template:

```text
customer_code
username
customer_name
phone
address
package
monitoring_enabled
notes
```

Dengan demikian:

```text
Download
   ↓
Edit Excel
   ↓
Upload
   ↓
Update Database
```

dapat dilakukan tanpa mengubah format.

---

# 44. Backup Sebelum Import

Sebelum melakukan import massal, buat backup database SQLite.

Contoh:

```text
data/backups/
```

Nama:

```text
traffic_20261002_211000.db
```

Jika import gagal atau terjadi masalah, database dapat dipulihkan.

---

# 45. Transaction

Import harus menggunakan database transaction.

Jika terjadi error:

```text
ROLLBACK
```

Jangan sampai 50 data sudah masuk sementara 20 data berikutnya gagal dan database berada dalam kondisi setengah ter-update.

---

# 46. Systemd

Aplikasi existing tetap menggunakan:

```text
systemd/mikrotik-traffic-monitor.service
```

Telegram Bot harus berjalan sebagai bagian dari service yang sama.

Contoh konsep:

```text
systemd
   │
   ▼
FastAPI Application
   ├── Traffic Monitor
   └── Telegram Bot
```

Jangan membuat service kedua kecuali benar-benar diperlukan oleh arsitektur framework.

---

# 47. Lifecycle Application

Saat aplikasi startup:

```text
Application startup
       │
       ├── Initialize database
       ├── Initialize MikroTik client
       ├── Start traffic collector
       ├── Start FastAPI
       └── Start Telegram bot
```

Saat shutdown:

```text
Application shutdown
       │
       ├── Stop Telegram bot
       ├── Stop traffic collector
       ├── Close MikroTik connection
       └── Close database
```

Pastikan tidak ada task asyncio yang tertinggal.

---

# 48. Tidak Mengganggu Traffic Monitoring

Fitur Telegram tidak boleh mengganggu:

```text
Traffic Collector
Traffic API
Web Dashboard
Historical Traffic
```

Telegram bot harus menjadi modul independen di dalam aplikasi.

Jika Telegram mengalami error, web traffic monitoring tetap harus berjalan.

Jika MikroTik API gagal saat `/cek_off`, traffic monitoring juga tidak boleh crash.

---

# 49. Web Dashboard

Tidak perlu mengubah frontend traffic monitoring secara signifikan.

Fitur utama tetap:

```text
Traffic Monitoring
```

Telegram PPPoE merupakan modul tambahan.

Tidak perlu membuat dashboard pelanggan PPPoE di web pada versi pertama.

---

# 50. Testing

Tambahkan test:

```text
tests/test_pppoe_service.py
tests/test_customer_repository.py
tests/test_excel.py
tests/test_telegram.py
```

Minimal test:

### Customer

```text
create customer
update customer
upsert customer
duplicate username
```

### PPPoE

```text
all online
some offline
all offline
empty database
```

### MikroTik

```text
API success
API timeout
API connection error
```

### Excel

```text
valid Excel
missing username
duplicate username
invalid extension
empty Excel
update existing customer
insert new customer
```

---

# 51. Contoh Unit Test Deteksi OFF

Input database:

```text
user01
user02
user03
user04
```

MikroTik active:

```text
user01
user03
```

Expected:

```text
user02
user04
```

---

# 52. Idempotency

Menjalankan:

```text
/cek_off
```

berulang kali tidak boleh mengubah database pelanggan.

Command tersebut hanya membaca:

```text
customers
```

dan:

```text
/ppp/active
```

kemudian menghasilkan report.

---

# 53. Tidak Menyimpan Status OFF Permanen

Versi pertama tidak perlu membuat tabel history status PPPoE.

Status:

```text
ONLINE
OFFLINE
```

dihitung realtime ketika:

```text
/cek_off
```

dipanggil.

Tujuan versi pertama adalah monitoring sederhana dan ringan.

---

# 54. Future Extension

Arsitektur harus memungkinkan penambahan fitur di masa depan seperti:

```text
/cek_on
/status pelanggan
/notifikasi pelanggan OFF
/notifikasi pelanggan kembali ON
/history pelanggan
/durasi offline
```

Tetapi fitur-fitur tersebut JANGAN dibuat pada versi pertama kecuali diperlukan untuk implementasi inti.

---

# 55. Struktur Direktori Final

Target struktur:

```text
.
├── app
│   ├── api
│   │   ├── routes_config.py
│   │   ├── routes_interfaces.py
│   │   ├── routes_status.py
│   │   └── routes_traffic.py
│   │
│   ├── core
│   │   ├── config.py
│   │   ├── duration.py
│   │   ├── logging.py
│   │   └── __init__.py
│   │
│   ├── database
│   │   ├── database.py
│   │   ├── models.py
│   │   └── repository.py
│   │
│   ├── mikrotik
│   │   ├── client.py
│   │   └── collector.py
│   │
│   ├── services
│   │   ├── traffic_service.py
│   │   └── pppoe_service.py
│   │
│   ├── telegram
│   │   ├── __init__.py
│   │   ├── bot.py
│   │   ├── handlers.py
│   │   ├── keyboards.py
│   │   └── excel.py
│   │
│   ├── main.py
│   └── __init__.py
│
├── data
│   ├── traffic.db
│   └── backups
│
├── frontend
│   ├── css
│   │   └── style.css
│   ├── js
│   │   └── app.js
│   └── index.html
│
├── systemd
│   └── mikrotik-traffic-monitor.service
│
├── tests
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_config.py
│   ├── test_database.py
│   ├── test_duration.py
│   ├── test_pppoe_service.py
│   ├── test_customer_repository.py
│   ├── test_excel.py
│   └── test_telegram.py
│
├── README.md
├── requirements.txt
└── .env
```

---

# 56. Konfigurasi .env Final

Pertahankan konfigurasi existing dan tambahkan:

```env
# ==============================
# MIKROTIK CONFIGURATION
# ==============================
MIKROTIK_HOST=192.168.1.1
MIKROTIK_PORT=8728
MIKROTIK_USERNAME=monitor
MIKROTIK_PASSWORD=password
MIKROTIK_USE_SSL=false
MIKROTIK_VERIFY_SSL=false

# ==============================
# INTERFACE MONITORING
# ==============================
MONITORED_INTERFACES=ether1-BAROKAH,ether2-BIZ,ether3-WAHED

# ==============================
# POLLING
# ==============================
POLL_INTERVAL=5

# ==============================
# DATABASE
# ==============================
DATABASE_PATH=./data/traffic.db

# ==============================
# WEB SERVER
# ==============================
WEB_HOST=0.0.0.0
WEB_PORT=8080

# ==============================
# GRAPH CONFIGURATION
# ==============================
GRAPH_PERIODS=5m,15m,30m,1h,12h,24h
GRAPH_DEFAULT_PERIOD=15m
GRAPH_REALTIME_MAX=30m
GRAPH_REFRESH_INTERVAL=5000
GRAPH_MAX_POINTS=500

# ==============================
# DATA RETENTION
# ==============================
DATA_RETENTION=30d

# ==============================
# TELEGRAM BOT
# ==============================
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
TELEGRAM_ALLOWED_CHAT_IDS=123456789
```

---

# 57. Acceptance Criteria

Fitur dianggap selesai apabila:

### Telegram

* [ ] Bot dapat dijalankan bersama aplikasi existing.
* [ ] `/start` bekerja.
* [ ] `/menu` bekerja.
* [ ] `/cek_off` bekerja.
* [ ] User yang tidak diizinkan ditolak.
* [ ] Telegram error tidak menyebabkan FastAPI mati.

### MikroTik

* [ ] Menggunakan API port 8728.
* [ ] Tidak menggunakan API-SSL.
* [ ] Dapat mengambil `/ppp/active/print`.
* [ ] Tidak melakukan request satu per pelanggan.

### Database

* [ ] Database existing tetap digunakan.
* [ ] Tabel customers tersedia.
* [ ] Username unik.
* [ ] Import menggunakan transaction.
* [ ] Backup dibuat sebelum import.

### Excel

* [ ] Template dapat didownload.
* [ ] Data pelanggan dapat didownload.
* [ ] Excel dapat diupload.
* [ ] Validasi dilakukan sebelum commit.
* [ ] Existing customer dapat di-update.
* [ ] Customer baru dapat ditambahkan.
* [ ] File invalid ditolak.

### /cek_off

* [ ] Membandingkan database dengan `/ppp/active/print`.
* [ ] Menampilkan pelanggan offline.
* [ ] Menampilkan jumlah online/offline.
* [ ] Jika MikroTik gagal, tidak menganggap pelanggan sebagai OFF.
* [ ] Jika semua online, menampilkan pesan yang sesuai.
* [ ] Tidak mengubah database.

### Existing Traffic Monitor

* [ ] Dashboard tetap berjalan.
* [ ] Traffic collector tetap berjalan.
* [ ] API existing tetap berjalan.
* [ ] Tidak terjadi konflik event loop.
* [ ] Tidak ada koneksi MikroTik redundant yang tidak diperlukan.

---

# 58. Urutan Implementasi

Antigravity harus mengimplementasikan dalam urutan berikut:

```text
STEP 1
Analisis kode existing.

STEP 2
Identifikasi database dan MikroTik client existing.

STEP 3
Tambahkan Customer model.

STEP 4
Tambahkan repository customer.

STEP 5
Tambahkan PPPoE service.

STEP 6
Tambahkan Telegram dependency.

STEP 7
Tambahkan Telegram bot.

STEP 8
Tambahkan Excel template/export/import.

STEP 9
Tambahkan authorization Telegram.

STEP 10
Integrasikan lifecycle Telegram dengan FastAPI.

STEP 11
Tambahkan backup database sebelum import.

STEP 12
Tambahkan unit test.

STEP 13
Update README.

STEP 14
Update systemd service jika diperlukan.

STEP 15
Jalankan seluruh test.

STEP 16
Pastikan traffic monitoring existing tetap berjalan.

STEP 17
Berikan instruksi deployment ke STB Ubuntu.
```

---

# 59. Prinsip Penting Untuk Antigravity

JANGAN:

* membuat aplikasi baru dari nol;
* membuat database baru;
* membuat koneksi MikroTik baru jika client existing dapat digunakan;
* mengubah API menjadi API-SSL;
* menghapus fitur traffic monitoring;
* mengubah frontend yang tidak diperlukan;
* menyimpan password Telegram atau MikroTik di database;
* menganggap semua pelanggan OFF ketika MikroTik gagal;
* melakukan query MikroTik satu per satu untuk setiap pelanggan;
* langsung commit Excel tanpa validasi.

WAJIB:

* mempertahankan backward compatibility;
* menggunakan database existing;
* menggunakan MikroTik client existing;
* menggunakan RouterOS API port 8728;
* menggunakan transaction untuk import;
* membuat backup database;
* melakukan authorization Telegram;
* menggunakan async architecture yang kompatibel dengan FastAPI;
* menangani error dengan baik;
* membuat unit test;
* memperbarui README;
* memastikan aplikasi existing tetap berjalan normal.

---

# 60. Definition of Done

Implementasi dianggap selesai ketika pada STB Ubuntu dapat menjalankan:

```bash
sudo systemctl restart mikrotik-traffic-monitor
```

kemudian:

```bash
systemctl status mikrotik-traffic-monitor
```

menunjukkan:

```text
active (running)
```

Web traffic monitor tetap dapat diakses:

```text
http://IP-STB:8080
```

dan Telegram Bot dapat digunakan:

```text
/start
```

kemudian:

```text
/cek_off
```

menghasilkan daftar pelanggan PPPoE yang sedang offline berdasarkan perbandingan:

```text
Customer Database
        VS
MikroTik /ppp/active/print
```

Selain itu user dapat melakukan:

```text
Telegram
   │
   ├── Download Template Excel
   ├── Upload Excel
   ├── Update Customer
   ├── Download Data Customer
   └── Cek PPPoE OFF
```

tanpa mengganggu fungsi utama:

```text
MikroTik Traffic Monitor
```

yang sudah berjalan.
