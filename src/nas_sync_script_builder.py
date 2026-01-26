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
)

from pathlib import Path
from jinja2 import Environment, FileSystemLoader

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_FILE = BASE_DIR / "nas_sync_config.yaml"

TEMPLATES_DIR = BASE_DIR / "templates"

env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
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

# Add:
# Local filesystem type per disk (ntfs3, ext4, xfs, …)
# Local disk identifiers (labels / UUIDs)
# Local → NAS directory mapping

class NasSyncScriptBuilder(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("NAS Configuration")
        self.resize(640, 480)

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

    def save_config(self):
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

        rendered = template.render(
            nas_base_path=self.nas_base_path_edit.text().rstrip("/") + "/",
            nas_username=self.nas_username_edit.text(),
            nas_mount_path=self.nas_mount_path_edit.text().rstrip("/") + "/",
            local_mount_path=self.local_mount_path_edit.text().rstrip("/") + "/",
            exclude_items=exclude_items,
        )

        output_path = BASE_DIR / "nas-sync.sh"
        output_path.write_text(rendered)
        output_path.chmod(0o755)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NasSyncScriptBuilder()
    window.show()
    sys.exit(app.exec())
