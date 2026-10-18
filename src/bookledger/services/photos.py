from __future__ import annotations

from pathlib import Path
from uuid import uuid4
import os

from PIL import Image, ImageOps

from bookledger.config import PHOTO_JPEG_QUALITY, PHOTO_MAX_EDGE

SUPPORTED_INPUTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


class PhotoService:
    """Stage, validate, and atomically install canonical per-copy JPEG photos."""

    def __init__(self, photo_dir: str | Path, trash_dir: str | Path | None = None):
        self.photo_dir = Path(photo_dir)
        self.data_dir = self.photo_dir.parent
        self.trash_dir = Path(trash_dir) if trash_dir else self.data_dir / "trash"
        self.staging_dir = self.photo_dir / ".staging"
        for folder in (self.photo_dir, self.trash_dir, self.staging_dir):
            folder.mkdir(parents=True, exist_ok=True)

    def import_and_compress(self, source: str | Path, *, copy_code: str | None = None) -> Path:
        """Create a validated temporary JPEG; canonical name is assigned after ID allocation."""
        source = Path(source)
        if source.suffix.lower() not in SUPPORTED_INPUTS:
            raise ValueError("Choose a JPG, PNG, WEBP, BMP, or TIFF image.")
        target = self.staging_dir / f"{uuid4().hex}.jpg"
        try:
            with Image.open(source) as original:
                original.load()
                image = ImageOps.exif_transpose(original).convert("RGB")
                image.thumbnail((PHOTO_MAX_EDGE, PHOTO_MAX_EDGE), Image.Resampling.LANCZOS)
                image.save(target, "JPEG", quality=PHOTO_JPEG_QUALITY, optimize=True, progressive=True)
            with Image.open(target) as check:
                check.verify()
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise ValueError(f"The selected photo could not be processed: {exc}") from exc
        if not target.is_file() or target.stat().st_size == 0:
            target.unlink(missing_ok=True)
            raise ValueError("The compressed photo could not be saved.")
        return target

    def canonical_path(self, copy_id: int) -> Path:
        return self.photo_dir / f"{int(copy_id)}.jpg"

    def install(self, copy_id: int, staged: str | Path) -> Path:
        target = self.canonical_path(copy_id)
        staged = Path(staged)
        if not staged.is_file():
            raise FileNotFoundError(f"Staged photo is missing: {staged}")
        if target.exists():
            raise FileExistsError(f"Canonical photo already exists for Copy ID {copy_id}: {target}")
        staged.replace(target)
        return target

    def replace(self, copy_id: int, staged: str | Path) -> Path:
        target = self.canonical_path(copy_id)
        staged = Path(staged)
        if not staged.is_file():
            raise FileNotFoundError(f"Staged photo is missing: {staged}")
        # The stage is complete before replace; Windows replace is atomic for a
        # same-volume target and leaves the prior image intact if it fails.
        os.replace(staged, target)
        return target

    def discard_staged(self, path: str | Path | None) -> None:
        if not path:
            return
        candidate = Path(path).resolve()
        try:
            candidate.relative_to(self.staging_dir.resolve())
        except ValueError:
            return
        candidate.unlink(missing_ok=True)
