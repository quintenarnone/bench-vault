from __future__ import annotations

import csv
import shutil
import sqlite3
from pathlib import Path
from typing import Any

APP_DIR = Path.home() / ".local" / "share" / "benchvault"
PHOTO_DIR = APP_DIR / "photos"
DB_PATH = APP_DIR / "benchvault.db"


def connect() -> sqlite3.Connection:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db() -> None:
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'Unsorted',
            manufacturer TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            quantity INTEGER NOT NULL DEFAULT 1,
            condition TEXT NOT NULL DEFAULT 'Unknown',
            location TEXT NOT NULL DEFAULT 'Unsorted',
            tags TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            photo_path TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Needs identification',
            datasheet_url TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Planning'
        );
        CREATE TABLE IF NOT EXISTS item_projects (
            item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            PRIMARY KEY (item_id, project_id)
        );
        CREATE TABLE IF NOT EXISTS test_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            tested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            result TEXT NOT NULL DEFAULT 'Untested',
            measurements TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS project_reservations (
            item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            quantity INTEGER NOT NULL DEFAULT 1,
            notes TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(item_id, project_id)
        );
        CREATE TABLE IF NOT EXISTS storage_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            parent TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL DEFAULT 'Storage',
            capacity INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
        CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
        """)
        # Safe additive migrations: never replace or reset the user's inventory.
        item_columns = {r[1] for r in con.execute("PRAGMA table_info(items)")}
        if "datasheet_url" not in item_columns:
            con.execute("ALTER TABLE items ADD COLUMN datasheet_url TEXT NOT NULL DEFAULT ''")
        if con.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0:
            starter = [
                ("Small green development board", "Embedded", "", "Needs inspection", 1, "Unknown", "Desk → Front-left", "microcontroller; PCB", "Visible in desk photo; identify silkscreen/model before use.", "", "Needs identification"),
                ("Second small development board", "Embedded", "", "Needs inspection", 1, "Unknown", "Desk → Front-left", "microcontroller; PCB", "Visible in desk photo; exact board/model unknown.", "", "Needs identification"),
                ("Third small development board", "Embedded", "", "Needs inspection", 1, "Unknown", "Desk → Front-left", "microcontroller; PCB", "Visible in desk photo; exact board/model unknown.", "", "Needs identification"),
                ("Dell laptop motherboard", "Computer hardware", "Dell", "Needs inspection", 1, "Used / untested", "Desk → Main work surface", "motherboard; laptop", "Loose motherboard visible in photo. Identify laptop model and board markings.", "", "Needs identification"),
                ("Dell laptop battery", "Computer hardware", "Dell", "43 Wh (label)", 1, "Used / untested", "Desk → Main work surface", "battery; lithium-ion", "Do not use if swollen, damaged, hot, or leaking. Do not puncture or open.", "", "Needs identification"),
                ("Laptop RAM module", "Computer hardware", "", "Needs inspection", 1, "Used / untested", "Desk → Main work surface", "RAM; memory", "Visible memory module; confirm generation/capacity from label.", "", "Needs identification"),
                ("USB-to-VGA adapter", "Cables & adapters", "Tripp Lite", "Needs inspection", 1, "Unknown", "Drawer → Adapter drawer", "USB; VGA; display", "Brand visible in photo; exact model should be read from label.", "", "Needs identification"),
                ("USB-to-DVI adapter", "Cables & adapters", "Tripp Lite", "Needs inspection", 1, "Unknown", "Drawer → Adapter drawer", "USB; DVI; display", "Brand visible in photo; exact model should be read from label.", "", "Needs identification"),
                ("Ethernet cable", "Cables & adapters", "TechData Cyber Range", "Needs inspection", 1, "Unknown", "Drawer → Cable drawer", "Ethernet; networking", "Several blue cables visible; count and cable category not confirmed.", "", "Needs identification"),
                ("Power adapter / supply", "Power", "", "Needs inspection", 1, "Unknown", "Drawer → Cable drawer", "power; adapter", "Multiple adapters visible; create separate records once labels are checked.", "", "Needs identification"),
                ("Achieva/Achiever-branded device", "Networking", "Unknown", "Needs inspection", 1, "Unknown", "Drawer → Cable drawer", "networking; identify", "Black device with circular top marking; exact product not confirmed.", "", "Needs identification"),
                ("Dell diagnostic device", "Computer hardware", "Dell", "Needs inspection", 1, "Unknown", "Drawer → Electronics drawer", "diagnostics; legacy", "Label appears to say Dell Diagnostics; identify interface and function.", "", "Needs identification"),
                ("Arduino-compatible board", "Embedded", "", "Needs inspection", 1, "Unknown", "Drawer → Electronics drawer", "Arduino; microcontroller", "A board resembling an Arduino is visible; confirm exact board.", "", "Needs identification"),
                ("Data CD-RW spindle", "Storage & media", "imation", "10x–24x (label)", 1, "Unused / unknown", "Drawer → Media drawer", "optical media; CD-RW", "Visible packaging; verify whether discs are still useful.", "", "Needs identification"),
            ]
            con.executemany("""
                INSERT INTO items
                (name, category, manufacturer, model, quantity, condition, location, tags, notes, photo_path, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, starter)
        # Populate the location registry from existing item locations without changing them.
        for loc in con.execute("SELECT DISTINCT location FROM items WHERE TRIM(location) != ''"):
            con.execute("INSERT OR IGNORE INTO storage_locations(name) VALUES (?)", (loc[0],))
        for name, desc in [
            ("BenchVault", "Inventory system itself and future improvements."),
            ("Laptop resurrection lab", "Identify and test reusable laptop components."),
            ("Embedded Wi-Fi monitor", "Potential sensor / network-status node."),
        ]:
            con.execute("INSERT OR IGNORE INTO projects(name, description) VALUES (?, ?)", (name, desc))


