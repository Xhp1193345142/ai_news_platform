from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.services.media import get_object_storage_client

router = APIRouter(prefix="/media")


@router.get("/{object_key:path}", include_in_schema=False)
def public_media(object_key: str) -> StreamingResponse:
    if not object_key.startswith("openai/") or ".." in object_key.split("/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="媒体不存在")
    try:
        stored = get_object_storage_client().get_object(
            Bucket=settings.s3_public_bucket, Key=object_key
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="媒体不存在"
            ) from error
        raise
    return StreamingResponse(
        stored["Body"].iter_chunks(chunk_size=128 * 1024),
        media_type=stored.get("ContentType") or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
