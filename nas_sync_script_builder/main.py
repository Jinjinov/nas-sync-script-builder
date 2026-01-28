#!/usr/bin/env python3

import sys
from pathlib import Path

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

from jinja2 import Environment, FileSystemLoader

import yaml

from pydbus import SystemBus

CONFIG_FILE = Path("nas_sync_config.yaml")

env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    trim_blocks=False,
    lstrip_blocks=False,
)
template = env.get_template("nas-sync.sh.tpl")

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

        partitions[label] = fstype

        #uuid = block.get("IdUUID")
        #device = b2s(block["Device"])

        #partitions[label] = {
        #    "label": label,
        #    "fstype": fstype,
        #    "uuid": uuid,
        #    "device": device,
        #}

    return partitions

def get_sync_dirs(partitions: dict):
    sync_dirs = {label: label for label in partitions}
    return sync_dirs

class NasSyncScriptBuilder(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("NAS Configuration")
        self.resize(500, 1000)

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

        self.sync_dirs_table = QTableWidget()
        self.sync_dirs_table.setColumnCount(2)
        self.sync_dirs_table.setHorizontalHeaderLabels(["Local Disk Label", "NAS Path"])
        self.sync_dirs_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.sync_dirs_table)

        # Save button at the bottom
        save_button = QPushButton("Generate")
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
            sync_dirs = config.get("sync_dirs", get_sync_dirs(partitions))
        else:
            partitions = detect_partitions()
            sync_dirs = get_sync_dirs(partitions)

        self.populate_partitions_table(partitions)
        self.populate_sync_dirs_table(sync_dirs)

    def populate_partitions_table(self, partitions: dict):
        self.partitions_table.setRowCount(0)
        for i, (label, fstype) in enumerate(partitions.items()):
            self.partitions_table.insertRow(i)
            self.partitions_table.setItem(i, 0, QTableWidgetItem(label))
            self.partitions_table.setItem(i, 1, QTableWidgetItem(fstype))

    def populate_sync_dirs_table(self, sync_dirs: dict):
        self.sync_dirs_table.setRowCount(0)
        for i, (local, nas_path) in enumerate(sync_dirs.items()):
            self.sync_dirs_table.insertRow(i)
            self.sync_dirs_table.setItem(i, 0, QTableWidgetItem(local))
            self.sync_dirs_table.setItem(i, 1, QTableWidgetItem(nas_path))

    def get_partitions_from_table(self):
        partitions = {}
        for row in range(self.partitions_table.rowCount()):
            label_item = self.partitions_table.item(row, 0)
            fstype_item = self.partitions_table.item(row, 1)
            if label_item and fstype_item:
                partitions[label_item.text().strip()] = fstype_item.text().strip()
        return partitions
    
    def get_sync_dirs_from_table(self):
        sync_dirs = {}
        for row in range(self.sync_dirs_table.rowCount()):
            local_item = self.sync_dirs_table.item(row, 0)
            nas_item = self.sync_dirs_table.item(row, 1)
            if local_item and nas_item:
                sync_dirs[local_item.text().strip()] = nas_item.text().strip()
        return sync_dirs

    def save_config(self):
        partitions = self.get_partitions_from_table()
        sync_dirs = self.get_sync_dirs_from_table()
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
            "sync_dirs": sync_dirs,
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
        sync_dirs = self.get_sync_dirs_from_table()

        rendered = template.render(
            nas_base_path=self.nas_base_path_edit.text().rstrip("/") + "/",
            nas_username=self.nas_username_edit.text(),
            nas_mount_path=self.nas_mount_path_edit.text().rstrip("/") + "/",
            local_mount_path=self.local_mount_path_edit.text().rstrip("/") + "/",
            exclude_items=exclude_items,
            partitions=partitions,
            sync_dirs=sync_dirs,
        )

        output_path = Path("nas-sync.sh")
        output_path.write_text(rendered)
        output_path.chmod(0o755)


def main():
    app = QApplication(sys.argv)
    window = NasSyncScriptBuilder()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
