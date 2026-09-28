# Warlocks Sales Tracker

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Electron](https://img.shields.io/badge/Electron-28-47848F?logo=electron&logoColor=white)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A sales-tracking product family for a real small business — inventory, point-of-sale style checkout, sales history, and tamper-evident receipts. Shipping in **three implementations** that share the same data model and visual brand:

1. **`python/`** — a Python / CustomTkinter desktop app (neon "Warlocks" theme, custom-rendered logo with bundled fonts).
2. **`electron/`** — a cross-platform Electron desktop app with secure preload bridge, JSON import/export, and CSV export.
3. **`web/`** — a PHP + MySQL PWA for online/offline sales, role-based users (owner/cashier), and **daily receipt anchoring to an EVM blockchain** via a sidecar Python signer worker.

---

## Features (across all variants)

| Capability | Python | Electron | Web |
|---|---|---|---|
| Add / edit / remove products | ✅ | ✅ | ✅ |
| Categories & search | ✅ | ✅ | ✅ |
| Quantity counter (+/- and manual) | ✅ | ✅ | ✅ |
| Built-in calculator | ✅ | ✅ | ✅ |
| Sales history & totals | ✅ | ✅ | ✅ |
| JSON save / load | ✅ | ✅ | — |
| CSV export | ✅ | ✅ | — |
| PWA offline + service worker | — | — | ✅ |
| Owner / cashier roles | — | — | ✅ |
| Receipt anchoring (blockchain) | — | — | ✅ |

> Money is stored as **integer centavos** (never floats) to eliminate rounding drift.

## Getting Started

### Python app

```bash
pip install customtkinter pillow numpy
python python/sales_tracker.py
```

### Electron app

```bash
cd electron
npm install
npm start
# Windows installer:
npm run build-win
```

### Web app (PWA + API)

```bash
# 1. Import schema
mysql < web/schema.sql
# 2. Edit web/api/config.php with your MySQL credentials
# 3. (optional) anchoring — run the sidecar signer once a day:
pip install -r web/signer/requirements.txt
python web/signer/sign.py
```

## Repository Layout

```
├── python/       CustomTkinter desktop app + PyInstaller spec + brand assets
├── electron/     Electron main/preload + renderer + electron-builder config
└── web/          PHP API, MySQL schema, PWA frontend, cron anchor, blockchain signer
```

## Project notes

Built for the **"Warlocks"** store brand (dark / neon-red identity — see the custom logo-rendering and font pipeline in `python/process_logo.py`). The web variant is Filipino-first UI ("Transparent na sales tracker para sa Warlocks").

## License

[MIT](LICENSE) © AJ Nietes