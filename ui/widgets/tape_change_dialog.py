"""Modal dialog requesting the next tape during a multivolume backup."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)


class TapeChangeDialog(QDialog):
    def __init__(self, volume_number: int, message: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tape Change Required")
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(message))
        layout.addWidget(QLabel(f"Target volume: #{volume_number}"))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)