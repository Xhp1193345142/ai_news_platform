from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from app.api.routes import media
from app.main import app


class StoredBody:
    def iter_chunks(self, chunk_size):
        yield b"image"


class StorageStub:
    def get_object(self, **_):
        return {"Body": StoredBody(), "ContentType": "image/webp"}


def test_public_media_streams_object(monkeypatch) -> None:
    monkeypatch.setattr(media, "get_object_storage_client", lambda: StorageStub())
    with TestClient(app) as client:
        response = client.get("/api/v1/media/openai/gpt-5-6/media/example.webp")
    assert response.status_code == 200
    assert response.content == b"image"
    assert response.headers["content-type"] == "image/webp"


def test_public_media_rejects_unknown_prefix() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/media/private/example.webp")
    assert response.status_code == 404


def test_public_media_returns_404_for_missing_object(monkeypatch) -> None:
    class MissingStorage:
        def get_object(self, **_):
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

    monkeypatch.setattr(media, "get_object_storage_client", lambda: MissingStorage())
    with TestClient(app) as client:
        response = client.get("/api/v1/media/openai/gpt-5-6/media/missing.webp")
    assert response.status_code == 404
