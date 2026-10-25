from __future__ import annotations

import json
import math
import os
import re
import tempfile
import textwrap
import uuid
from pathlib import Path, PurePosixPath

from PIL import Image, ImageDraw, ImageFont, ImageOps


BACKGROUND_NAME = re.compile(r"^template_background_(\d+)\.(png|jpe?g|webp)$", re.IGNORECASE)
POSTER_FIELDS = (
    "Title", "Author", "ISBN", "Genre", "Edition", "Publisher/Imprint",
    "Publication Year", "Page Count", "Book Details", "Format", "Condition", "Price", "Photo",
)


def title_for_poster(title: str, shortened: str | None = None) -> str:
    """Apply the poster title policy without changing the catalog value."""
    value = str(title or "").strip()
    if len(value) > 50:
        value = str(shortened or "").strip()
        if not value:
            raise ValueError("A shortened title is required for titles longer than 50 characters.")
        if len(value) > 50:
            raise ValueError("The shortened title must be 50 characters or fewer.")
    if len(value) > 25:
        lines = textwrap.wrap(value, width=25, break_long_words=True, break_on_hyphens=False)
        if len(lines) > 2:
            lines = [" ".join(lines[:-1]), lines[-1]]
        return "\n".join(lines)
    return value


def poster_price(price_minor: int | None) -> str:
    if price_minor is None or int(price_minor) <= 0:
        raise ValueError("This copy does not have a valid sale price.")
    return f"₱{int(price_minor) / 100:,.2f}"


def _font(size: int):
    candidates = (
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf",
        Path("/Library/Fonts/Arial.ttf"),
        Path("/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"),
    )
    for path in candidates:
        try:
            if path.is_file():
                return ImageFont.truetype(str(path), size=size)
        except OSError:
            continue
    try:
        return ImageFont.truetype("Arial.ttf", size=size)
    except OSError:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size=size)
        except OSError:
            return ImageFont.load_default()


