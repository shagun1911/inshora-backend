import os


def cloudinary_configured() -> bool:
    if os.getenv("CLOUDINARY_URL"):
        return True
    return all(
        [
            os.getenv("CLOUDINARY_CLOUD_NAME"),
            os.getenv("CLOUDINARY_API_KEY"),
            os.getenv("CLOUDINARY_API_SECRET"),
        ]
    )


def configure_cloudinary() -> None:
    import cloudinary

    if os.getenv("CLOUDINARY_URL"):
        cloudinary.config()
        return

    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    )
