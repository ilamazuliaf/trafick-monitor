# MikroTik Traffic Monitor

A lightweight, configuration-driven web application to monitor interface traffic (RX/TX rates, real-time & historical graphs) on MikroTik RouterOS devices. Built specifically for low-resource Linux deployment (e.g. STB Ubuntu / Ubuntu Server).

---

## 🏗 Architecture & Configuration Principles

- **Configuration-Driven**: All application settings originate exclusively from `.env`.
- **Single Source of Truth**: Backend exposes configuration via `GET /api/config`. Frontend dynamically builds cards, dropdowns, and timers without hardcoded interfaces or graph periods.
- **Generic Duration Engine**: Generic `m`, `h`, `d` parser supports arbitrary time windows (e.g., `5m`, `15m`, `1h`, `2d`, `7d`).

---

## 🚀 Quick Start & Installation

### 1. Requirements
- Python 3.9+
- Linux (Ubuntu / STB Ubuntu recommended) or Windows

### 2. Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the example environment file and configure your MikroTik router credentials and interface settings:

```bash
cp .env.example .env
nano .env
```

---

## ⚙️ Configuration (.env) Parameters

| Variable | Default | Description |
| :--- | :--- | :--- |
| `MIKROTIK_HOST` | `192.168.1.1` | RouterOS IP address or hostname |
| `MIKROTIK_PORT` | `8728` | RouterOS API port (`8728` standard, `8729` for SSL) |
| `MIKROTIK_USERNAME` | `monitor` | API Username |
| `MIKROTIK_PASSWORD` | `password` | API Password |
| `MIKROTIK_USE_SSL` | `false` | Enable API-SSL connection |
| `MIKROTIK_VERIFY_SSL` | `false` | Verify SSL certificate validity |
| `MONITORED_INTERFACES` | `ether1-BAROKAH,ether2-BIZ,ether3-WAHED` | Comma-separated list of interface names to monitor |
| `POLL_INTERVAL` | `5` | MikroTik polling interval in seconds |
| `DATABASE_PATH` | `./data/traffic.db` | SQLite database file location |
| `WEB_HOST` | `0.0.0.0` | Web server bind IP |
| `WEB_PORT` | `8080` | Web server bind port |
| `GRAPH_PERIODS` | `5m,15m,30m,1h,12h,24h` | Time duration choices for frontend chart |
| `GRAPH_DEFAULT_PERIOD` | `15m` | Default selected period (must exist in `GRAPH_PERIODS`) |
| `GRAPH_REALTIME_MAX` | `30m` | Periods <= `GRAPH_REALTIME_MAX` are auto-refreshed in real-time |
| `GRAPH_REFRESH_INTERVAL` | `5000` | Real-time frontend refresh interval in milliseconds |
| `GRAPH_MAX_POINTS` | `500` | Maximum points returned after downsampling |
| `DATA_RETENTION` | `30d` | Historical data retention limit before cleanup |
| `TELEGRAM_ENABLED` | `true` | Enable Telegram Bot module |
| `TELEGRAM_BOT_TOKEN` | `YOUR_TELEGRAM_BOT_TOKEN` | Bot Father API Token |
| `TELEGRAM_ALLOWED_CHAT_IDS` | `123456789` | Comma-separated allowed Telegram Chat IDs |
| `ISOLATED_IP_RANGE` | `10.127.0.0/18` | Subnet CIDR IP isolir pelanggan PPPoE |

---

## 🤖 Telegram Bot Monitoring & Management

Sistem terintegrasi penuh dengan Telegram Bot untuk pemantauan koneksi PPPoE MikroTik, perbandingan data pelanggan lokal vs router, pemantauan OLT GPON/EPON, dan manajemen pelanggan berbasis Excel.

### 📋 Daftar Command Telegram:
- `/start` - Menampilkan menu interaktif utama (Inline Keyboard).
- `/menu` - Membuka menu utama Telegram Bot.
- `/cek_pelanggan` - Membandingkan data pelanggan di database lokal dengan sesi aktif di MikroTik (`/ppp/active/print`), menampilkan daftar pelanggan aktif di MikroTik yang belum terdaftar di database.
- `/cek_off` - Memeriksa status pelanggan PPPoE yang sedang OFFLINE dengan membandingkan data pelanggan dipantau di database terhadap sesi aktif MikroTik.
- `/cek_isolir` - Memeriksa daftar pelanggan PPPoE yang mendapatkan IP isolir berdasarkan subnet CIDR (`ISOLATED_IP_RANGE`).
- `/pelanggan` - Menampilkan menu manajemen data pelanggan PPPoE (download template, export, import).
- `/cek_putus` - Memeriksa daftar ONT berstatus OFFLINE dikelompokkan per PON (Modul OLT).
- `/cek_redaman` - Memeriksa ONT dengan RX Power optik di bawah ambang batas / threshold redaman (Modul OLT).
- `/olt_status` - Memeriksa status koneksi SNMP ke perangkat OLT (Modul OLT).

