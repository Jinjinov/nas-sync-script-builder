from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QHBoxLayout,
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
from .partitions import detect_partition_fstypes, get_partition_nas_paths

CONFIG_FILE = Path("nas_sync_config.yaml")

class NasSyncScriptBuilder(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("NAS sync script builder")
        self.resize(800, 600)

        main_layout = QHBoxLayout(self)

        form_column = QVBoxLayout()

        # --- Form ---
        form_layout = QFormLayout()
        self.nas_base_path_edit = QLineEdit()
        self.nas_username_edit = QLineEdit()
        self.nas_mount_path_edit = QLineEdit()
        self.local_mount_path_edit = QLineEdit()
        self.exclude_edit = QPlainTextEdit()
        self.exclude_edit.setPlaceholderText("One exclude pattern per line")

        form_layout.addRow("NAS base path:", self.nas_base_path_edit)
        form_layout.addRow("NAS username:", self.nas_username_edit)
        form_layout.addRow("NAS mount root:", self.nas_mount_path_edit)
        form_layout.addRow("Local mount root:", self.local_mount_path_edit)
        form_layout.addRow("Exclude patterns:", self.exclude_edit)

        form_column.addLayout(form_layout)

        save_button = QPushButton("Generate bash script")
        save_button.clicked.connect(self.on_save)
        form_column.addWidget(save_button)

        table_column = QVBoxLayout()

        detect_button = QPushButton("Detect local partitions")
        detect_button.clicked.connect(self.on_detect_partitions)
        table_column.addWidget(detect_button)

        # --- Tables ---
        self.partition_fstypes_table = QTableWidget()
        self.partition_fstypes_table.setColumnCount(3)
        self.partition_fstypes_table.setHorizontalHeaderLabels(["Local partition label", "File system type", ""])
        self.partition_fstypes_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.partition_fstypes_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.partition_fstypes_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.partition_fstypes_table.verticalHeader().setVisible(False)
        table_column.addWidget(self.partition_fstypes_table)

        self.partition_nas_paths_table = QTableWidget()
        self.partition_nas_paths_table.setColumnCount(3)
        self.partition_nas_paths_table.setHorizontalHeaderLabels(["Local partition label", "NAS path", ""])
        self.partition_nas_paths_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.partition_nas_paths_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.partition_nas_paths_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.partition_nas_paths_table.verticalHeader().setVisible(False)
        table_column.addWidget(self.partition_nas_paths_table)

        main_layout.addLayout(table_column)
        main_layout.addLayout(form_column)

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

        self.populate_partition_fstypes_table(cfg.partition_fstypes)
        self.populate_partition_nas_paths_table(cfg.partition_nas_paths)

    def update_config_from_widgets(self, cfg: NasSyncConfig):
        cfg.nas_base_path = self.nas_base_path_edit.text()
        cfg.nas_username = self.nas_username_edit.text()
        cfg.nas_mount_path = self.nas_mount_path_edit.text()
        cfg.local_mount_path = self.local_mount_path_edit.text()
        cfg.exclude_items = [
            line.strip() for line in self.exclude_edit.toPlainText().splitlines() if line.strip()
        ]
        cfg.partition_fstypes = self.get_partition_fstypes_from_table()
        cfg.partition_nas_paths = self.get_partition_nas_paths_from_table()

    # ---- Table helpers ----
    def populate_partition_fstypes_table(self, partition_fstypes: dict):
        self.partition_fstypes_table.setRowCount(0)
        for i, (label, fstype) in enumerate(partition_fstypes.items()):
            self.partition_fstypes_table.insertRow(i)
            label_item = QTableWidgetItem(label)
            label_item.setFlags(label_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.partition_fstypes_table.setItem(i, 0, label_item)
            self.partition_fstypes_table.setItem(i, 1, QTableWidgetItem(fstype))

            # Add delete button
            delete_button = QPushButton("X")
            delete_button.setFixedWidth(36)
            delete_button.clicked.connect(lambda chk=False, t=self.partition_fstypes_table, b=delete_button: self.delete_row(t, b))
            self.partition_fstypes_table.setCellWidget(i, 2, delete_button)

    def populate_partition_nas_paths_table(self, partition_nas_paths: dict):
        self.partition_nas_paths_table.setRowCount(0)
        for i, (label, nas_path) in enumerate(partition_nas_paths.items()):
            self.partition_nas_paths_table.insertRow(i)
            label_item = QTableWidgetItem(label)
            label_item.setFlags(label_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.partition_nas_paths_table.setItem(i, 0, label_item)
            self.partition_nas_paths_table.setItem(i, 1, QTableWidgetItem(nas_path))

            # Add delete button
            delete_button = QPushButton("X")
            delete_button.setFixedWidth(36)
            delete_button.clicked.connect(lambda chk=False, t=self.partition_nas_paths_table, b=delete_button: self.delete_row(t, b))
            self.partition_nas_paths_table.setCellWidget(i, 2, delete_button)

    def delete_row(self, table: QTableWidget, button: QPushButton):
        index = table.indexAt(button.pos())
        if index.isValid():
            table.removeRow(index.row())

    def get_partition_fstypes_from_table(self):
        partition_fstypes = {}
        for row in range(self.partition_fstypes_table.rowCount()):
            label_item = self.partition_fstypes_table.item(row, 0)
            fstype_item = self.partition_fstypes_table.item(row, 1)
            if label_item and fstype_item:
                partition_fstypes[label_item.text().strip()] = fstype_item.text().strip()
        return partition_fstypes

    def get_partition_nas_paths_from_table(self):
        partition_nas_paths = {}
        for row in range(self.partition_nas_paths_table.rowCount()):
            local_item = self.partition_nas_paths_table.item(row, 0)
            nas_item = self.partition_nas_paths_table.item(row, 1)
            if local_item and nas_item:
                partition_nas_paths[local_item.text().strip()] = nas_item.text().strip()
        return partition_nas_paths

    # ---- Detect partitions ----
    def on_detect_partitions(self):
        partition_fstypes = detect_partition_fstypes()
        partition_nas_paths = get_partition_nas_paths(partition_fstypes)
        self.populate_partition_fstypes_table(partition_fstypes)
        self.populate_partition_nas_paths_table(partition_nas_paths)

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
