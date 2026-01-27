#!/usr/bin/env python3

import sys
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from pathlib import Path
from jinja2 import Environment, FileSystemLoader

import yaml

from pydbus import SystemBus

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_FILE = BASE_DIR / "nas_sync_config.yaml"

TEMPLATES_DIR = BASE_DIR / "templates"

env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    trim_blocks=False,
    lstrip_blocks=False,
)
template = env.get_template("nas-sync.sh.tpl")

DEFAULT_PARTITIONS = {
    "860_Personal": "ntfs3",
    "D_Programs": "ntfs3",
    "E_Setups": "ntfs3",
    "F_Personal": "ntfs3",
    "G_Media": "ntfs3",
    "H_Downloads": "ntfs3",
    "I_Installs": "ntfs3",
    "J_Video": "ntfs3",
}

DEFAULT_EXCLUDE_ITEMS = [
    "$RECYCLE.BIN/",
    "System Volume Information/",
    "RECYCLER/",
    "Program Files/",
    "Program Files (x86)/",
    "Windows/",
    "PerfLogs/",
    "MSOCache/",
    "found.000/",

    "hiberfil.sys",
    "pagefile.sys",
    "swapfile.sys",
    "desktop.ini",
    "Desktop.ini",
    "Thumbs.db",
    "ehthumbs.db",
    "DumpStack.log*",
    "WPSettings.dat",
    "IndexerVolumeGuid",

    ".Trash-1000/",

    ".git/",
    ".vs/",
    ".vscode/",
]

# ----------------------------
# D-Bus partition detection
# List partitions where:
#   HintIgnore != true
#   IdLabel is not empty
#   IdType is not empty
#   IdUsage == "filesystem"
# ----------------------------
def detect_partitions():
    bus = SystemBus()
    udisks = bus.get("org.freedesktop.UDisks2")
    objects = udisks.GetManagedObjects()

    partitions = {}

    def b2s(b):
        return bytes(b).decode(errors="ignore").strip("\x00")
    
    for path, interfaces in objects.items():
        block = interfaces.get("org.freedesktop.UDisks2.Block")

        if not block:
            continue

        if block.get("HintIgnore", False):
            continue

        if block.get("IdUsage") != "filesystem":
            continue

        fstype = block.get("IdType")
        if not fstype:
            continue

        fs = interfaces.get("org.freedesktop.UDisks2.Filesystem")

        mounted = bool(fs and fs.get("MountPoints"))
        if mounted:
            mountpoints = [b2s(mp) for mp in fs["MountPoints"]]
            if any(mp in ("/", "/boot", "/usr", "/var") for mp in mountpoints):
                continue

        label = block.get("IdLabel")
        if not label:
            continue

        uuid = block.get("IdUUID")
        device = b2s(block["Device"])

        partitions[label] = fstype

        #partitions[label] = {
        #    "label": label,
        #    "fstype": fstype,
        #    "uuid": uuid,
        #    "device": device,
        #}

    return partitions

# Add:
# Local filesystem type per disk (ntfs3, ext4, xfs, …)
# Local disk identifiers (labels / UUIDs)
# Local → NAS directory mapping

class NasSyncScriptBuilder(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("NAS Configuration")
        self.resize(600, 900)

        # Top-level vertical layout (like a StackPanel)
        main_layout = QVBoxLayout(self)

        # Form layout (label + field pairs)
        form_layout = QFormLayout()

        self.nas_base_path_edit = QLineEdit("//synologynas.local/Intel-i5-2500/")
        self.nas_username_edit = QLineEdit("Jinjinov")
        self.nas_mount_path_edit = QLineEdit("/mnt/nas/")
        self.local_mount_path_edit = QLineEdit("/mnt/data/")

        self.exclude_edit = QPlainTextEdit()
        self.exclude_edit.setPlaceholderText("One exclude pattern per line")
        self.exclude_edit.setPlainText("\n".join(DEFAULT_EXCLUDE_ITEMS))

        form_layout.addRow("NAS Host:", self.nas_base_path_edit)
        form_layout.addRow("NAS Username:", self.nas_username_edit)
        form_layout.addRow("NAS Mount Root:", self.nas_mount_path_edit)
        form_layout.addRow("Local Mount Root:", self.local_mount_path_edit)

        form_layout.addRow("Exclude patterns:", self.exclude_edit)

        main_layout.addLayout(form_layout)

        # Partition table
        self.partitions_table = QTableWidget()
        self.partitions_table.setColumnCount(2)
        self.partitions_table.setHorizontalHeaderLabels(["Label", "FSTYPE"])
        self.partitions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.partitions_table)

        # Save button at the bottom
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.on_save)
        main_layout.addWidget(save_button)

        self.load_config()

    def load_config(self):
        if CONFIG_FILE.exists():
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            self.nas_base_path_edit.setText(config.get("nas_base_path", "//synologynas.local/Intel-i5-2500/"))
            self.nas_username_edit.setText(config.get("nas_username", "Jinjinov"))
            self.nas_mount_path_edit.setText(config.get("nas_mount_path", "/mnt/nas/"))
            self.local_mount_path_edit.setText(config.get("local_mount_path", "/mnt/data/"))
            self.exclude_edit.setPlainText("\n".join(config.get("exclude_items", DEFAULT_EXCLUDE_ITEMS)))
            partitions = config.get("partitions", detect_partitions())
        else:
            partitions = detect_partitions()
        self.populate_partitions_table(partitions)

    def populate_partitions_table(self, partitions: dict):
        self.partitions_table.setRowCount(0)
        for i, (label, fstype) in enumerate(partitions.items()):
            self.partitions_table.insertRow(i)
            self.partitions_table.setItem(i, 0, QTableWidgetItem(label))
            self.partitions_table.setItem(i, 1, QTableWidgetItem(fstype))

    def get_partitions_from_table(self):
        partitions = {}
        for row in range(self.partitions_table.rowCount()):
            label_item = self.partitions_table.item(row, 0)
            fstype_item = self.partitions_table.item(row, 1)
            if label_item and fstype_item:
                partitions[label_item.text().strip()] = fstype_item.text().strip()
        return partitions

    def save_config(self):
        partitions = self.get_partitions_from_table()
        config = {
            "nas_base_path": self.nas_base_path_edit.text(),
            "nas_username": self.nas_username_edit.text(),
            "nas_mount_path": self.nas_mount_path_edit.text(),
            "local_mount_path": self.local_mount_path_edit.text(),
            "exclude_items": [
                line.strip()
                for line in self.exclude_edit.toPlainText().splitlines()
                if line.strip()
            ],
            "partitions": partitions,
        }

        with CONFIG_FILE.open("w", encoding="utf-8") as f:
            yaml.safe_dump(config, f)

    def on_save(self):

        self.save_config()

        exclude_items = [
            line.strip()
            for line in self.exclude_edit.toPlainText().splitlines()
            if line.strip()
        ]

        partitions = self.get_partitions_from_table()

        rendered = template.render(
            nas_base_path=self.nas_base_path_edit.text().rstrip("/") + "/",
            nas_username=self.nas_username_edit.text(),
            nas_mount_path=self.nas_mount_path_edit.text().rstrip("/") + "/",
            local_mount_path=self.local_mount_path_edit.text().rstrip("/") + "/",
            exclude_items=exclude_items,
            partitions=partitions,
        )

        output_path = BASE_DIR / "nas-sync.sh"
        output_path.write_text(rendered)
        output_path.chmod(0o755)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NasSyncScriptBuilder()
    window.show()
    sys.exit(app.exec())
