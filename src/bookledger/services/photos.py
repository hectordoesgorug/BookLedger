from __future__ import annotations
from pathlib import Path
from uuid import uuid4
from PIL import Image, ImageOps
from bookledger.config import PHOTO_JPEG_QUALITY, PHOTO_MAX_EDGE

SUPPORTED_INPUTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


class PhotoService:
    def __init__(self, photo_dir: str | Path):
        self.photo_dir = Path(photo_dir)
        self.photo_dir.mkdir(parents=True, exist_ok=True)

    def import_and_compress(self, source: str | Path, *, copy_code: str | None = None) -> Path:
        source = Path(source)
        if source.suffix.lower() not in SUPPORTED_INPUTS:
            raise ValueError("Choose a JPG, PNG, WEBP, BMP, or TIFF image.")
        try:
            with Image.open(source) as original:
                image = ImageOps.exif_transpose(original).convert("RGB")
                image.thumbnail((PHOTO_MAX_EDGE, PHOTO_MAX_EDGE), Image.Resampling.LANCZOS)
                name = f"{copy_code or 'pending'}-{uuid4().hex[:12]}.jpg"
                target = self.photo_dir / name
                image.save(target, "JPEG", quality=PHOTO_JPEG_QUALITY, optimize=True, progressive=True)
        except Exception as exc:
            raise ValueError(f"The selected photo could not be processed: {exc}") from exc
        if not target.exists() or target.stat().st_size == 0:
            raise ValueError("The compressed photo could not be saved.")
        return target
