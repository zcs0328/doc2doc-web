from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / 'uploads'
OUTPUT_DIR = BASE_DIR / 'outputs'
STATIC_DIR = BASE_DIR / 'static'

app = FastAPI(title='文档互转服务')
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')

CONVERSION_TARGETS: Dict[str, str] = {
    'pdf': 'pdf',
    'docx': 'docx',
    'pptx': 'pptx',
}

ALLOWED_PAIRS = {
    ('pdf', 'docx'),
    ('pdf', 'pptx'),
    ('docx', 'pdf'),
    ('pptx', 'pdf'),
    ('docx', 'pptx'),
    ('pptx', 'docx'),
}

TASKS: Dict[str, dict] = {}


def find_libreoffice() -> str | None:
    candidates = [
        os.environ.get('LIBREOFFICE_BIN'),
        shutil.which('soffice'),
        shutil.which('libreoffice'),
        r'C:\\Program Files\\LibreOffice\\program\\soffice.exe',
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


LIBREOFFICE_BIN = find_libreoffice()


def ensure_dirs() -> None:
    UPLOAD_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)


def infer_source_ext(filename: str) -> str:
    extension = Path(filename).suffix.lower().lstrip('.')
    if extension in {'doc', 'docx'}:
        return 'docx'
    if extension in {'ppt', 'pptx'}:
        return 'pptx'
    if extension == 'pdf':
        return 'pdf'
    raise HTTPException(400, '暂不支持该源文件类型，请上传 PDF、Word 或 PPT 文件')


def safe_target_ext(target: str) -> str:
    if target not in CONVERSION_TARGETS:
        raise HTTPException(400, '目标格式必须是 pdf、docx 或 pptx')
    return CONVERSION_TARGETS[target]


def create_task() -> str:
    task_id = uuid.uuid4().hex
    TASKS[task_id] = {
        'status': 'created',
        'message': '已创建转换任务',
        'download_url': '',
    }
    return task_id


def mark_failed(task_id: str, message: str) -> None:
    TASKS[task_id]['status'] = 'failed'
    TASKS[task_id]['message'] = message


def run_libreoffice(libreoffice_bin: str, source_file: Path, target_file: Path) -> None:
    with tempfile.TemporaryDirectory(prefix='doc2doc-') as tmp_dir:
        command = [
            libreoffice_bin,
            '--headless',
            '--convert-to',
            target_file.suffix.lstrip('.'),
            '--outdir',
            tmp_dir,
            str(source_file),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or '').strip()
            raise RuntimeError(detail[:300] or 'LibreOffice 转换失败')

        converted = Path(tmp_dir) / f'{source_file.stem}{target_file.suffix}'
        if not converted.exists():
            raise RuntimeError('未找到转换结果文件')
        shutil.move(converted, target_file)


def convert_with_pdf_to_docx(source_file: Path, target_file: Path) -> bool:
    target_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        from pdf2docx import Converter  # type: ignore

        converter = Converter(str(source_file))
        converter.convert(str(target_file))
        converter.close()
        return target_file.exists()
    except Exception:
        return False


@app.get('/')
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / 'index.html')


@app.get('/health')
def health() -> dict:
    return {
        'status': 'ok',
        'libreoffice': bool(LIBREOFFICE_BIN),
        'conversions': len(ALLOWED_PAIRS),
    }


@app.post('/api/convert')
async def convert(file: UploadFile = File(...), target: str = Form('docx')) -> dict:
    ensure_dirs()
    source_ext = infer_source_ext(file.filename or 'upload.pdf')
    target_ext = safe_target_ext(target)
    pair = (source_ext, target_ext)
    if pair not in ALLOWED_PAIRS:
        supported = [
            f'{source} → {destination}'
            for source, destination in ALLOWED_PAIRS
        ]
        detail = f'暂不支持 {source_ext} → {target_ext}；当前支持：{chr(10).join(supported)}'
        raise HTTPException(400, detail)

    task_id = create_task()
    safe_name = f'{task_id[:12]}-{Path(file.filename or "upload.pdf").stem}'
    source_file = UPLOAD_DIR / f'{safe_name}.{source_ext}'
    with source_file.open('wb') as output_handle:
        shutil.copyfileobj(file.file, output_handle)

    TASKS[task_id]['status'] = 'processing'
    TASKS[task_id]['message'] = '正在转换文件'

    if source_ext == 'pdf' and target_ext == 'docx' and convert_with_pdf_to_docx(source_file, OUTPUT_DIR / f'{safe_name}.{target_ext}'):
        TASKS[task_id]['status'] = 'completed'
        TASKS[task_id]['message'] = '转换完成'
        TASKS[task_id]['download_url'] = f'/api/download/{task_id}'
        TASKS[task_id]['output_path'] = str(OUTPUT_DIR / f'{safe_name}.{target_ext}')
        return TASKS[task_id] | {'task_id': task_id}

    if not LIBREOFFICE_BIN:
        mark_failed(task_id, '服务器未安装 LibreOffice，无法执行该转换。请按 README 安装 LibreOffice 后重试。')
        return TASKS[task_id] | {'task_id': task_id}

    target_file = OUTPUT_DIR / f'{safe_name}.{target_ext}'
    try:
        run_libreoffice(LIBREOFFICE_BIN, source_file, target_file)
    except Exception as error:
        mark_failed(task_id, f'转换失败：{error}')
        return TASKS[task_id] | {'task_id': task_id}

    TASKS[task_id]['status'] = 'completed'
    TASKS[task_id]['message'] = '转换完成'
    TASKS[task_id]['download_url'] = f'/api/download/{task_id}'
    TASKS[task_id]['output_path'] = str(target_file)
    return TASKS[task_id] | {'task_id': task_id}


@app.get('/api/tasks/{task_id}')
def task_status(task_id: str) -> dict:
    if task_id not in TASKS:
        raise HTTPException(404, '任务不存在')
    return TASKS[task_id] | {'task_id': task_id}


@app.get('/api/download/{task_id}')
def download(task_id: str) -> FileResponse:
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(404, '任务不存在')
    output_path = task.get('output_path', '')
    if task.get('status') != 'completed' or not output_path or not Path(output_path).exists():
        raise HTTPException(400, '暂无可下载文件')
    return FileResponse(output_path, media_type='application/octet-stream')


if __name__ == '__main__':
    import uvicorn

    ensure_dirs()
    port = int(os.environ.get('PORT', '8000'))
    uvicorn.run(app, host='0.0.0.0', port=port)
