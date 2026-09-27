"""
Cloudinary service — upload odometer images and return secure_url.
"""

import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

from app.config import get_settings

settings = get_settings()

# ── Configure Cloudinary SDK ──────────────────────────────

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)


async def upload_odometer_image(file: UploadFile, folder: str = "odometer_images") -> str:
    """
    Upload an image file to Cloudinary and return the secure URL.

    Args:
        file: FastAPI UploadFile from the request.
        folder: Cloudinary folder to organise uploads.

    Returns:
        The HTTPS secure_url string to store in PostgreSQL.
    """
    contents = await file.read()
    result = cloudinary.uploader.upload(
        contents,
        folder=folder,
        resource_type="image",
        allowed_formats=["jpg", "jpeg", "png", "webp"],
    )
    return result["secure_url"]
