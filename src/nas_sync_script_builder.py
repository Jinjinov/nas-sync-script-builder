#!/usr/bin/env python3

import sys
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
)

from pathlib import Path
from jinja2 import Environment, FileSystemLoader

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    trim_blocks=False,
    lstrip_blocks=False,
)
template = env.get_template("nas-sync.sh.tpl")

# Add:
# Local filesystem type per disk (ntfs3, ext4, xfs, …)
# Local disk identifiers (labels / UUIDs)
# Local → NAS directory mapping
# Exclude lists

class NasSyncScriptBuilder(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("NAS Configuration")
        self.resize(400, 200)

        # Top-level vertical layout (like a StackPanel)
        main_layout = QVBoxLayout(self)

        # Form layout (label + field pairs)
        form_layout = QFormLayout()

        self.nas_base_path_edit = QLineEdit("//synologynas.local/Intel-i5-2500/")
        self.nas_username_edit = QLineEdit("Jinjinov")
        self.nas_mount_path_edit = QLineEdit("/mnt/nas")
        self.local_mount_path_edit = QLineEdit("/mnt/data")

        form_layout.addRow("NAS Host:", self.nas_base_path_edit)
        form_layout.addRow("NAS Username:", self.nas_username_edit)
        form_layout.addRow("NAS Mount Root:", self.nas_mount_path_edit)
        form_layout.addRow("Local Mount Root:", self.local_mount_path_edit)

        main_layout.addLayout(form_layout)

        # Save button at the bottom
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.on_save)
        main_layout.addWidget(save_button)

    def on_save(self):
        rendered = template.render(
            nas_base_path=self.nas_base_path_edit.text().rstrip("/") + "/",
            nas_username=self.nas_username_edit.text(),
            nas_mount_path=self.nas_mount_path_edit.text().rstrip("/") + "/",
            local_mount_path=self.local_mount_path_edit.text().rstrip("/") + "/",
        )

        output_path = BASE_DIR / "nas-sync.sh"
        output_path.write_text(rendered)
        output_path.chmod(0o755)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NasSyncScriptBuilder()
    window.show()
    sys.exit(app.exec())
