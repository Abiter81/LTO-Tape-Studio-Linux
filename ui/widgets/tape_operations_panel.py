"""Panel with common tape operations and generation selection."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.hardware_controller import HardwareController, TapeGeneration


class TapeOperationsPanel(QWidget):
    def __init__(self, controller: HardwareController, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller

        gen_box = QGroupBox("Tape Generation")
        gen_layout = QFormLayout(gen_box)
        self.gen_combo = QComboBox()
        for g in TapeGeneration:
            self.gen_combo.addItem(g.value, g)
        self.gen_combo.currentIndexChanged.connect(self._on_gen_changed)
        gen_layout.addRow("Generation:", self.gen_combo)

        ops_box = QGroupBox("Operations")
        ops_layout = QHBoxLayout(ops_box)
        self.rewind_btn = QPushButton("Rewind")
        self.eject_btn = QPushButton("Eject")
        self.retension_btn = QPushButton("Retension")
        self.erase_btn = QPushButton("Erase")
        self.status_btn = QPushButton("Status")
        for b in (self.rewind_btn, self.eject_btn, self.retension_btn, self.erase_btn, self.status_btn):
            ops_layout.addWidget(b)

        layout = QVBoxLayout(self)
        layout.addWidget(gen_box)
        layout.addWidget(ops_box)
        layout.addStretch()

        self.rewind_btn.clicked.connect(lambda: self.controller.rewind())
        self.eject_btn.clicked.connect(lambda: self.controller.eject())
        self.retension_btn.clicked.connect(lambda: self.controller.retension())
        self.erase_btn.clicked.connect(lambda: self.controller.erase())
        self.status_btn.clicked.connect(lambda: self.controller.status())

    def _on_gen_changed(self, _idx: int) -> None:
        gen = self.gen_combo.currentData()
        if gen is not None:
            self.controller.set_generation(gen)