class PosterService:
    """Poster template persistence, portable resources, and PNG rendering."""

    def __init__(self, db, paths):
        self.db = db
        self.paths = paths
        if self.paths.posters.is_symlink() or self.paths.poster_background_fallback.is_symlink():
            raise RuntimeError("Poster storage must use ordinary folders inside the portable application data.")
        self.paths.posters.resolve().relative_to(self.paths.root.resolve())
        self.paths.poster_background_fallback.resolve().relative_to(self.paths.data.resolve())
        self.paths.posters.mkdir(parents=True, exist_ok=True)
        self.paths.poster_background_fallback.mkdir(parents=True, exist_ok=True)

    def list_templates(self) -> list[dict]:
        with self.db.connect() as conn:
            rows = [dict(row) for row in conn.execute("SELECT id,name,background_ref,elements_json FROM poster_templates ORDER BY id")]
        for row in rows:
            try:
                row["elements"] = self._validate_elements(json.loads(row.pop("elements_json")))
            except (TypeError, ValueError, json.JSONDecodeError):
                row.pop("elements_json", None)
                row["elements"] = []
                row["invalid_elements"] = True
        return rows

    def get_template(self, template_id: int) -> dict | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT id,name,background_ref,elements_json FROM poster_templates WHERE id=?", (int(template_id),)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["elements"] = self._validate_elements(json.loads(result.pop("elements_json")))
        return result

    def _background_dirs(self):
        return (self.paths.root / "assets", self.paths.poster_background_fallback)

    def resolve_background(self, reference: str) -> Path:
        if not isinstance(reference, str) or "\\" in reference:
            raise ValueError("The saved background reference is invalid.")
        rel = PurePosixPath(reference)
        if rel.is_absolute() or ".." in rel.parts or not BACKGROUND_NAME.match(rel.name):
            raise ValueError("The saved background reference is invalid.")
        if rel.parts == ("assets", rel.name):
            raw_base = self.paths.root / "assets"
            raw_candidate = raw_base / rel.name
            if raw_base.is_symlink() or raw_candidate.is_symlink():
                raise ValueError("Linked poster background paths are not allowed.")
            candidate = raw_candidate.resolve()
            base = raw_base.resolve()
        elif rel.parts == ("data", "poster_backgrounds", rel.name):
            raw_base = self.paths.poster_background_fallback
            raw_candidate = raw_base / rel.name
            if raw_base.is_symlink() or raw_candidate.is_symlink():
                raise ValueError("Linked poster background paths are not allowed.")
            candidate = raw_candidate.resolve()
            base = raw_base.resolve()
        else:
            raise ValueError("The saved background reference is outside the managed poster folders.")
        candidate.relative_to(base)
        if not candidate.is_file():
            raise FileNotFoundError(f"Poster background is missing: {candidate.name}")
        return candidate

    def add_background(self, source: str | Path) -> tuple[str, Path]:
        source = Path(source)
        with Image.open(source) as original:
            if original.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Choose a PNG, JPEG, or WebP background image.")
            original.load()
            image = ImageOps.exif_transpose(original).copy()
            suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[original.format]
        destination_dir = None
        for directory in self._background_dirs():
            try:
                if directory.is_symlink():
                    continue
                directory.resolve().relative_to(self.paths.root.resolve())
                directory.mkdir(parents=True, exist_ok=True)
                fd, probe = tempfile.mkstemp(prefix=".poster-write-", dir=directory)
                os.close(fd)
                Path(probe).unlink()
                destination_dir = directory
                break
            except OSError:
                continue
        if destination_dir is None:
            raise OSError("BookLedger cannot write a poster background to the application assets or managed data folder.")
        used = set()
        for directory in self._background_dirs():
            if directory.is_dir():
                for file in directory.iterdir():
                    match = BACKGROUND_NAME.match(file.name)
                    if match:
                        used.add(int(match.group(1)))
        number = 1
        while number in used:
            number += 1
        image_format = {".png": "PNG", ".jpg": "JPEG", ".webp": "WEBP"}[suffix]
        while True:
            destination = destination_dir / f"template_background_{number}{suffix}"
            try:
                with destination.open("xb") as stream:
                    image.save(stream, format=image_format)
                break
            except FileExistsError:
                number += 1
            except Exception:
                destination.unlink(missing_ok=True)
                raise
        ref = f"assets/{destination.name}" if destination_dir == self.paths.root / "assets" else f"data/poster_backgrounds/{destination.name}"
        return ref, destination

    def save_template(self, background_ref: str, elements: list[dict]) -> dict:
        self.resolve_background(background_ref)
        elements = self._validate_elements(elements)
        with self.db.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO poster_templates(name,background_ref,elements_json) VALUES(?,?,?)",
                (f"__pending__{uuid.uuid4().hex}", background_ref, json.dumps(elements, ensure_ascii=False, separators=(",", ":"))),
            )
            template_id = int(cursor.lastrowid)
            name = f"Preset {template_id}"
            conn.execute(
                "UPDATE poster_templates SET name=? WHERE id=?",
                (name, template_id),
            )
        return self.get_template(template_id)

    @staticmethod
    def _validate_elements(elements):
        if not isinstance(elements, list):
            raise ValueError("Poster elements must be a list.")
        clean = []
        for element in elements:
            if not isinstance(element, dict) or element.get("field") not in POSTER_FIELDS:
                raise ValueError("A poster element has an unsupported field.")
            values = {}
            for name in ("x", "y", "w", "h"):
                try:
                    values[name] = float(element[name])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError("Poster element geometry is invalid.") from exc
                if not math.isfinite(values[name]):
                    raise ValueError("Poster element geometry must be finite.")
            if not (0 <= values["x"] < 1 and 0 <= values["y"] < 1 and 0 < values["w"] <= 1 and 0 < values["h"] <= 1):
                raise ValueError("Poster elements must fit inside the canvas.")
            if values["x"] + values["w"] > 1 or values["y"] + values["h"] > 1:
                raise ValueError("Poster elements must fit inside the canvas.")
            try:
                font_size = int(element.get("font_size", 28))
            except (TypeError, ValueError) as exc:
                raise ValueError("Poster font size is invalid.") from exc
            if not 8 <= font_size <= 160:
                raise ValueError("Poster font size must be between 8 and 160.")
            clean.append({
                "field": element["field"],
                "type": "image" if element["field"] == "Photo" else "text",
                **values,
                "font_family": "Arial",
                "font_size": font_size,
            })
        return clean

    def discard_template(self, template_id: int) -> str | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT background_ref FROM poster_templates WHERE id=?", (int(template_id),)).fetchone()
            if row is None:
                return None
            reference = row[0]
            conn.execute("DELETE FROM poster_templates WHERE id=?", (int(template_id),))
            referenced = conn.execute("SELECT 1 FROM poster_templates WHERE background_ref=? LIMIT 1", (reference,)).fetchone()
        if not referenced:
            try:
                path = self.resolve_background(reference)
                path.unlink(missing_ok=True)
            except (OSError, ValueError):
                pass
        return reference

    @staticmethod
    def _field_value(row: dict, field: str, shortened_title: str | None) -> str:
        values = {
            "Title": title_for_poster(row.get("title", ""), shortened_title),
            "Author": row.get("author"), "ISBN": row.get("isbn"), "Publisher/Imprint": row.get("publisher"),
            "Publication Year": row.get("publication_year"), "Edition": row.get("edition"),
            "Page Count": row.get("page_count"), "Format": row.get("format"),
            "Condition": row.get("condition"), "Genre": row.get("genre"),
            "Price": poster_price(row.get("price_minor")), "Book Details": row.get("book_details"),
        }
        return "" if values.get(field) is None else str(values.get(field, ""))

    def render(self, template: dict, copy_row: dict, *, shortened_title: str | None = None) -> Image.Image:
        background = self.resolve_background(template["background_ref"])
        with Image.open(background) as source:
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
        scale = min(4096 / max(image.size), max(1, 1080 / min(image.size)))
        size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        image = image.resize(size, Image.Resampling.LANCZOS) if size != image.size else image
        def wrap_to_width(value, font, limit, text_draw):
            lines = []
            for paragraph in str(value).splitlines() or [""]:
                words = paragraph.split()
                line = ""
                for word in words:
                    candidate = f"{line} {word}".strip()
                    if line and text_draw.textlength(candidate, font=font) > limit:
                        lines.append(line)
                        line = word
                    else:
                        line = candidate
                lines.append(line)
            return "\n".join(lines)

        for element in self._validate_elements(template.get("elements", [])):
            field = element.get("field")
            x = max(0, min(1, float(element.get("x", 0.1)))) * image.width
            y = max(0, min(1, float(element.get("y", 0.1)))) * image.height
            width = max(0.01, min(1, float(element.get("w", 0.35)))) * image.width
            height = max(0.01, min(1, float(element.get("h", 0.1)))) * image.height
            if field == "Photo":
                reference = copy_row.get("photo_path")
                photo_path = (self.paths.data / reference).resolve() if reference and not Path(reference).is_absolute() else Path(reference or "")
                try:
                    photo_path.relative_to(self.paths.data.resolve())
                    with Image.open(photo_path) as source:
                        photo = ImageOps.exif_transpose(source).convert("RGB")
                        photo.thumbnail((round(width), round(height)), Image.Resampling.LANCZOS)
                        image.paste(photo, (round(x), round(y)))
                except (OSError, ValueError):
                    raise FileNotFoundError("The selected copy photo is missing or unreadable.")
                continue
            text = self._field_value(copy_row, field, shortened_title)
            if not text:
                continue
            font_size = max(8, round(float(element.get("font_size", 28)) * image.width / max(1, template.get("preview_width", 600))))
            font = _font(font_size)
            text_layer = Image.new("RGBA", (max(1, round(width)), max(1, round(height))), (0, 0, 0, 0))
            text_draw = ImageDraw.Draw(text_layer)
            text = wrap_to_width(text, font, width, text_draw)
            text_draw.multiline_text((0, 0), text, font=font, fill=element.get("color", "#111111"), spacing=max(2, round(font_size * 0.18)), align="left")
            image.paste(text_layer, (round(x), round(y)), text_layer)
        return image

    def export(self, template: dict, copy_row: dict, *, shortened_title: str | None = None) -> Path:
        match = re.fullmatch(r"BL-(\d{6,})", str(copy_row.get("copy_code", "")), re.IGNORECASE)
        if not match or int(match.group(1)) != int(copy_row.get("copy_id", -1)):
            raise ValueError("The copy does not have a valid canonical Copy ID.")
        output = self.paths.posters / f"BL-{int(copy_row['copy_id']):06d}.png"
        self.paths.posters.mkdir(parents=True, exist_ok=True)
        rendered = self.render(template, copy_row, shortened_title=shortened_title)
        fd, temp = tempfile.mkstemp(prefix=f".{output.stem}-", suffix=".png", dir=output.parent)
        os.close(fd)
        try:
            rendered.save(temp, format="PNG", optimize=True)
            os.replace(temp, output)
        except Exception:
            Path(temp).unlink(missing_ok=True)
            raise
        return output
