"""Roundtrip backup/restore tests (unittest, no external deps)."""

import os
import sys
import tempfile
import time
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from core.hardware_controller import HardwareController
from core.backup_engine import BackupEngine, BackupJob
from core.restore_engine import RestoreEngine, RestoreJob
from core.compression_engine import CompressionMode
from core.checksum import HashAlgorithm


class RoundtripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _run_backup(self, be, job):
        done = {"ok": None, "msg": None}
        be.finished.connect(lambda ok, msg: (done.__setitem__("ok", ok), done.__setitem__("msg", msg)))
        be.start(job)
        for _ in range(200):
            self.app.processEvents()
            time.sleep(0.05)
            if done["ok"] is not None:
                break
        return done

    def _run_restore(self, re, files, job):
        done = {"ok": None, "msg": None}
        re.finished.connect(lambda ok, msg: (done.__setitem__("ok", ok), done.__setitem__("msg", msg)))
        re.restore_from_file(files, job)
        for _ in range(200):
            self.app.processEvents()
            time.sleep(0.05)
            if done["ok"] is not None:
                break
        return done

    def test_roundtrip_none(self):
        d = Path(tempfile.mkdtemp())
        (d / "a.txt").write_text("hello" * 100)
        (d / "sub").mkdir()
        (d / "sub" / "b.txt").write_text("world" * 50)
        tape = Path(tempfile.mkdtemp()) / "tape.img"
        hc = HardwareController(str(tape))
        be = BackupEngine(hc)
        job = BackupJob(job_id="1", sources=[d], label="t", compression=CompressionMode.NONE,
                        checksum=HashAlgorithm.SHA256, block_size=0)
        done = self._run_backup(be, job)
        self.assertTrue(done["ok"], done)

        outdir = Path(tempfile.mkdtemp()) / "out"
        re = RestoreEngine(hc)
        rjob = RestoreJob(destination=outdir)
        rdone = self._run_restore(re, [tape], rjob)
        self.assertTrue(rdone["ok"], rdone)
        self.assertEqual((outdir / "a.txt").read_text(), (d / "a.txt").read_text())
        self.assertEqual((outdir / "sub" / "b.txt").read_text(), (d / "sub" / "b.txt").read_text())

    def test_roundtrip_gzip(self):
        d = Path(tempfile.mkdtemp())
        (d / "a.txt").write_text("hello" * 1000)
        tape = Path(tempfile.mkdtemp()) / "tape.img"
        hc = HardwareController(str(tape))
        be = BackupEngine(hc)
        job = BackupJob(job_id="2", sources=[d], label="t", compression=CompressionMode.SOFTWARE_GZIP,
                        checksum=HashAlgorithm.SHA256, block_size=0)
        done = self._run_backup(be, job)
        self.assertTrue(done["ok"], done)

        outdir = Path(tempfile.mkdtemp()) / "out"
        re = RestoreEngine(hc)
        rjob = RestoreJob(destination=outdir)
        rdone = self._run_restore(re, [tape], rjob)
        self.assertTrue(rdone["ok"], rdone)
        self.assertEqual((outdir / "a.txt").read_text(), (d / "a.txt").read_text())

    def test_roundtrip_encrypted(self):
        d = Path(tempfile.mkdtemp())
        (d / "a.txt").write_text("secret" * 200)
        tape = Path(tempfile.mkdtemp()) / "tape.img"
        hc = HardwareController(str(tape))
        be = BackupEngine(hc)
        job = BackupJob(job_id="4", sources=[d], label="t", compression=CompressionMode.NONE,
                        checksum=HashAlgorithm.SHA256, block_size=0, encrypt=True, passphrase="pw")
        done = self._run_backup(be, job)
        self.assertTrue(done["ok"], done)

        outdir = Path(tempfile.mkdtemp()) / "out"
        re = RestoreEngine(hc)
        rjob = RestoreJob(destination=outdir, passphrase="pw")
        rdone = self._run_restore(re, [tape], rjob)
        self.assertTrue(rdone["ok"], rdone)
        self.assertEqual((outdir / "a.txt").read_text(), (d / "a.txt").read_text())

    def test_roundtrip_zstd(self):
        d = Path(tempfile.mkdtemp())
        (d / "a.txt").write_text("hello" * 1000)
        tape = Path(tempfile.mkdtemp()) / "tape.img"
        hc = HardwareController(str(tape))
        be = BackupEngine(hc)
        job = BackupJob(job_id="3", sources=[d], label="t", compression=CompressionMode.SOFTWARE_ZSTD,
                        checksum=HashAlgorithm.SHA256, block_size=0)
        done = self._run_backup(be, job)
        self.assertTrue(done["ok"], done)

        outdir = Path(tempfile.mkdtemp()) / "out"
        re = RestoreEngine(hc)
        rjob = RestoreJob(destination=outdir)
        rdone = self._run_restore(re, [tape], rjob)
        self.assertTrue(rdone["ok"], rdone)
        self.assertEqual((outdir / "a.txt").read_text(), (d / "a.txt").read_text())


if __name__ == "__main__":
    unittest.main()