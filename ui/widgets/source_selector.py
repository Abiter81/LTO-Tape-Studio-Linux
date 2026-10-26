"""Multi-source selector widget for backup jobs."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SourceSelector(QWidget):
    sources_changed = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        add_folder = QPushButton("Add Folder")
        add_file = QPushButton("Add File")
        add_disk = QPushButton("Add Disk/Mount")
        remove = QPushButton("Remove")
        clear = QPushButton("Clear")

        add_folder.clicked.connect(self._add_folder)
        add_file.clicked.connect(self._add_file)
        add_disk.clicked.connect(self._add_disk)
        remove.clicked.connect(self._remove)
        clear.clicked.connect(self._clear)

        btns = QHBoxLayout()
        for b in (add_folder, add_file, add_disk, remove, clear):
            btns.addWidget(b)

        layout = QVBoxLayout(self)
        layout.addWidget(self._list)
        layout.addLayout(btns)

    def _add_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select source folder")
        if d:
            self._add_path(d)

    def _add_file(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Select source files")
        for f in files:
            self._add_path(f)

    def _add_disk(self) -> None:
        # Allow selecting a mount point root
        d = QFileDialog.getExistingDirectory(self, "Select disk/mount point")
        if d:
            self._add_path(d)

    def _add_path(self, path: str) -> None:
        for i in range(self._list.count()):
            if self._list.item(i).text() == path:
                return
        self._list.addItem(QListWidgetItem(path))
        self._emit()

    def _remove(self) -> None:
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))
        self._emit()

    def _clear(self) -> None:
        self._list.clear()
        self._emit()

    def _emit(self) -> None:
        self.sources_changed.emit(self.sources())

    def sources(self) -> list:
        return [Path(self._list.item(i).text()) for i in range(self._list.count())]