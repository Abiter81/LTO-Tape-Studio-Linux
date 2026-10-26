"""Main application window for LTO Tape Studio."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.backup_engine import BackupEngine, BackupJob, CompressionMode
from core.restore_engine import RestoreEngine, RestoreJob
from core.checksum import HashAlgorithm
from core.hardware_controller import HardwareController, TapeGeneration
from core.i18n import tr, set_language
from core.logger import TapeLogger
from core.config import AppConfig
from ui.widgets.job_queue import JobQueueWidget
from ui.widgets.source_selector import SourceSelector
from ui.widgets.tape_change_dialog import TapeChangeDialog
from ui.widgets.tape_operations_panel import TapeOperationsPanel


DARK_STYLESHEET = """
QMainWindow { background-color: #1e1e2e; color: #cdd6f4; }
QWidget { background-color: #1e1e2e; color: #cdd6f4; font-family: 'Segoe UI', sans-serif; }
QTabWidget::pane { border: 1px solid #45475a; }
QTabBar::tab { background: #313244; padding: 8px 16px; margin: 2px; border-radius: 4px; }
QTabBar::tab:selected { background: #89b4fa; color: #1e1e2e; }
QPushButton { background-color: #313244; border: 1px solid #45475a; padding: 6px 12px; border-radius: 4px; }
QPushButton:hover { background-color: #45475a; }
QPushButton:pressed { background-color: #585b70; }
QLineEdit, QComboBox { background-color: #313244; border: 1px solid #45475a; padding: 4px; border-radius: 4px; }
QProgressBar { border: 1px solid #45475a; border-radius: 4px; text-align: center; }
QProgressBar::chunk { background-color: #89b4fa; }
QGroupBox { border: 1px solid #45475a; margin-top: 8px; padding-top: 8px; border-radius: 6px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QListWidget { background-color: #313244; border: 1px solid #45475a; }
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(tr("LTO Tape Studio - Enterprise"))
        self.resize(1200, 800)
        self.setStyleSheet(DARK_STYLESHEET)

        self.logger = TapeLogger.instance()
        self.config = AppConfig()
        self.controller = HardwareController()
        devices = HardwareController.discover_devices()
        if devices:
            self.controller.set_device(devices[0].path, devices[0].sg_path)

        self.backup_engine = BackupEngine(self.controller, self.logger)
        self.backup_engine.multivolume.tape_change_required.connect(self._on_tape_change)
        self.restore_engine = RestoreEngine(self.controller, self.logger)
        self.restore_engine.finished.connect(self._on_restore_finished)
        self.restore_engine.multivolume.tape_change_required.connect(self._on_restore_tape_change)

        self._build_ui()
        self._build_menubar()
        self._restore_settings()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_telemetry)
        self._timer.start(1000)

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Header / dashboard
        dash = QGroupBox(tr("Live Dashboard"))
        dash_layout = QHBoxLayout(dash)
        self.device_label = QLabel(f"{tr('Device')}: {self.controller.device}")
        self.gen_label = QLabel(f"{tr('Generation')}: -")
        self.status_label = QLabel(f"{tr('Status')}: -")
        self.speed_label = QLabel(f"{tr('Speed')}: 0.0 MB/s")
        self.capacity_label = QLabel(f"{tr('Capacity')}: -")
        for w in (self.device_label, self.gen_label, self.status_label, self.speed_label, self.capacity_label):
            dash_layout.addWidget(w)
        self.util_bar = QProgressBar()
        self.util_bar.setRange(0, 100)
        dash_layout.addWidget(self.util_bar)
        self.telemetry_label = QLabel("Telemetry: -")
        dash_layout.addWidget(self.telemetry_label)
        layout.addWidget(dash)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        # Backup tab
        backup_tab = QWidget()
        backup_layout = QVBoxLayout(backup_tab)
        self.source_selector = SourceSelector()
        backup_layout.addWidget(self.source_selector)

        opts = QGroupBox("Backup Options")
        opts_layout = QHBoxLayout(opts)
        opts_layout.addWidget(QLabel("Compression:"))
        self.comp_combo = QComboBox()
        for m in CompressionMode:
            self.comp_combo.addItem(m.value, m)
        opts_layout.addWidget(self.comp_combo)
        opts_layout.addWidget(QLabel("Checksum:"))
        self.hash_combo = QComboBox()
        for h in HashAlgorithm:
            self.hash_combo.addItem(h.value, h)
        opts_layout.addWidget(self.hash_combo)
        opts_layout.addWidget(QLabel("Label:"))
        self.label_edit = QLineEdit("backup")
        opts_layout.addWidget(self.label_edit)
        opts_layout.addWidget(QLabel("Block size:"))
        self.block_edit = QLineEdit("262144")
        opts_layout.addWidget(self.block_edit)
        self.encrypt_check = QCheckBox("Encrypt")
        opts_layout.addWidget(self.encrypt_check)
        self.verify_check = QCheckBox("Verify (read-after-write)")
        opts_layout.addWidget(self.verify_check)
        self.passphrase_edit = QLineEdit()
        self.passphrase_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.passphrase_edit.setPlaceholderText("Passphrase")
        opts_layout.addWidget(self.passphrase_edit)
        backup_layout.addWidget(opts)

        run_row = QHBoxLayout()
        self.start_btn = QPushButton(tr("Start Backup"))
        self.cancel_btn = QPushButton(tr("Cancel"))
        run_row.addWidget(self.start_btn)
        run_row.addWidget(self.cancel_btn)
        backup_layout.addLayout(run_row)

        self.progress = QProgressBar()
        backup_layout.addWidget(self.progress)
        self.current_file_label = QLabel(tr("Idle"))
        backup_layout.addWidget(self.current_file_label)
        tabs.addTab(backup_tab, tr("Backup"))

        # Tape ops tab
        ops_tab = TapeOperationsPanel(self.controller)
        tabs.addTab(ops_tab, tr("Tape Operations"))

        # Job queue tab
        self.job_queue = JobQueueWidget()
        tabs.addTab(self.job_queue, tr("Job Queue"))

        # Restore tab
        restore_tab = QWidget()
        restore_layout = QVBoxLayout(restore_tab)
        restore_layout.addWidget(QLabel("Destination:"))
        self.restore_dest_edit = QLineEdit(str(Path.home() / "restore"))
        restore_layout.addWidget(self.restore_dest_edit)
        self.restore_pass_edit = QLineEdit()
        self.restore_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.restore_pass_edit.setPlaceholderText("Passphrase (if encrypted)")
        restore_layout.addWidget(self.restore_pass_edit)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_restore_dest)
        restore_layout.addWidget(browse_btn)
        self.restore_tape_btn = QPushButton("Restore from Tape")
        self.restore_files_btn = QPushButton("Restore from Volume Files")
        restore_layout.addWidget(self.restore_tape_btn)
        restore_layout.addWidget(self.restore_files_btn)
        restore_layout.addStretch()
        tabs.addTab(restore_tab, tr("Restore"))
        self.restore_tape_btn.clicked.connect(self._start_restore_tape)
        self.restore_files_btn.clicked.connect(self._start_restore_files)

        # Log view
        log_box = QGroupBox(tr("Audit Log"))
        log_layout = QVBoxLayout(log_box)
        from PySide6.QtWidgets import QTextEdit
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_box)

        self.logger.register_listener(self._append_log)

        # Signals
        self.start_btn.clicked.connect(self._start_backup)
        self.cancel_btn.clicked.connect(self.backup_engine.cancel)
        self.backup_engine.progress.connect(lambda v: self.progress.setValue(int(v * 100)))
        self.backup_engine.speed.connect(lambda v: self.speed_label.setText(f"Speed: {v:.1f} MB/s"))
        self.backup_engine.status.connect(lambda s: self.status_label.setText(f"Status: {s}"))
        self.backup_engine.current_file.connect(lambda f: self.current_file_label.setText(f))
        self.backup_engine.finished.connect(self._on_finished)

    # ------------------------------------------------------------------ #
    def _restore_settings(self) -> None:
        try:
            self.label_edit.setText(self.config.get("label", "backup"))
            self.block_edit.setText(str(self.config.get("block_size", 262144)))
            self.encrypt_check.setChecked(bool(self.config.get("encrypt", False)))
            # Note: passphrase is intentionally never persisted for security.
            comp = self.config.get("compression")
            if comp:
                for i in range(self.comp_combo.count()):
                    if self.comp_combo.itemData(i) and self.comp_combo.itemData(i).value == comp:
                        self.comp_combo.setCurrentIndex(i)
                        break
            hsh = self.config.get("hash")
            if hsh:
                for i in range(self.hash_combo.count()):
                    if self.hash_combo.itemData(i) and self.hash_combo.itemData(i).value == hsh:
                        self.hash_combo.setCurrentIndex(i)
                        break
            lang = self.config.get("language", "en")
            set_language(lang)
        except Exception:
            pass

    def _save_settings(self) -> None:
        try:
            self.config.set("label", self.label_edit.text())
            self.config.set("block_size", self.block_edit.text())
            self.config.set("encrypt", self.encrypt_check.isChecked())
            comp = self.comp_combo.currentData()
            if comp is not None:
                self.config.set("compression", comp.value)
            hsh = self.hash_combo.currentData()
            if hsh is not None:
                self.config.set("hash", hsh.value)
        except Exception:
            pass

    def _start_backup(self) -> None:
        sources = self.source_selector.sources()
        if not sources:
            QMessageBox.warning(self, "No sources", "Please select at least one source.")
            return
        self._save_settings()
        job = BackupJob(
            job_id=uuid.uuid4().hex[:8],
            sources=sources,
            label=self.label_edit.text() or "backup",
            compression=self.comp_combo.currentData(),
            checksum=self.hash_combo.currentData(),
            block_size=int(self.block_edit.text() or 262144),
            encrypt=self.encrypt_check.isChecked(),
            passphrase=self.passphrase_edit.text(),
            verify=self.verify_check.isChecked(),
        )
        self.job_queue.add_job(f"{job.job_id} - {job.label}")
        self.backup_engine.start(job)
        self.start_btn.setEnabled(False)

    def _on_finished(self, ok: bool, msg: str) -> None:
        self.start_btn.setEnabled(True)
        if ok:
            QMessageBox.information(self, "Backup", msg)
        else:
            QMessageBox.critical(self, "Backup failed", msg)

    def _on_tape_change(self, vol: int, msg: str) -> None:
        dlg = TapeChangeDialog(vol, msg, self)
        if dlg.exec() == TapeChangeDialog.DialogCode.Accepted:
            self.backup_engine.multivolume.confirm_volume_change()
        else:
            self.backup_engine.multivolume.cancel_volume_change()
            self.backup_engine.cancel()

    def _append_log(self, entry) -> None:
        self.log_view.append(entry.formatted())

    def _refresh_telemetry(self) -> None:
        try:
            t = self.controller.status()
            self.status_label.setText(f"Status: {t.status.value}")
            gen = self.controller.current_generation()
            if gen is None:
                gen = self.controller.detect_generation()
            self.gen_label.setText(f"Generation: {gen.value if gen else '-'}")
            cap = self.controller.native_capacity()
            if cap:
                used = t.bytes_written
                pct = int(used / cap * 100) if cap else 0
                self.util_bar.setValue(min(100, pct))
                self.capacity_label.setText(f"{tr('Capacity')}: {used // (1024**3)} / {cap // (1024**3)} GB")
            # Hardware telemetry via sg_logs (best-effort)
            try:
                logs = self.controller.sg_logs()
                temp = None
                load_count = None
                for k, v in logs.items():
                    kl = k.lower()
                    if "temp" in kl:
                        try:
                            temp = float(v.split()[0])
                        except Exception:
                            temp = v
                    if "load" in kl:
                        load_count = v
                parts = []
                if temp is not None:
                    parts.append(f"Temp: {temp}°C")
                if load_count is not None:
                    parts.append(f"Loads: {load_count}")
                if parts:
                    self.telemetry_label.setText("Telemetry: " + ", ".join(parts))
            except Exception:
                pass
        except Exception:
            pass

    def _browse_restore_dest(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Restore destination")
        if d:
            self.restore_dest_edit.setText(d)

    def _start_restore_tape(self) -> None:
        job = RestoreJob(destination=Path(self.restore_dest_edit.text()), passphrase=self.restore_pass_edit.text())
        self.restore_engine.restore_from_tape(job)

    def _start_restore_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Select volume images")
        if not files:
            return
        job = RestoreJob(destination=Path(self.restore_dest_edit.text()), passphrase=self.restore_pass_edit.text())
        self.restore_engine.restore_from_file([Path(f) for f in files], job)

    def _on_restore_tape_change(self, vol: int, msg: str) -> None:
        dlg = TapeChangeDialog(vol, msg, self)
        if dlg.exec() == TapeChangeDialog.DialogCode.Accepted:
            self.restore_engine.multivolume.confirm_volume_change()
        else:
            self.restore_engine.multivolume.cancel_volume_change()
            self.restore_engine.cancel()

    def _on_restore_finished(self, ok: bool, msg: str) -> None:
        if ok:
            QMessageBox.information(self, "Restore", msg)
        else:
            QMessageBox.critical(self, "Restore failed", msg)

    def _build_menubar(self) -> None:
        menubar = self.menuBar()
        help_menu = menubar.addMenu(tr("Help"))
        about_action = help_menu.addAction(tr("About"))
        about_action.triggered.connect(self._show_about)

        lang_menu = menubar.addMenu("Language")
        for code, name in (("en", "English"), ("de", "Deutsch")):
            act = lang_menu.addAction(name)
            act.triggered.connect(lambda _checked=False, c=code: self._set_language(c))

    def _set_language(self, code: str) -> None:
        set_language(code)
        self.config.set("language", code)
        self.status_label.setText(f"{tr('Status')}: {code}")
        QMessageBox.information(self, "Language", f"Language set to {code}. Restart the app for full effect.")

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "About LTO Tape Studio",
            "LTO Tape Studio - Enterprise\n"
            "Version 1.0.0\n\n"
            "Programmed by Jörg Althaus\n"
            "LTO tape management and archiving for Linux.",
        )

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.backup_engine.cancel()
        self.restore_engine.cancel()
        super().closeEvent(event)
