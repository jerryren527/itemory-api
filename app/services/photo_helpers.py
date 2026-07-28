import uuid

import boto3
from django.conf import settings

ALLOWED_PHOTO_CONTENT_TYPES = {"image/jpeg": "jpg", "image/png": "png"}

PHOTO_UPLOAD_EXPIRES_IN = 300  # 5 minutes


def _s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_S3_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def presign_item_photo_upload(item_id, content_type):
    """
    Build a presigned S3 PUT URL for an item photo. Returns
    (upload_url, photo_url, expires_in). Caller is responsible for validating
    `content_type` against ALLOWED_PHOTO_CONTENT_TYPES first.
    """
    ext = ALLOWED_PHOTO_CONTENT_TYPES[content_type]
    key = f"items/{item_id}/{uuid.uuid4()}.{ext}"

    upload_url = _s3_client().generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.AWS_S3_BUCKET_NAME,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=PHOTO_UPLOAD_EXPIRES_IN,
    )

    photo_url = f"https://{settings.AWS_S3_BUCKET_NAME}.s3.{settings.AWS_S3_REGION}.amazonaws.com/{key}"

    return upload_url, photo_url, PHOTO_UPLOAD_EXPIRES_IN
