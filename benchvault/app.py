from __future__ import annotations

import sys
import csv
import html
import shutil
import tempfile
import zipfile
import webbrowser
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QPixmap, QIcon, QKeySequence, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QStackedWidget, QDialog, QFormLayout, QTextEdit,
    QSpinBox, QFileDialog, QMessageBox, QCheckBox, QListWidget, QListWidgetItem,
    QAbstractItemView, QSplitter, QStatusBar, QToolButton, QScrollArea, QInputDialog, QDateTimeEdit, QDialogButtonBox
)

from . import db

APP_QSS = """
* { font-family: "Inter", "Noto Sans", sans-serif; font-size: 13px; }
QMainWindow, QWidget { background: #000000; color: #f2edf0; }
QFrame#Sidebar { background: #000000; border-right: 1px solid #34303d; }
QLabel#Brand { font-size: 22px; font-weight: 800; color: #fff4ed; letter-spacing: 1px; }
QLabel#SubBrand { color: #a7a4ba; font-size: 11px; }
QLabel#PageTitle { font-size: 26px; font-weight: 750; color: #fff1e8; }
QLabel#Muted { color: #aaa7b9; }
QLabel#Metric { font-size: 24px; font-weight: 750; color: #ffe1ca; }
QFrame#MetricCard, QFrame#Panel, QFrame#DetailPanel { background: #08080b; border: 1px solid #393746; border-radius: 12px; }
QPushButton { background: #111116; border: 1px solid #454052; border-radius: 8px; padding: 9px 13px; color: #f4edf0; }
QPushButton:hover { background: #373346; border-color: #d18a79; }
QPushButton#Primary { background: #f1c3a7; color: #251a20; border: 1px solid #f1c3a7; font-weight: 700; }
QPushButton#Primary:hover { background: #ffd3b7; border-color: #ffd3b7; }
QPushButton#Nav { text-align: left; padding: 11px 14px; background: transparent; border: 1px solid transparent; color: #c0bbca; }
QPushButton#Nav:checked { background: #302d3d; color: #ffe6d6; border-color: #645064; }
QLineEdit, QComboBox, QSpinBox, QTextEdit, QListWidget { background: #000000; color: #f4edf0; border: 1px solid #403c4b; border-radius: 7px; padding: 8px; selection-background-color: #66516b; selection-color: #fff8f2; }
QComboBox QAbstractItemView { background: #000000; color: #f4edf0; selection-background-color: #66516b; }
QTableWidget { background: #000000; alternate-background-color: #0b0a0f; color: #f4edf0; border: 1px solid #393746; border-radius: 9px; gridline-color: #302f3d; selection-background-color: #4a4055; selection-color: #fff7f0; }
QHeaderView::section { background: #111016; color: #d5b8b1; padding: 10px; border: none; border-bottom: 1px solid #494052; font-weight: 650; }
QTableWidget::item { padding: 7px; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QScrollBar:vertical { background: #000000; width: 10px; }
QScrollBar::handle:vertical { background: #655365; min-height: 24px; border-radius: 4px; }
QScrollBar:horizontal { background: #000000; height: 10px; }
QScrollBar::handle:horizontal { background: #655365; min-width: 24px; border-radius: 4px; }
QStatusBar { background: #000000; color: #aaa7b9; border-top: 1px solid #34303d; }
QToolButton { background: #111116; border: 1px solid #454052; border-radius: 7px; padding: 6px; }
"""

CATEGORIES = ["Computer hardware", "Embedded", "Cables & adapters", "Power", "Networking", "Storage & media", "Tools", "Robotics", "Unsorted"]
CONDITIONS = ["Unknown", "New", "Unused / unknown", "Used / untested", "Working", "Needs repair", "For parts", "Damaged"]


def label(text: str, object_name: str | None = None) -> QLabel:
    w = QLabel(text)
    if object_name:
        w.setObjectName(object_name)
    return w


