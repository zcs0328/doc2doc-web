from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class EngineError(RuntimeError):
    def __init__(self, message, engine):
        super().__init__(message)
        self.engine = engine


@dataclass
class EngineResult:
    ok: bool
    engine: str
    error: str = ""


class ConversionEngine:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self._libreoffice_bin = self._find_libreoffice()

    def _find_libreoffice(self):
        candidates = [
            os.environ.get("LIBREOFFICE_BIN"),
            shutil.which("soffice"),
            shutil.which("libreoffice"),
            r"C:\Program Files\LibreOffice\program\soffice.exe",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return None

    def available(self):
        pdf2docx_ok = False
        try:
            import pdf2docx
            pdf2docx_ok = True
        except Exception:
            pass
        return {"libreoffice": bool(self._libreoffice_bin), "pdf2docx": pdf2docx_ok}

    def _run_pdf2docx(self, source_file, target_file):
        from pdf2docx import Converter
        converter = Converter(str(source_file))
        try:
            converter.convert(str(target_file))
        finally:
            converter.close()
        if not target_file.exists():
            raise EngineError("pdf2docx did not produce output", "pdf2docx")

    def _run_libreoffice(self, source_file, target_file):
        if not self._libreoffice_bin:
            raise EngineError("LibreOffice not installed", "libreoffice")
        target_ext = target_file.suffix.lstrip(".")
        with tempfile.TemporaryDirectory(prefix="doc2doc-") as tmp_dir:
            command = [
                self._libreoffice_bin,
                "--headless",
                "--convert-to",
                target_ext,
                "--outdir",
                tmp_dir,
                str(source_file),
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "").strip()
                raise EngineError(detail[:300] or "LibreOffice conversion failed", "libreoffice")
            converted = Path(tmp_dir) / f"{source_file.stem}{target_file.suffix}"
            if not converted.exists():
                raise EngineError("LibreOffice produced no output", "libreoffice")
            shutil.move(str(converted), str(target_file))

    def convert(self, source_file, target_file):
        source_file = Path(source_file)
        target_file = Path(target_file)
        target_file.parent.mkdir(parents=True, exist_ok=True)
        src = source_file.suffix.lower().lstrip(".")
        dst = target_file.suffix.lower().lstrip(".")
        if src == "pdf" and dst == "docx":
            try:
                self._run_pdf2docx(source_file, target_file)
                return EngineResult(ok=True, engine="pdf2docx")
            except Exception as error:
                return EngineResult(ok=False, engine="pdf2docx", error=str(error))
        try:
            self._run_libreoffice(source_file, target_file)
            return EngineResult(ok=True, engine="libreoffice")
        except Exception as error:
            return EngineResult(ok=False, engine="libreoffice", error=str(error))