def list_items(search: str = "", category: str = "All categories") -> list[sqlite3.Row]:
    with connect() as con:
        sql = "SELECT * FROM items WHERE 1=1"
        args: list[Any] = []
        if search.strip():
            needle = f"%{search.strip()}%"
            sql += " AND (name LIKE ? OR category LIKE ? OR manufacturer LIKE ? OR model LIKE ? OR location LIKE ? OR tags LIKE ? OR notes LIKE ?)"
            args.extend([needle] * 7)
        if category != "All categories":
            sql += " AND category = ?"
            args.append(category)
        sql += " ORDER BY updated_at DESC, name COLLATE NOCASE"
        return con.execute(sql, args).fetchall()


def get_item(item_id: int) -> sqlite3.Row | None:
    with connect() as con:
        return con.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()


def save_item(data: dict[str, Any], item_id: int | None = None) -> int:
    fields = ["name", "category", "manufacturer", "model", "quantity", "condition", "location", "tags", "notes", "photo_path", "status", "datasheet_url"]
    values = [data.get(k, "") for k in fields]
    values[0] = values[0].strip() or "Untitled component"
    values[1] = values[1].strip() or "Unsorted"
    values[4] = max(0, int(values[4] or 0))
    values[5] = values[5] or "Unknown"
    values[6] = values[6] or "Unsorted"
    with connect() as con:
        if item_id:
            with con:
                con.execute(
                    f"UPDATE items SET {', '.join(f'{f}=?' for f in fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (*values, item_id),
                )
                con.execute("INSERT OR IGNORE INTO storage_locations(name) VALUES (?)", (values[6],))
            return item_id
        with con:
            cur = con.execute(
                f"INSERT INTO items ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
                values,
            )
            con.execute("INSERT OR IGNORE INTO storage_locations(name) VALUES (?)", (values[6],))
            return int(cur.lastrowid)


def delete_item(item_id: int) -> None:
    with connect() as con:
        con.execute("DELETE FROM items WHERE id=?", (item_id,))


