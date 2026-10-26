"""Job queue widget showing backup jobs and their state."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class JobQueueWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.list = QListWidget()
        self.add_btn = QPushButton("Enqueue Job")
        self.cancel_btn = QPushButton("Cancel Selected")
        self.clear_btn = QPushButton("Clear")
        row = QHBoxLayout()
        row.addWidget(self.add_btn)
        row.addWidget(self.cancel_btn)
        row.addWidget(self.clear_btn)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Job Queue"))
        layout.addWidget(self.list)
        layout.addLayout(row)

    def add_job(self, text: str) -> None:
        self.list.addItem(text)

    def selected_row(self) -> int:
        items = self.list.selectedItems()
        if not items:
            return -1
        return self.list.row(items[0])