### 🔍 Fitur & Kemampuan Telegram Bot:

1. **Cek Data Pelanggan (`/cek_pelanggan` & Tombol "🔍 Cek Data Pelanggan")**:
   - Membandingkan seluruh data pelanggan di database SQLite dengan sesi aktif PPPoE di MikroTik (`/ppp/active/print`).
   - Mendeteksi user atau koneksi aktif liar/baru di MikroTik yang tidak tercatat di database lokal.
   - Menampilkan detail user yang tidak terdaftar: Username, IP Address, Caller ID (MAC/Interface), Uptime koneksi, dan Tipe Service.
   - Dilengkapi sistem auto-pagination jika jumlah daftar pelanggan melebihi batas karakter pesan Telegram.

2. **Monitoring PPPoE Offline & Isolir**:
   - **Cek PPPoE OFF (`/cek_off`)**: Memantau pelanggan terdaftar yang koneksinya mati/putus.
   - **Cek PPPoE Isolir (`/cek_isolir`)**: Mendeteksi pelanggan yang terisolir (mendapatkan IP isolir dari pool penagihan).

3. **Manajemen Pelanggan via Excel (`/pelanggan`)**:
   - **Download Template Excel**: Mengunduh file `.xlsx` template standar yang siap diisi.
   - **Export Data Pelanggan**: Mengunduh seluruh database pelanggan ke file Excel `.xlsx`.
   - **Import / Update Excel**: Mengunggah file Excel `.xlsx` langsung ke chat bot untuk menambah dan memperbarui data pelanggan, lengkap dengan validasi data dan pratinjau (preview).
   - **Backup Otomatis**: Setiap proses import otomatis membuat salinan cadangan database di direktori `data/backups/`.

4. **Monitoring OLT SNMP (GPON/EPON)**:
   - **Cek ONT Putus (`/cek_putus`)**: Menampilkan daftar ONT offline per port PON.
   - **Cek Redaman Tinggi (`/cek_redaman`)**: Menampilkan daftar ONT dengan sinyal optik RX yang buruk (redaman tinggi).
   - **Status OLT (`/olt_status`)**: Mengecek status ketersediaan dan respon perangkat OLT via SNMP.

5. **Monitoring Traffic Interface**:
   - Melalui tombol `📊 Traffic Monitor` pada menu utama, Anda dapat melihat ringkasan kecepatan RX/TX realtime dari interface MikroTik yang dipantau.

6. **Navigasi Interaktif (Inline Keyboard)**:
   - Akses cepat sekali sentuh tanpa perlu mengetik command:
     - `🔴 Cek PPPoE OFF`
     - `🟡 Cek PPPoE Isolir`
     - `🔌 Cek ONT Putus`
     - `📶 Cek Redaman`
     - `🔍 Cek Data Pelanggan`
     - `👥 Data Pelanggan`
     - `📊 Traffic Monitor`


## 💻 Running the Application

### Development / Direct Run
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```
Open browser at `http://localhost:8080` or `http://<server-ip>:8080`.

### Running Automated Tests
```bash
pytest
```

---

## 🐧 Systemd Deployment (Ubuntu STB Server)

1. Copy application files to `/opt/mikrotik-traffic-monitor`:
   ```bash
   sudo mkdir -p /opt/mikrotik-traffic-monitor
   sudo cp -r . /opt/mikrotik-traffic-monitor/
   cd /opt/mikrotik-traffic-monitor
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

2. Install systemd service:
   ```bash
   sudo cp systemd/mikrotik-traffic-monitor.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable mikrotik-traffic-monitor
   sudo systemctl start mikrotik-traffic-monitor
   ```

3. Check service status & logs:
   ```bash
   sudo systemctl status mikrotik-traffic-monitor
   sudo journalctl -u mikrotik-traffic-monitor -f
   ```

---

## 🔧 Troubleshooting

### 1. Connection Failure (`mikrotik: false`)
- Verify MikroTik IP, API port (`8728`), and firewall rules.
- Ensure API service is enabled on MikroTik: `/ip service enable api`.

### 2. Authentication Failed
- Verify `MIKROTIK_USERNAME` and `MIKROTIK_PASSWORD` in `.env`.
- Ensure the user has `read` and `api` permissions in RouterOS (`/user group`).

### 3. Invalid Configuration Error on Startup
- Ensure `GRAPH_DEFAULT_PERIOD` is present inside `GRAPH_PERIODS`.
- Ensure all duration values match the format `^\d+(m|h|d)$` (e.g. `5m`, `1h`, `2d`).

### 4. Self-Signed Certificate Errors (API-SSL)
- If `MIKROTIK_USE_SSL=true` and using self-signed certificates, set `MIKROTIK_VERIFY_SSL=false` in `.env`.