def categories() -> list[str]:
    with connect() as con:
        return [r[0] for r in con.execute("SELECT DISTINCT category FROM items ORDER BY category COLLATE NOCASE")]


def projects() -> list[sqlite3.Row]:
    with connect() as con:
        return con.execute("SELECT * FROM projects ORDER BY name COLLATE NOCASE").fetchall()


def item_project_names(item_id: int) -> list[str]:
    with connect() as con:
        return [r[0] for r in con.execute("""
            SELECT p.name FROM projects p JOIN item_projects ip ON p.id=ip.project_id
            WHERE ip.item_id=? ORDER BY p.name
        """, (item_id,))]


def set_item_projects(item_id: int, names: list[str]) -> None:
    with connect() as con:
        con.execute("DELETE FROM item_projects WHERE item_id=?", (item_id,))
        for name in names:
            name = name.strip()
            if not name:
                continue
            con.execute("INSERT OR IGNORE INTO projects(name) VALUES (?)", (name,))
            project_id = con.execute("SELECT id FROM projects WHERE name=?", (name,)).fetchone()[0]
            con.execute("INSERT OR IGNORE INTO item_projects(item_id, project_id) VALUES (?, ?)", (item_id, project_id))


def save_photo(source: str) -> str:
    src = Path(source)
    if not src.exists():
        return ""
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    target = PHOTO_DIR / src.name
    stem, suffix = target.stem, target.suffix
    n = 2
    while target.exists():
        target = PHOTO_DIR / f"{stem}-{n}{suffix}"
        n += 1
    shutil.copy2(src, target)
    return str(target)


def import_csv(path: str) -> tuple[int, int]:
    """Import rows, returning (created, skipped). Supports common column names."""
    aliases = {
        "name": "name", "item": "name", "component": "name", "title": "name",
        "category": "category", "type": "category",
        "manufacturer": "manufacturer", "brand": "manufacturer",
        "model": "model", "part_number": "model", "part number": "model",
        "quantity": "quantity", "qty": "quantity", "count": "quantity",
        "condition": "condition", "location": "location", "storage": "location", "drawer": "location",
        "tags": "tags", "notes": "notes", "description": "notes", "status": "status",
        "projects": "projects", "project": "projects", "datasheet_url": "datasheet_url", "datasheet": "datasheet_url", "url": "datasheet_url",
    }
    created = skipped = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return 0, 0
        for raw in reader:
            mapped: dict[str, str] = {}
            for key, value in raw.items():
                if key is None:
                    continue
                field = aliases.get(key.strip().lower())
                if field:
                    mapped[field] = (value or "").strip()
            if not mapped.get("name"):
                skipped += 1
                continue
            item_id = save_item({
                "name": mapped.get("name", ""),
                "category": mapped.get("category", "Unsorted"),
                "manufacturer": mapped.get("manufacturer", ""),
                "model": mapped.get("model", ""),
                "quantity": mapped.get("quantity", "1") or "1",
                "condition": mapped.get("condition", "Unknown"),
                "location": mapped.get("location", "Unsorted"),
                "tags": mapped.get("tags", ""),
                "notes": mapped.get("notes", ""),
                "photo_path": "",
                "status": mapped.get("status", "Needs identification") or "Needs identification",
                "datasheet_url": mapped.get("datasheet_url", ""),
            })
            names = [p.strip() for p in mapped.get("projects", "").split(";") if p.strip()]
            if names:
                set_item_projects(item_id, names)
            created += 1
    return created, skipped


def export_csv(path: str) -> int:
    rows = list_items()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "category", "manufacturer", "model", "quantity", "condition", "location", "tags", "notes", "status", "datasheet_url", "projects"])
        for r in rows:
            writer.writerow([r["id"], r["name"], r["category"], r["manufacturer"], r["model"], r["quantity"], r["condition"], r["location"], r["tags"], r["notes"], r["status"], r["datasheet_url"], "; ".join(item_project_names(r["id"]))])
    return len(rows)
