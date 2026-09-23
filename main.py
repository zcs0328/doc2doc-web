from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from conversion_engine import ConversionEngine, EngineResult

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / 'uploads'
OUTPUT_DIR = BASE_DIR / 'outputs'
STATIC_DIR = BASE_DIR / 'static'

app = FastAPI(title='文档互转工具')
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

engine = ConversionEngine(OUTPUT_DIR)


def ensure_dirs() -> None:
    UPLOAD_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)


def infer_source_ext(filename: str) -> str:
    extension = Path(filename).suffix.lower().lstrip('.')
    if extension in {'doc', 'docx'}:
        return 'docx'
    if extension in {'ppt', 'pptx'}:
        return 'pptx'
    if extension == "pdf":
        return 'pdf'
    raise HTTPException(400, '不支持该源文件类型，请上传 PDF、Word 或 PPT 文件')


def safe_target_ext(target: str) -> str:
    if target not in CONVERSION_TARGETS:
        raise HTTPException(400, '目标格式只支持 pdf、docx 或 pptx')
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


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {
        'status': 'ok',
        'engines': engine.available(),
        'conversions': len(ALLOWED_PAIRS),
    }


@app.post("/api/convert")
async def convert(file: UploadFile = File(...), target: str = Form("docx")) -> dict:
    ensure_dirs()
    source_ext = infer_source_ext(file.filename or "upload.pdf")
    target_ext = safe_target_ext(target)
    pair = (source_ext, target_ext)
    if pair not in ALLOWED_PAIRS:
        supported = [
            f"{source} → {destination}"
            for source, destination in ALLOWED_PAIRS
        ]
        detail = f'不支持 {source_ext} → {target_ext}，当前支持：{chr(10).join(supported)}'
        raise HTTPException(400, detail)

    task_id = create_task()
    safe_name = f'{task_id[:12]}-{Path(file.filename or "upload.pdf").stem}'
    source_file = UPLOAD_DIR / f'{safe_name}.{source_ext}'
    with source_file.open('wb') as output_handle:
        shutil.copyfileobj(file.file, output_handle)

    TASKS[task_id]['status'] = 'processing'
    TASKS[task_id]['message'] = '正在转换文件'

    target_file = OUTPUT_DIR / f'{safe_name}.{target_ext}'
    result: EngineResult = engine.convert(source_file, target_file)

    if not result.ok:
        mark_failed(task_id, f'转换失败（{result.engine}）：{result.error}')
        return TASKS[task_id] | {"task_id": task_id}

    TASKS[task_id]['status'] = 'completed'
    TASKS[task_id]['message'] = f'转换完成（引擎：{result.engine}）'
    TASKS[task_id]['download_url'] = f'/api/download/{task_id}'
    TASKS[task_id]['output_path'] = str(target_file)
    return TASKS[task_id] | {"task_id": task_id}


@app.get("/api/tasks/{task_id}")
def task_status(task_id: str) -> dict:
    if task_id not in TASKS:
        raise HTTPException(404, '任务不存在')
    return TASKS[task_id] | {"task_id": task_id}


@app.get("/api/download/{task_id}")
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
