"""Generate and store blog header images (OpenAI + Cloudinary/local fallback)."""

from __future__ import annotations

import base64
import os
from datetime import datetime
from pathlib import Path

import openai
import requests

from cloudinary_util import cloudinary_configured, configure_cloudinary

DEFAULT_BLOG_IMAGE_URL = os.getenv(
    "BLOG_DEFAULT_IMAGE_URL",
    "https://inshora-frontend-nine.vercel.app/blog-default-cover.svg",
)
BLOG_IMAGE_MODEL = os.getenv("BLOG_IMAGE_MODEL", "gpt-image-1")
BACKEND_DIR = Path(__file__).parent
STATIC_IMAGES_DIR = BACKEND_DIR / "static" / "images"


def default_blog_image_url() -> str:
    return DEFAULT_BLOG_IMAGE_URL


def _image_bytes_from_response(image_item) -> bytes:
    if getattr(image_item, "b64_json", None):
        return base64.b64decode(image_item.b64_json)
    if getattr(image_item, "url", None):
        response = requests.get(image_item.url, timeout=60)
        response.raise_for_status()
        return response.content
    raise ValueError("OpenAI image response had no url or b64_json data")


def _store_image_bytes(image_bytes: bytes, *, prefix: str = "blog") -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    if cloudinary_configured():
        try:
            import cloudinary.uploader

            configure_cloudinary()
            upload_result = cloudinary.uploader.upload(
                image_bytes,
                public_id=f"inshora_{prefix}_{timestamp}",
                folder="blog_images",
                resource_type="image",
            )
            print(f"✓ Image uploaded to Cloudinary: {upload_result['public_id']}")
            return upload_result["secure_url"]
        except Exception as exc:
            print(f"✗ Cloudinary upload failed, using local storage: {exc}")

    STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{timestamp}.png"
    filepath = STATIC_IMAGES_DIR / filename
    filepath.write_bytes(image_bytes)
    print(f"✓ Image saved locally: {filename}")
    return f"/static/images/{filename}"


def generate_blog_image_url(topic: str) -> str:
    """Generate an AI blog header image, or return a reliable default on failure."""
    image_prompt = (
        f"Professional insurance blog header illustration about {topic}, "
        "modern flat design, navy blue and orange accents, clean, no text, wide banner"
    )

    try:
        kwargs = {
            "model": BLOG_IMAGE_MODEL,
            "prompt": image_prompt,
            "size": "1024x1024",
            "n": 1,
        }
        if BLOG_IMAGE_MODEL.startswith("dall-e"):
            kwargs["quality"] = "standard"

        image_response = openai.images.generate(**kwargs)
        image_bytes = _image_bytes_from_response(image_response.data[0])
        print(f"✓ Image generated with {BLOG_IMAGE_MODEL}")
        return _store_image_bytes(image_bytes)
    except Exception as exc:
        print(f"✗ Error generating/saving image: {exc}")
        print(f"✓ Using default blog cover: {DEFAULT_BLOG_IMAGE_URL}")
        return DEFAULT_BLOG_IMAGE_URL