class ItemDialog(QDialog):
    def __init__(self, parent=None, item=None):
        super().__init__(parent)
        self.setWindowTitle("Edit component" if item else "Add component")
        self.setMinimumWidth(620)
        self.item = item
        self.photo_path = item["photo_path"] if item else ""
        outer = QVBoxLayout(self)
        heading = label("COMPONENT RECORD", "Muted")
        outer.addWidget(heading)
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        self.name = QLineEdit(item["name"] if item else "")
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems(CATEGORIES)
        self.category.setCurrentText(item["category"] if item else "Unsorted")
        self.manufacturer = QLineEdit(item["manufacturer"] if item else "")
        self.model = QLineEdit(item["model"] if item else "")
        self.quantity = QSpinBox()
        self.quantity.setRange(0, 999999)
        self.quantity.setValue(int(item["quantity"]) if item else 1)
        self.condition = QComboBox()
        self.condition.setEditable(True)
        self.condition.addItems(CONDITIONS)
        self.condition.setCurrentText(item["condition"] if item else "Unknown")
        self.location = QLineEdit(item["location"] if item else "Unsorted")
        self.tags = QLineEdit(item["tags"] if item else "")
        self.status = QComboBox()
        self.status.setEditable(True)
        self.status.addItems(["Needs identification", "Identified", "Tested", "In use", "Archived"])
        self.status.setCurrentText(item["status"] if item else "Needs identification")
        self.datasheet_url = QLineEdit(item["datasheet_url"] if item and "datasheet_url" in item.keys() else "")
        self.datasheet_url.setPlaceholderText("https://… (datasheet or product page)")
        self.notes = QTextEdit()
        self.notes.setMinimumHeight(95)
        self.notes.setPlainText(item["notes"] if item else "")
        form.addRow("Name *", self.name)
        form.addRow("Category", self.category)
        form.addRow("Manufacturer", self.manufacturer)
        form.addRow("Model / part number", self.model)
        form.addRow("Quantity", self.quantity)
        form.addRow("Condition", self.condition)
        form.addRow("Physical location", self.location)
        form.addRow("Tags (semicolon separated)", self.tags)
        form.addRow("Status", self.status)
        form.addRow("Datasheet / reference URL", self.datasheet_url)
        form.addRow("Notes", self.notes)
        outer.addLayout(form)
        photo_row = QHBoxLayout()
        self.photo_label = label(Path(self.photo_path).name if self.photo_path else "No photo attached", "Muted")
        self.photo_label.setWordWrap(True)
        photo_btn = QPushButton("Choose photo…")
        photo_btn.clicked.connect(self.choose_photo)
        photo_row.addWidget(self.photo_label, 1)
        photo_row.addWidget(photo_btn)
        outer.addLayout(photo_row)
        self.project_checks: list[QCheckBox] = []
        project_box = QFrame()
        project_box.setObjectName("Panel")
        project_layout = QVBoxLayout(project_box)
        project_layout.addWidget(label("PROJECT ASSOCIATIONS"))
        project_names = [r["name"] for r in db.projects()]
        linked = db.item_project_names(item["id"]) if item else []
        for name in project_names:
            cb = QCheckBox(name)
            cb.setChecked(name in linked)
            self.project_checks.append(cb)
            project_layout.addWidget(cb)
        self.new_project = QLineEdit()
        self.new_project.setPlaceholderText("Add project name (optional)")
        project_layout.addWidget(self.new_project)
        outer.addWidget(project_box)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        save = QPushButton("Save component")
        save.setObjectName("Primary")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        outer.addLayout(buttons)

    def choose_photo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose component photo", str(Path.home()), "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path:
            self.photo_path = db.save_photo(path)
            self.photo_label.setText(Path(self.photo_path).name)

    def payload(self):
        return {
            "name": self.name.text(),
            "category": self.category.currentText(),
            "manufacturer": self.manufacturer.text(),
            "model": self.model.text(),
            "quantity": self.quantity.value(),
            "condition": self.condition.currentText(),
            "location": self.location.text(),
            "tags": self.tags.text(),
            "notes": self.notes.toPlainText(),
            "photo_path": self.photo_path,
            "status": self.status.currentText(),
            "datasheet_url": self.datasheet_url.text().strip(),
        }

    def selected_projects(self):
        names = [cb.text() for cb in self.project_checks if cb.isChecked()]
        extra = self.new_project.text().strip()
        if extra:
            names.append(extra)
        return names


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BenchVault — Electronics Inventory")
        self.resize(1380, 850)
        self.setMinimumSize(1050, 680)
        self.selected_id: int | None = None
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 24, 18, 18)
        side.setSpacing(8)
        side.addWidget(label("⬡ BENCHVAULT", "Brand"))
        side.addWidget(label("LOCAL HARDWARE REGISTRY", "SubBrand"))
        side.addSpacing(24)
        self.nav_inventory = QPushButton("▦   Inventory")
        self.nav_inventory.setObjectName("Nav")
        self.nav_inventory.setCheckable(True)
        self.nav_inventory.setChecked(True)
        self.nav_storage = QPushButton("▤   Storage map")
        self.nav_storage.setObjectName("Nav")
        self.nav_storage.setCheckable(True)
        self.nav_storage.clicked.connect(self.show_storage)
        self.nav_projects = QPushButton("◇   Projects")
        self.nav_projects.setObjectName("Nav")
        self.nav_projects.setCheckable(True)
        self.nav_projects.clicked.connect(self.show_projects)
        self.nav_tools = QPushButton("⌘   Workshop tools")
        self.nav_tools.setObjectName("Nav")
        self.nav_tools.setCheckable(True)
        self.nav_tools.clicked.connect(self.show_tools)
        self.nav_inventory.clicked.connect(self.show_inventory)
        side.addWidget(self.nav_inventory)
        side.addWidget(self.nav_storage)
        side.addWidget(self.nav_projects)
        side.addWidget(self.nav_tools)
        side.addStretch()
        side.addWidget(label("LOCAL DATABASE", "Muted"))
        side.addWidget(label(str(db.DB_PATH), "SubBrand"))
        root_layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, 1)
        self.inventory_page = self.build_inventory_page()
        self.projects_page = self.build_projects_page()
        self.storage_page = self.build_storage_page()
        self.tools_page = self.build_tools_page()
        self.stack.addWidget(self.inventory_page)
        self.stack.addWidget(self.storage_page)
        self.stack.addWidget(self.projects_page)
        self.stack.addWidget(self.tools_page)
        self.setStatusBar(QStatusBar())
        search_action = QAction("Global search", self)
        search_action.setShortcut(QKeySequence("Ctrl+K"))
        search_action.triggered.connect(self.global_search)
        self.addAction(search_action)
        self.statusBar().showMessage("Ready · Data stays on this machine")
        self.refresh()

    def build_inventory_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 25, 28, 22)
        layout.setSpacing(17)
        top = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.addWidget(label("Hardware inventory", "PageTitle"))
        title_col.addWidget(label("Every board, cable, adapter, and mystery component — accounted for.", "Muted"))
        top.addLayout(title_col, 1)
        import_btn = QPushButton("Import CSV")
        import_btn.clicked.connect(self.import_data)
        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self.export_data)
        add_btn = QPushButton("+ Add component")
        add_btn.setObjectName("Primary")
        add_btn.clicked.connect(self.add_item)
        bulk_btn = QPushButton("Bulk edit selected")
        bulk_btn.clicked.connect(self.bulk_edit)
        top.addWidget(import_btn)
        top.addWidget(export_btn)
        top.addWidget(bulk_btn)
        top.addWidget(add_btn)
        layout.addLayout(top)

        metrics = QHBoxLayout()
        self.metric_items = self.metric_card("TOTAL RECORDS", "0")
        self.metric_quantity = self.metric_card("TOTAL QUANTITY", "0")
        self.metric_unknown = self.metric_card("NEEDS IDENTIFICATION", "0")
        self.metric_categories = self.metric_card("CATEGORIES", "0")
        for card in [self.metric_items, self.metric_quantity, self.metric_unknown, self.metric_categories]:
            metrics.addWidget(card, 1)
        layout.addLayout(metrics)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search parts, models, tags, notes, locations…")
        self.search.textChanged.connect(self.refresh_table)
        self.category_filter = QComboBox()
        self.category_filter.addItem("All categories")
        self.category_filter.currentTextChanged.connect(self.refresh_table)
        filters.addWidget(self.search, 1)
        filters.addWidget(self.category_filter)
        layout.addLayout(filters)

        split = QSplitter(Qt.Horizontal)
        table_wrap = QFrame()
        table_wrap.setObjectName("Panel")
        table_layout = QVBoxLayout(table_wrap)
        table_layout.setContentsMargins(10, 10, 10, 10)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Component", "Category", "Model / ID", "Qty", "Condition", "Location", "Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in [1, 2, 4, 5, 6]:
            self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(3, 50)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.table.doubleClicked.connect(lambda *_: self.edit_item())
        table_layout.addWidget(self.table)
        split.addWidget(table_wrap)

        self.detail = QFrame()
        self.detail.setObjectName("DetailPanel")
        self.detail.setMinimumWidth(280)
        detail_layout = QVBoxLayout(self.detail)
        detail_layout.setContentsMargins(16, 16, 16, 16)
        detail_layout.setSpacing(10)
        self.photo_preview = QLabel("NO PHOTO")
        self.photo_preview.setAlignment(Qt.AlignCenter)
        self.photo_preview.setMinimumHeight(145)
        self.photo_preview.setStyleSheet("background:#000000;border:1px dashed #354756;border-radius:9px;color:#708497;")
        detail_layout.addWidget(self.photo_preview)
        self.detail_name = label("Select a component", "PageTitle")
        self.detail_name.setWordWrap(True)
        detail_layout.addWidget(self.detail_name)
        self.detail_meta = label("Choose a row to inspect its record.", "Muted")
        self.detail_meta.setWordWrap(True)
        detail_layout.addWidget(self.detail_meta)
        self.detail_notes = label("", "Muted")
        self.detail_notes.setWordWrap(True)
        detail_layout.addWidget(self.detail_notes, 1)
        self.detail_projects = label("", "Muted")
        self.detail_projects.setWordWrap(True)
        detail_layout.addWidget(self.detail_projects)
        self.datasheet_link = QPushButton("Open datasheet / reference")
        self.datasheet_link.clicked.connect(self.open_datasheet)
        detail_layout.addWidget(self.datasheet_link)
        self.test_btn = QPushButton("＋ Record hardware test")
        self.test_btn.clicked.connect(self.record_test)
        detail_layout.addWidget(self.test_btn)
        actions = QGridLayout()
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self.edit_item)
        self.duplicate_btn = QPushButton("Duplicate")
        self.duplicate_btn.clicked.connect(self.duplicate_item)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self.delete_item)
        actions.addWidget(self.edit_btn, 0, 0)
        actions.addWidget(self.duplicate_btn, 0, 1)
        actions.addWidget(self.delete_btn, 1, 0, 1, 2)
        detail_layout.addLayout(actions)
        split.addWidget(self.detail)
        split.setSizes([780, 350])
        layout.addWidget(split, 1)
        return page

    def refresh_storage_map(self):
        if not hasattr(self, "storage_grid"):
            return
        while self.storage_grid.count():
            item = self.storage_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        rows = db.list_items()
        grouped = {}
        for row in rows:
            location = (row["location"] or "Unsorted").strip() or "Unsorted"
            grouped.setdefault(location, []).append(row)
        locations = sorted(grouped, key=str.casefold)
        self.storage_summary.setText(f"{len(locations)} storage areas  ·  {len(rows)} component records  ·  Select a card to view or move items")
        for idx, location in enumerate(locations):
            items = grouped[location]
            card = QFrame()
            card.setObjectName("MetricCard")
            card.setMinimumHeight(126)
            card.setCursor(Qt.PointingHandCursor)
            card.setStyleSheet("QFrame#MetricCard { background:#09090d; border:1px solid #40394b; border-radius:12px; } QFrame#MetricCard:hover { border:1px solid #f1c3a7; background:#17121a; }")
            box = QVBoxLayout(card)
            box.setContentsMargins(14, 12, 14, 12)
            icon = label("▤", "Metric")
            icon.setStyleSheet("color:#f1c3a7;font-size:25px;font-weight:800;")
            box.addWidget(icon)
            name = label(location)
            name.setWordWrap(True)
            name.setStyleSheet("font-weight:700;color:#fff1e8;")
            box.addWidget(name)
            count = label(f"{len(items)} record{'s' if len(items) != 1 else ''}  ·  {sum(int(r['quantity']) for r in items)} total units", "Muted")
            box.addWidget(count)
            box.addStretch()
            card.mousePressEvent = lambda event, loc=location: self.select_storage_location(loc)
            self.storage_grid.addWidget(card, idx // 2, idx % 2)
        if self.selected_storage_location not in grouped and locations:
            self.selected_storage_location = locations[0]
        if locations:
            self.select_storage_location(self.selected_storage_location, refresh=False)
        else:
            self.selected_storage_location = ""
            self.storage_location_title.setText("No storage locations yet")
            self.storage_location_count.setText("Add a component and give it a physical location to create your first storage area.")
            self.storage_items.clear()
            self.storage_move_combo.clear()

    def select_storage_location(self, location, refresh=True):
        self.selected_storage_location = location
        rows = [r for r in db.list_items() if ((r["location"] or "Unsorted").strip() or "Unsorted") == location]
        self.storage_location_title.setText(location)
        self.storage_location_count.setText(f"{len(rows)} records · {sum(int(r['quantity']) for r in rows)} total units")
        self.storage_items.clear()
        for row in rows:
            item = QListWidgetItem(f"{row['name']}   ·   Qty {row['quantity']}   ·   {row['category']}")
            item.setData(Qt.UserRole, int(row["id"]))
            self.storage_items.addItem(item)
        self.storage_move_combo.clear()
        for row in db.list_items():
            self.storage_move_combo.addItem(f"{row['name']}  ·  {row['location']}", int(row["id"]))

    def move_item_to_location(self):
        if not self.selected_storage_location:
            QMessageBox.information(self, "Choose a location", "Select a storage card first.")
            return
        item_id = self.storage_move_combo.currentData()
        if item_id is None:
            QMessageBox.information(self, "No components", "Add a component before moving it.")
            return
        row = db.get_item(int(item_id))
        if not row:
            return
        data = {key: row[key] for key in ["name", "category", "manufacturer", "model", "quantity", "condition", "location", "tags", "notes", "photo_path", "status", "datasheet_url"]}
        data["location"] = self.selected_storage_location
        db.save_item(data, int(item_id))
        self.refresh()
        self.statusBar().showMessage(f"Moved {row['name']} to {self.selected_storage_location}", 4000)

    def open_storage_item(self, list_item):
        item_id = list_item.data(Qt.UserRole)
        row = db.get_item(int(item_id)) if item_id else None
        if not row:
            return
        dialog = ItemDialog(self, row)
        if dialog.exec() == QDialog.Accepted:
            db.save_item(dialog.payload(), int(item_id))
            db.set_item_projects(int(item_id), dialog.selected_projects())
            self.refresh()
            self.statusBar().showMessage("Component updated", 3500)

    def create_storage_location(self):
        locations = sorted({(r["location"] or "Unsorted").strip() for r in db.list_items()})
        location, ok = QInputDialog.getText(self, "New storage location", "Location name (you can then move components into it):")
        location = location.strip()
        if not ok or not location:
            return
        if location in locations:
            self.select_storage_location(location)
            return
        # Empty locations are not stored separately; assign an existing item to create the location.
        items = db.list_items()
        if not items:
            QMessageBox.information(self, "Add a component first", "Create a component, then assign it to this location.")
            return
        choices = [f"{r['name']}  ·  {r['location']}" for r in items]
        choice, ok = QInputDialog.getItem(self, "Create location", f"Choose a component to move to ‘{location}’:", choices, 0, False)
        if not ok or not choice:
            return
        selected = items[choices.index(choice)]
        data = {key: selected[key] for key in ["name", "category", "manufacturer", "model", "quantity", "condition", "location", "tags", "notes", "photo_path", "status", "datasheet_url"]}
        data["location"] = location
        db.save_item(data, int(selected["id"]))
        self.selected_storage_location = location
        self.refresh()
        self.statusBar().showMessage(f"Created storage area: {location}", 4000)

    def metric_card(self, title, value):
        card = QFrame()
        card.setObjectName("MetricCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 13, 16, 13)
        box.addWidget(label(title, "Muted"))
        val = label(value, "Metric")
        box.addWidget(val)
        card.metric_value = val
        return card

    def build_storage_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 25, 28, 22)
        layout.setSpacing(14)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label("Storage map", "PageTitle"))
        titles.addWidget(label("Choose a drawer or work area to inspect what is stored there.", "Muted"))
        header.addLayout(titles, 1)
        new_location = QPushButton("＋ New location")
        new_location.setObjectName("Primary")
        new_location.clicked.connect(self.create_storage_location)
        header.addWidget(new_location)
        layout.addLayout(header)

        self.storage_summary = label("Locations are grouped from each component's Physical location field.", "Muted")
        layout.addWidget(self.storage_summary)
        split = QSplitter(Qt.Horizontal)
        map_frame = QFrame()
        map_frame.setObjectName("Panel")
        map_layout = QVBoxLayout(map_frame)
        map_layout.setContentsMargins(14, 14, 14, 14)
        map_layout.addWidget(label("YOUR STORAGE AREAS", "Muted"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.storage_cards_host = QWidget()
        self.storage_grid = QGridLayout(self.storage_cards_host)
        self.storage_grid.setContentsMargins(2, 2, 2, 2)
        self.storage_grid.setSpacing(12)
        scroll.setWidget(self.storage_cards_host)
        map_layout.addWidget(scroll, 1)
        split.addWidget(map_frame)

        detail_frame = QFrame()
        detail_frame.setObjectName("DetailPanel")
        detail_layout = QVBoxLayout(detail_frame)
        detail_layout.setContentsMargins(16, 16, 16, 16)
        detail_layout.setSpacing(10)
        self.storage_location_title = label("Select a location", "PageTitle")
        self.storage_location_title.setWordWrap(True)
        detail_layout.addWidget(self.storage_location_title)
        self.storage_location_count = label("Choose a storage card to see its contents.", "Muted")
        detail_layout.addWidget(self.storage_location_count)
        detail_layout.addWidget(label("COMPONENTS HERE", "Muted"))
        self.storage_items = QListWidget()
        self.storage_items.itemDoubleClicked.connect(self.open_storage_item)
        detail_layout.addWidget(self.storage_items, 1)
        detail_layout.addWidget(label("MOVE A COMPONENT HERE", "Muted"))
        self.storage_move_combo = QComboBox()
        self.storage_move_combo.setMinimumWidth(230)
        detail_layout.addWidget(self.storage_move_combo)
        move_btn = QPushButton("Move selected component here")
        move_btn.setObjectName("Primary")
        move_btn.clicked.connect(self.move_item_to_location)
        detail_layout.addWidget(move_btn)
        hint = label("Tip: double-click a component to edit its full record. Moving it updates the existing inventory entry.", "Muted")
        hint.setWordWrap(True)
        detail_layout.addWidget(hint)
        split.addWidget(detail_frame)
        split.setSizes([690, 380])
        layout.addWidget(split, 1)
        self.selected_storage_location = ""
        return page

    def build_projects_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 25, 28, 22)
        layout.setSpacing(16)
        layout.addWidget(label("Projects", "PageTitle"))
        layout.addWidget(label("Connect hardware to the builds that use it.", "Muted"))
        row = QHBoxLayout()
        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("New project name")
        self.project_desc = QLineEdit()
        self.project_desc.setPlaceholderText("What are you building?")
        add = QPushButton("Create project")
        add.setObjectName("Primary")
        add.clicked.connect(self.create_project)
        row.addWidget(self.project_name, 1)
        row.addWidget(self.project_desc, 2)
        row.addWidget(add)
        layout.addLayout(row)
        self.project_list = QListWidget()
        layout.addWidget(self.project_list, 1)
        return page

    def build_tools_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 25, 28, 22)
        layout.setSpacing(16)
        layout.addWidget(label("Workshop tools", "PageTitle"))
        layout.addWidget(label("Testing history, duplicate checks, labels, bulk updates, and safe backups.", "Muted"))
        grid = QGridLayout()
        actions = [
            ("⌕  Global search  ·  Ctrl+K", self.global_search),
            ("◉  Find possible duplicates", self.find_duplicates),
            ("▤  Create QR storage labels", self.make_qr_labels),
            ("▣  Backup database + photos", self.backup_data),
            ("↶  Restore from backup", self.restore_data),
            ("✓  View hardware test history", self.test_history),
            ("⇄  Reserve parts for a project", self.reserve_parts),
            ("▦  Print inventory labels (CSV/PDF-ready HTML)", self.make_print_labels),
        ]
        for i, (caption, callback) in enumerate(actions):
            b = QPushButton(caption)
            b.setMinimumHeight(54)
            b.clicked.connect(callback)
            if i in (0, 3): b.setObjectName("Primary")
            grid.addWidget(b, i // 2, i % 2)
        layout.addLayout(grid)
        note = QFrame(); note.setObjectName("Panel")
        note_layout = QVBoxLayout(note)
        note_layout.addWidget(label("LOCAL-FIRST WORKFLOW", "Muted"))
        note_layout.addWidget(label("Backups include the SQLite database and locally stored photos. QR labels link to local item IDs; they do not expose your inventory to the internet. Component identification is manual-assisted: attach a photo, record chip markings, and save the manufacturer's datasheet URL.", "Muted"))
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def show_tools(self):
        for nav in (self.nav_inventory, self.nav_storage, self.nav_projects, self.nav_tools): nav.setChecked(nav is self.nav_tools)
        self.stack.setCurrentWidget(self.tools_page)

    def open_datasheet(self):
        item = db.get_item(self.selected_id) if self.selected_id else None
        if item and item["datasheet_url"]:
            url = item["datasheet_url"].strip()
            if not url.startswith(("https://", "http://")):
                QMessageBox.warning(self, "Invalid URL", "Use a full http:// or https:// URL.")
                return
            QDesktopServices.openUrl(QUrl(url))

    def record_test(self):
        if not self.selected_id: return
        item = db.get_item(self.selected_id)
        dialog = QDialog(self); dialog.setWindowTitle("Record hardware test")
        form = QFormLayout(dialog)
        form.addRow(label(f'Test record · {item["name"]}', "PageTitle"))
        result = QComboBox(); result.addItems(["Working", "Passed", "Failed", "Intermittent", "Needs repair", "Untested"])
        measurements = QLineEdit(); measurements.setPlaceholderText("Voltage, current, interface, observed values…")
        notes = QTextEdit(); notes.setPlaceholderText("Setup, steps performed, issues, logs…")
        form.addRow("Result", result); form.addRow("Measurements", measurements); form.addRow("Notes", notes)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); form.addRow(buttons)
        if dialog.exec() == QDialog.Accepted:
            with db.connect() as con:
                con.execute("INSERT INTO test_records(item_id,result,measurements,notes) VALUES (?,?,?,?)", (int(self.selected_id), result.currentText(), measurements.text().strip(), notes.toPlainText().strip()))
                status = "Tested" if result.currentText() in ("Working", "Passed") else ("Needs identification" if result.currentText() == "Untested" else "Needs repair")
                con.execute("UPDATE items SET status=?, condition=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, result.currentText(), int(self.selected_id)))
            self.refresh(); self.statusBar().showMessage("Hardware test saved", 3500)

    def test_history(self):
        with db.connect() as con:
            rows = con.execute("SELECT t.*, i.name FROM test_records t JOIN items i ON i.id=t.item_id ORDER BY tested_at DESC, t.id DESC LIMIT 500").fetchall()
        dialog = QDialog(self); dialog.setWindowTitle("Hardware test history"); dialog.resize(900, 560)
        layout = QVBoxLayout(dialog); table = QTableWidget(len(rows), 5)
        table.setHorizontalHeaderLabels(["Component", "Date", "Result", "Measurements", "Notes"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for r, row in enumerate(rows):
            for c, val in enumerate([row["name"], row["tested_at"], row["result"], row["measurements"], row["notes"]]): table.setItem(r,c,QTableWidgetItem(str(val)))
        layout.addWidget(table); close = QPushButton("Close"); close.clicked.connect(dialog.accept); layout.addWidget(close); dialog.exec()

    def global_search(self):
        query, ok = QInputDialog.getText(self, "Global search", "Search components, locations, tags, models, and notes:")
        if not ok or not query.strip(): return
        self.show_inventory(); self.search.setText(query.strip()); self.refresh_table()

    def find_duplicates(self):
        rows = db.list_items(); groups = {}
        for row in rows:
            key = (row["name"].strip().casefold(), row["model"].strip().casefold())
            if key[0]: groups.setdefault(key, []).append(row)
        dupes = [g for g in groups.values() if len(g) > 1]
        if not dupes:
            QMessageBox.information(self, "Duplicate check", "No possible duplicates found by matching component name + model.")
            return
        lines = []
        for group in dupes:
            lines.append("• " + group[0]["name"] + (f' [{group[0]["model"]}]' if group[0]["model"] else ""))
            lines.extend(f'    ID {r["id"]} · Qty {r["quantity"]} · {r["location"]}' for r in group)
        QMessageBox.information(self, "Possible duplicates", "These records have matching names and model fields. Review before deleting or merging; records were not changed.\n\n" + "\n".join(lines))

    def bulk_edit(self):
        ids = sorted({int(self.table.item(idx.row(), 0).data(Qt.UserRole)) for idx in self.table.selectionModel().selectedRows()})
        if not ids:
            QMessageBox.information(self, "Bulk edit", "Select multiple component rows first (Ctrl-click or Shift-click).")
            return
        dialog = QDialog(self); dialog.setWindowTitle(f"Bulk edit {len(ids)} components")
        form = QFormLayout(dialog)
        location = QLineEdit(); location.setPlaceholderText("Leave blank to keep existing locations")
        status = QComboBox(); status.addItems(["(keep existing)", "Needs identification", "Identified", "Tested", "In use", "Archived"])
        condition = QComboBox(); condition.addItems(["(keep existing)", *CONDITIONS])
        tags = QLineEdit(); tags.setPlaceholderText("Leave blank to keep existing tags; otherwise replace")
        form.addRow("New location", location); form.addRow("Set status", status); form.addRow("Set condition", condition); form.addRow("Replace tags", tags)
        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); form.addRow(buttons)
        if dialog.exec() != QDialog.Accepted: return
        with db.connect() as con:
            for iid in ids:
                old = con.execute("SELECT * FROM items WHERE id=?", (iid,)).fetchone()
                if not old: continue
                loc = location.text().strip() or old["location"]
                st = old["status"] if status.currentText() == "(keep existing)" else status.currentText()
                cond = old["condition"] if condition.currentText() == "(keep existing)" else condition.currentText()
                tg = tags.text().strip() or old["tags"]
                con.execute("UPDATE items SET location=?,status=?,condition=?,tags=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (loc,st,cond,tg,iid))
                con.execute("INSERT OR IGNORE INTO storage_locations(name) VALUES (?)", (loc,))
        self.refresh(); self.statusBar().showMessage(f"Bulk updated {len(ids)} components", 4000)

    def backup_data(self):
        default = str(Path.home() / f"benchvault-backup-{datetime.now():%Y%m%d-%H%M%S}.zip")
        path, _ = QFileDialog.getSaveFileName(self, "Save BenchVault backup", default, "ZIP backup (*.zip)")
        if not path: return
        if not path.lower().endswith(".zip"): path += ".zip"
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                if db.DB_PATH.exists(): zf.write(db.DB_PATH, "benchvault.db")
                if db.PHOTO_DIR.exists():
                    for f in db.PHOTO_DIR.rglob("*"):
                        if f.is_file(): zf.write(f, str(Path("photos") / f.relative_to(db.PHOTO_DIR)))
            QMessageBox.information(self, "Backup complete", f"Saved database and photos to:\n{path}")
        except Exception as exc: QMessageBox.critical(self, "Backup failed", str(exc))

    def restore_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Restore BenchVault backup", str(Path.home()), "ZIP backup (*.zip)")
        if not path: return
        if QMessageBox.warning(self, "Replace current data?", "First create a backup of the current database and photos. Restoring replaces the current database and photo folder.", QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Yes: return
        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                if "benchvault.db" not in names: raise ValueError("This ZIP does not contain benchvault.db")
                # Reject paths that could escape the backup destination.
                if any(Path(n).is_absolute() or ".." in Path(n).parts for n in names): raise ValueError("Unsafe path found in backup")
                # Automatically snapshot current state before replacing it.
                safety_dir = db.APP_DIR / "pre-restore-backups"
                safety_dir.mkdir(parents=True, exist_ok=True)
                safety_path = safety_dir / f"benchvault-before-restore-{datetime.now():%Y%m%d-%H%M%S}.zip"
                with zipfile.ZipFile(safety_path, "w", zipfile.ZIP_DEFLATED) as safety:
                    if db.DB_PATH.exists(): safety.write(db.DB_PATH, "benchvault.db")
                    if db.PHOTO_DIR.exists():
                        for f in db.PHOTO_DIR.rglob("*"):
                            if f.is_file(): safety.write(f, str(Path("photos") / f.relative_to(db.PHOTO_DIR)))
                with tempfile.TemporaryDirectory() as tmp:
                    zf.extractall(tmp)
                    shutil.copy2(Path(tmp) / "benchvault.db", db.DB_PATH)
                    restored_photos = Path(tmp) / "photos"
                    if restored_photos.exists():
                        if db.PHOTO_DIR.exists(): shutil.rmtree(db.PHOTO_DIR)
                        shutil.copytree(restored_photos, db.PHOTO_DIR)
            db.init_db(); self.refresh(); QMessageBox.information(self, "Restore complete", "Backup restored successfully.")
        except Exception as exc: QMessageBox.critical(self, "Restore failed", str(exc))

    def make_qr_labels(self):
        rows = db.list_items()
        if not rows:
            QMessageBox.information(self, "QR labels", "Add components first."); return
        try:
            import qrcode
        except ImportError:
            QMessageBox.information(self, "QR label dependency", "Installing QR support once in your BenchVault environment:\n\npython -m pip install 'qrcode[pil]'\n\nThen reopen BenchVault and try again.")
            return
        out = QFileDialog.getExistingDirectory(self, "Choose folder for QR labels", str(Path.home()))
        if not out: return
        outp = Path(out); cards = []
        for row in rows:
            payload = f"BenchVault item ID: {row['id']}\\nName: {row['name']}\\nLocation: {row['location']}"
            img = qrcode.make(payload); filename = f"benchvault-item-{row['id']}.png"; img.save(outp / filename)
            cards.append(f'<article><img src="{html.escape(filename)}"><h3>{html.escape(row["name"])}</h3><p>{html.escape(row["location"])}</p><small>ID {row["id"]}</small></article>')
        doc = '<!doctype html><meta charset="utf-8"><title>BenchVault QR labels</title><style>body{font:14px sans-serif;background:#000;color:#f4edf0}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}article{border:1px solid #66516b;border-radius:8px;padding:12px;text-align:center;break-inside:avoid}img{width:150px;height:150px;background:white}h3{font-size:16px} @media print{body{background:white;color:black}.grid{grid-template-columns:repeat(3,1fr)}} </style><h1>BenchVault · Storage labels</h1><div class="grid">' + ''.join(cards) + '</div>'
        (outp / "benchvault-qr-labels.html").write_text(doc, encoding="utf-8")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(outp / "benchvault-qr-labels.html")))
        QMessageBox.information(self, "QR labels created", f"Created {len(rows)} QR PNGs and a printable HTML sheet in:\n{outp}\n\nQRs encode local record details, not a network URL.")

    def make_print_labels(self):
        rows = db.list_items()
        path, _ = QFileDialog.getSaveFileName(self, "Save printable inventory labels", str(Path.home()/"benchvault-labels.html"), "HTML file (*.html)")
        if not path: return
        cards = ''.join(f'<article><b>{html.escape(r["name"])}</b><p>{html.escape(r["location"])}</p><small>{html.escape(r["category"])} · ID {r["id"]} · Qty {r["quantity"]}</small></article>' for r in rows)
        doc = '<!doctype html><meta charset="utf-8"><title>BenchVault labels</title><style>body{font:12px sans-serif}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}article{border:1px solid #777;padding:12px;min-height:65px;break-inside:avoid}p{margin:5px 0}@media print{button{display:none}}</style><button onclick="print()">Print labels</button><div class="grid">'+cards+'</div>'
        Path(path).write_text(doc, encoding="utf-8"); QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))

    def reserve_parts(self):
        items = db.list_items(); projs = db.projects()
        if not items or not projs:
            QMessageBox.information(self, "Reserve parts", "Create a component and a project first."); return
        dialog = QDialog(self); dialog.setWindowTitle("Reserve components for a project")
        form = QFormLayout(dialog)
        item_combo = QComboBox(); item_combo.addItems([f'{r["name"]} · available qty {r["quantity"]} · {r["location"]}' for r in items])
        project_combo = QComboBox(); project_combo.addItems([r["name"] for r in projs])
        qty = QSpinBox(); qty.setRange(1, 999999); qty.setValue(1)
        notes = QLineEdit(); notes.setPlaceholderText("Optional purpose / build step")
        form.addRow("Component", item_combo); form.addRow("Project", project_combo); form.addRow("Quantity to reserve", qty); form.addRow("Notes", notes)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); form.addRow(buttons)
        if dialog.exec() != QDialog.Accepted: return
        item = items[item_combo.currentIndex()]; project = projs[project_combo.currentIndex()]
        with db.connect() as con:
            current = con.execute("SELECT quantity FROM project_reservations WHERE item_id=? AND project_id=?", (item["id"],project["id"])).fetchone()
            newqty = qty.value() + (int(current[0]) if current else 0)
            if newqty > int(item["quantity"]):
                QMessageBox.warning(self, "Not enough stock", f"Only {item['quantity']} units are recorded. Existing reservations for this project: {int(current[0]) if current else 0}.")
                return
            con.execute("INSERT INTO project_reservations(item_id,project_id,quantity,notes) VALUES (?,?,?,?) ON CONFLICT(item_id,project_id) DO UPDATE SET quantity=excluded.quantity,notes=excluded.notes", (item["id"],project["id"],newqty,notes.text().strip()))
            con.execute("INSERT OR IGNORE INTO item_projects(item_id,project_id) VALUES (?,?)", (item["id"],project["id"]))
        self.refresh_projects(); QMessageBox.information(self, "Reserved", f"Reserved {qty.value()} unit(s) of {item['name']} for {project['name']}.")

    def show_projects(self):
        self.nav_projects.setChecked(True)
        self.nav_inventory.setChecked(False)
        self.nav_storage.setChecked(False)
        self.nav_tools.setChecked(False)
        self.stack.setCurrentWidget(self.projects_page)
        self.refresh_projects()

    def show_inventory(self):
        self.nav_inventory.setChecked(True)
        self.nav_projects.setChecked(False)
        self.nav_storage.setChecked(False)
        self.stack.setCurrentWidget(self.inventory_page)
        self.refresh()

    def show_storage(self):
        self.nav_storage.setChecked(True)
        self.nav_inventory.setChecked(False)
        self.nav_projects.setChecked(False)
        self.nav_tools.setChecked(False)
        self.stack.setCurrentWidget(self.storage_page)
        self.refresh_storage_map()

    def refresh(self):
        self.refresh_metrics()
        self.refresh_category_filter()
        self.refresh_table()
        self.refresh_projects()
        if hasattr(self, "storage_page"):
            self.refresh_storage_map()

    def refresh_metrics(self):
        rows = db.list_items()
        self.metric_items.metric_value.setText(str(len(rows)))
        self.metric_quantity.metric_value.setText(str(sum(int(r["quantity"]) for r in rows)))
        self.metric_unknown.metric_value.setText(str(sum(r["status"] == "Needs identification" for r in rows)))
        self.metric_categories.metric_value.setText(str(len({r["category"] for r in rows})))

    def refresh_category_filter(self):
        current = self.category_filter.currentText() if hasattr(self, "category_filter") else "All categories"
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("All categories")
        self.category_filter.addItems(db.categories())
        self.category_filter.setCurrentText(current if current in ["All categories", *db.categories()] else "All categories")
        self.category_filter.blockSignals(False)

    def refresh_table(self):
        if not hasattr(self, "table"):
            return
        rows = db.list_items(self.search.text(), self.category_filter.currentText())
        self.table.setRowCount(len(rows))
        for row_index, r in enumerate(rows):
            values = [r["name"], r["category"], r["model"] or "—", str(r["quantity"]), r["condition"], r["location"], r["status"]]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.UserRole, r["id"])
                if col == 0:
                    cell.setForeground(Qt.white)
                if col == 6 and r["status"] == "Needs identification":
                    cell.setForeground(Qt.darkYellow)
                self.table.setItem(row_index, col, cell)
        if self.table.rowCount():
            self.table.selectRow(0)
        else:
            self.selected_id = None
            self.update_detail(None)

    def selected_item_id(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        return int(self.table.item(selected[0].row(), 0).data(Qt.UserRole))

    def selection_changed(self):
        self.selected_id = self.selected_item_id()
        self.update_detail(db.get_item(self.selected_id) if self.selected_id else None)

    def update_detail(self, item):
        if not item:
            self.detail_name.setText("Select a component")
            self.detail_meta.setText("Choose a row to inspect its record.")
            self.detail_notes.setText("")
            self.detail_projects.setText("")
            self.datasheet_link.setEnabled(False)
            self.test_btn.setEnabled(False)
            self.photo_preview.setPixmap(QPixmap())
            self.photo_preview.setText("NO PHOTO")
            return
        self.detail_name.setText(item["name"])
        self.datasheet_link.setEnabled(bool(item["datasheet_url"]))
        self.test_btn.setEnabled(True)
        self.datasheet_link.setToolTip(item["datasheet_url"] or "Add a URL in Edit component")
        self.detail_meta.setText(
            f'{item["category"]}  ·  Qty {item["quantity"]}\n'
            f'{item["manufacturer"] or "Manufacturer unknown"} · {item["model"] or "Model unknown"}\n'
            f'Condition: {item["condition"]}\nLocation: {item["location"]}\nStatus: {item["status"]}\nTags: {item["tags"] or "—"}'
        )
        self.detail_notes.setText(item["notes"] or "No notes yet.")
        projects = db.item_project_names(item["id"])
        self.detail_projects.setText("PROJECTS\n" + ("\n".join("• " + p for p in projects) if projects else "No project links"))
        path = item["photo_path"]
        if path and Path(path).exists():
            pix = QPixmap(path)
            self.photo_preview.setText("")
            self.photo_preview.setPixmap(pix.scaled(QSize(330, 190), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.photo_preview.setPixmap(QPixmap())
            self.photo_preview.setText("NO PHOTO ATTACHED")

    def add_item(self):
        dialog = ItemDialog(self)
        if dialog.exec() == QDialog.Accepted:
            item_id = db.save_item(dialog.payload())
            db.set_item_projects(item_id, dialog.selected_projects())
            self.refresh()
            self.statusBar().showMessage("Component added", 3500)

    def edit_item(self):
        item_id = self.selected_id
        if not item_id:
            return
        item = db.get_item(item_id)
        dialog = ItemDialog(self, item)
        if dialog.exec() == QDialog.Accepted:
            db.save_item(dialog.payload(), item_id)
            db.set_item_projects(item_id, dialog.selected_projects())
            self.refresh()
            self.statusBar().showMessage("Component updated", 3500)

    def duplicate_item(self):
        item_id = self.selected_id
        if not item_id:
            return
        item = db.get_item(item_id)
        dialog = ItemDialog(self, item)
        dialog.setWindowTitle("Duplicate component")
        dialog.name.setText(item["name"] + " copy")
        if dialog.exec() == QDialog.Accepted:
            new_id = db.save_item(dialog.payload())
            db.set_item_projects(new_id, dialog.selected_projects())
            self.refresh()
            self.statusBar().showMessage("Component duplicated", 3500)

    def delete_item(self):
        item_id = self.selected_id
        if not item_id:
            return
        item = db.get_item(item_id)
        answer = QMessageBox.question(self, "Delete component", f'Delete "{item["name"]}"? This cannot be undone.')
        if answer == QMessageBox.Yes:
            db.delete_item(item_id)
            self.selected_id = None
            self.refresh()
            self.statusBar().showMessage("Component deleted", 3500)

    def import_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import inventory CSV", str(Path.home()), "CSV files (*.csv)")
        if not path:
            return
        try:
            created, skipped = db.import_csv(path)
            self.refresh()
            QMessageBox.information(self, "Import complete", f"Created {created} records.\nSkipped {skipped} rows without a name.")
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))

    def export_data(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export inventory CSV", str(Path.home() / "benchvault-export.csv"), "CSV files (*.csv)")
        if not path:
            return
        try:
            count = db.export_csv(path)
            QMessageBox.information(self, "Export complete", f"Exported {count} records.")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))

    def create_project(self):
        name = self.project_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Project name required", "Enter a name for the project.")
            return
        with db.connect() as con:
            con.execute("INSERT OR IGNORE INTO projects(name, description) VALUES (?, ?)", (name, self.project_desc.text().strip()))
        self.project_name.clear()
        self.project_desc.clear()
        self.refresh_projects()

    def refresh_projects(self):
        if not hasattr(self, "project_list"):
            return
        self.project_list.clear()
        for p in db.projects():
            with db.connect() as con:
                count = con.execute("SELECT COUNT(*) FROM item_projects WHERE project_id=?", (p["id"],)).fetchone()[0]
            with db.connect() as con:
                reserved = con.execute("SELECT COALESCE(SUM(quantity),0) FROM project_reservations WHERE project_id=?", (p["id"],)).fetchone()[0]
            item = QListWidgetItem(f'{p["name"]}    ·    {count} linked components    ·    {reserved} reserved units\n{p["description"]}')
            item.setData(Qt.UserRole, p["id"])
            self.project_list.addItem(item)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("BenchVault")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_QSS)
    db.init_db()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
