# BenchVault 0.3.0 — Electronics Workshop Manager

BenchVault is a local-first electronics inventory and workshop manager built with Python, PySide6, and SQLite. It uses a pure-black background, muted-purple selections, and sunset-peach highlights.

## Run on Linux / CachyOS

From the extracted `benchvault` directory:

```bash
chmod +x run.sh
./run.sh
```

The launcher creates `.venv`, installs dependencies, and starts the app. Python 3.11+ is required. QR label generation uses the `qrcode` package, installed automatically by the launcher.

## Features

- **Inventory:** component records, category, maker, model/part number, quantity, condition, tags, status, notes, photo, location, and datasheet/reference URL.
- **Storage map:** cards for locations used by the inventory, contents, quantities, and move-to-location workflow. Use descriptive hierarchical names such as `Desk → Drawer 1 → Bin A` to represent compartments.
- **Project associations:** link inventory records to projects.
- **Project reservations:** reserve a quantity of a component for a project, with a stock quantity check.
- **Hardware testing log:** save results, measurements, test notes, and timestamps. Test results update the component's condition/status.
- **Global search:** Ctrl+K opens search across component names, models, categories, locations, tags, and notes.
- **Bulk edit:** multi-select inventory rows with Ctrl/Shift and update location, status, condition, or tags together.
- **Duplicate review:** find possible duplicates by matching name and model. This only reports candidates; it does not delete or merge records.
- **QR labels:** generate per-item QR PNGs and a printable HTML sheet. QR contents are local record details, not a public web link.
- **Printable inventory labels:** create a print-ready HTML sheet with names, locations, categories, IDs, and quantities.
- **Datasheets:** save and open an HTTP(S) datasheet/product reference from a component record.
- **CSV import/export:** bulk transfer inventory records.
- **Backup/restore:** create a ZIP containing the SQLite database and local photos. Restore automatically snapshots the current data first under `pre-restore-backups`.
- **Local photo storage:** chosen photos are copied into the app's photo directory.

## Data safety

Database: `~/.local/share/benchvault/benchvault.db`

Photos: `~/.local/share/benchvault/photos/`

The upgrade performs an additive SQLite migration for the datasheet URL field and adds supporting tables for test records, project reservations, and location metadata. It does not intentionally reset existing inventory records. Make a backup before upgrading any database-backed app.

## Practical notes

- Component identification is a manual-assisted workflow: attach a photo, enter visible chip/model markings, and save datasheet links. This release does not claim to identify parts automatically with AI.
- The QR codes contain a local component ID/name/location, not a remote URL; phone scanning can read the label, but opening a live phone inventory page requires a separately configured network service.
- Storage areas are represented by location strings, so hierarchical names (for example `Drawer → Adapter drawer → Slot 2`) are supported without forcing a fixed physical layout.
