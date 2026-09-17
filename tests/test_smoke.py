import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture()
def client() -> TestClient:
    return TestClient(main.app)


def test_index_returns_html(client: TestClient) -> None:
    response = client.get('/')
    assert response.status_code == 200
    assert '文档互转工具' in response.text


def test_health_reports_libreoffice_flag(client: TestClient) -> None:
    response = client.get('/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert isinstance(payload['libreoffice'], bool)


def test_invalid_conversion_pair_returns_400(client: TestClient) -> None:
    response = client.post('/api/convert', files={'file': ('a.txt', b'hello', 'text/plain')}, data={'target': 'pdf'})
    assert response.status_code == 400


@pytest.mark.parametrize(
    ('filename', 'target', 'expected_status'),
    [
        ('doc.pdf', 'docx', 200),
        ('doc.pdf', 'pptx', 200),
        ('doc.docx', 'pdf', 200),
        ('deck.pptx', 'pdf', 200),
        ('doc.docx', 'pptx', 200),
        ('deck.pptx', 'docx', 200),
    ],
)
def test_supported_conversion_pairs_are_accepted(client: TestClient, filename: str, target: str, expected_status: int) -> None:
    content = b'%PDF-1.4' if filename.endswith('.pdf') else b'zip-marker'
    response = client.post('/api/convert', files={'file': (filename, content, 'application/octet-stream')}, data={'target': target})
    assert response.status_code == expected_status
