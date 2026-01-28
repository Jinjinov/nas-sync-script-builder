from pathlib import Path
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

from .config import NasSyncConfig, save_config, load_config
from .template import render_script
from .partitions import detect_partitions, get_sync_dirs

CONFIG_FILE = Path("nas_sync_config.yaml")

class NasSyncScriptBuilder(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("NAS Configuration")
        self.resize(500, 1000)

        main_layout = QVBoxLayout(self)

        # --- Form ---
        form_layout = QFormLayout()
        self.nas_base_path_edit = QLineEdit()
        self.nas_username_edit = QLineEdit()
        self.nas_mount_path_edit = QLineEdit()
        self.local_mount_path_edit = QLineEdit()
        self.exclude_edit = QPlainTextEdit()
        self.exclude_edit.setPlaceholderText("One exclude pattern per line")

        form_layout.addRow("NAS Host:", self.nas_base_path_edit)
        form_layout.addRow("NAS Username:", self.nas_username_edit)
        form_layout.addRow("NAS Mount Root:", self.nas_mount_path_edit)
        form_layout.addRow("Local Mount Root:", self.local_mount_path_edit)
        form_layout.addRow("Exclude patterns:", self.exclude_edit)

        main_layout.addLayout(form_layout)

        # --- Tables ---
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

        # --- Buttons ---
        buttons_layout = QVBoxLayout()
        detect_button = QPushButton("Detect Partitions")
        detect_button.clicked.connect(self.on_detect_partitions)
        buttons_layout.addWidget(detect_button)

        save_button = QPushButton("Generate")
        save_button.clicked.connect(self.on_save)
        buttons_layout.addWidget(save_button)

        main_layout.addLayout(buttons_layout)

        # --- Load config ---
        self.cfg = load_config(CONFIG_FILE)
        self.load_into_widgets(self.cfg)

    # ---- GUI <-> DTO mapping ----
    def load_into_widgets(self, cfg: NasSyncConfig):
        self.nas_base_path_edit.setText(cfg.nas_base_path)
        self.nas_username_edit.setText(cfg.nas_username)
        self.nas_mount_path_edit.setText(cfg.nas_mount_path)
        self.local_mount_path_edit.setText(cfg.local_mount_path)
        self.exclude_edit.setPlainText("\n".join(cfg.exclude_items))

        self.populate_partitions_table(cfg.partitions)
        self.populate_sync_dirs_table(cfg.sync_dirs)

    def update_config_from_widgets(self, cfg: NasSyncConfig):
        cfg.nas_base_path = self.nas_base_path_edit.text()
        cfg.nas_username = self.nas_username_edit.text()
        cfg.nas_mount_path = self.nas_mount_path_edit.text()
        cfg.local_mount_path = self.local_mount_path_edit.text()
        cfg.exclude_items = [
            line.strip() for line in self.exclude_edit.toPlainText().splitlines() if line.strip()
        ]
        cfg.partitions = self.get_partitions_from_table()
        cfg.sync_dirs = self.get_sync_dirs_from_table()

    # ---- Table helpers ----
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

    # ---- Detect partitions ----
    def on_detect_partitions(self):
        partitions = detect_partitions()
        sync_dirs = get_sync_dirs(partitions)
        self.populate_partitions_table(partitions)
        self.populate_sync_dirs_table(sync_dirs)

    # ---- Save / Generate ----
    def on_save(self):
        self.update_config_from_widgets(self.cfg)
        save_config(self.cfg, CONFIG_FILE)

        rendered = render_script(self.cfg)
        output_path = Path("nas-sync.sh")
        output_path.write_text(rendered + "\n")
        output_path.chmod(0o755)


def main():
    app = QApplication(sys.argv)
    window = NasSyncScriptBuilder()
    window.show()
    sys.exit(app.exec())
