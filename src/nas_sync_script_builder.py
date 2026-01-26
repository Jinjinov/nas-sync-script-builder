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


class NasSyncScriptBuilder(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("NAS Configuration")
        self.resize(400, 200)

        # Top-level vertical layout (like a StackPanel)
        main_layout = QVBoxLayout(self)

        # Form layout (label + field pairs)
        form_layout = QFormLayout()

        self.nas_host_edit = QLineEdit()
        self.nas_user_edit = QLineEdit()
        self.mount_root_edit = QLineEdit("/mnt/nas")

        form_layout.addRow("NAS Host:", self.nas_host_edit)
        form_layout.addRow("NAS Username:", self.nas_user_edit)
        form_layout.addRow("NAS Mount Root:", self.mount_root_edit)

        main_layout.addLayout(form_layout)

        # Save button at the bottom
        save_button = QPushButton("Save (print to stdout)")
        save_button.clicked.connect(self.on_save)
        main_layout.addWidget(save_button)

    def on_save(self):
        print("NAS Host:", self.nas_host_edit.text())
        print("NAS Username:", self.nas_user_edit.text())
        print("NAS Mount Root:", self.mount_root_edit.text())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NasSyncScriptBuilder()
    window.show()
    sys.exit(app.exec())
