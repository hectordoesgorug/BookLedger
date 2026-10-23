"""Portable lookup and rendering helpers for bundled BookLedger resources."""

from __future__ import annotations

import math
import hashlib
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageOps


_SVG_TOKEN = re.compile(r"[AaCcHhLlMmSsVvZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
_ARGUMENTS = {"a": 7, "c": 6, "h": 1, "l": 2, "m": 2, "s": 4, "v": 1}


def resource_path(*parts: str) -> Path:
    """Resolve a bundled resource without depending on the current directory."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    base = Path(frozen_root) if frozen_root else Path(__file__).resolve().parents[2]
    return base.joinpath(*parts)


def apply_application_icon(window) -> bool:
    """Apply the bundled Windows icon, while remaining safe on other platforms."""
    icon = resource_path("assets", "icon.ico")
    if not icon.is_file():
        return False
    try:
        window.iconbitmap(str(icon))
        try:
            window.iconbitmap(default=str(icon))
        except (AttributeError, TypeError):
            pass
        return True
    except Exception:
        return False


def resolve_managed_logo(data_dir: str | Path, reference) -> Path | None:
    """Resolve a config-stored logo reference only beneath portable data/assets."""
    if not isinstance(reference, str) or not reference or "\\" in reference:
        return None
    relative = Path(reference)
    if relative.is_absolute() or not relative.parts or relative.parts[0] != "assets" or ".." in relative.parts:
        return None
    data_root = Path(data_dir).resolve()
    candidate = (data_root / relative).resolve()
    try:
        candidate.relative_to((data_root / "assets").resolve())
    except ValueError:
        return None
    return candidate


def store_shop_logo(source_path: str | Path, assets_dir: str | Path) -> Path:
    """Normalize an accepted image into a compact, content-addressed portable PNG."""
    source_path = Path(source_path)
    assets_dir = Path(assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with Image.open(source_path) as opened:
            if opened.format not in {"PNG", "JPEG", "GIF", "BMP", "WEBP", "TIFF"}:
                raise ValueError("Choose a PNG, JPEG, GIF, BMP, WebP, or TIFF image.")
            opened.load()
            image = ImageOps.exif_transpose(opened)
            image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        descriptor, temporary_name = tempfile.mkstemp(prefix=".shop-logo-", suffix=".png", dir=assets_dir)
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        image.save(temporary_path, format="PNG", optimize=True)
        digest = hashlib.sha256(temporary_path.read_bytes()).hexdigest()[:20]
        destination = assets_dir / f"shop-logo-{digest}.png"
        if destination.exists():
            temporary_path.unlink()
        else:
            os.replace(temporary_path, destination)
        return destination
    except Exception:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise


def normalize_shop_url(value: str) -> str | None:
    """Accept only web URLs; assume HTTPS for a plain domain or path."""
    value = str(value or "").strip()
    if not value:
        return ""
    if any(ord(char) < 32 or char.isspace() for char in value) or "\\" in value:
        return None
    try:
        parsed = urlsplit(value)
        if not parsed.scheme:
            parsed = urlsplit(f"https://{value}")
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        _ = parsed.port  # Validate malformed or out-of-range ports.
        return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path, parsed.query, parsed.fragment))
    except ValueError:
        return None


def _arc_points(start, rx, ry, rotation, large_arc, sweep, end):
    x1, y1 = start
    x2, y2 = end
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0 or start == end:
        return [end]
    phi = math.radians(rotation % 360)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    xp = cos_phi * dx + sin_phi * dy
    yp = -sin_phi * dx + cos_phi * dy
    radius_scale = xp * xp / (rx * rx) + yp * yp / (ry * ry)
    if radius_scale > 1:
        factor = math.sqrt(radius_scale)
        rx, ry = rx * factor, ry * factor
    numerator = max(0.0, rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp)
    denominator = max(1e-12, rx * rx * yp * yp + ry * ry * xp * xp)
    direction = -1 if bool(large_arc) == bool(sweep) else 1
    factor = direction * math.sqrt(numerator / denominator)
    cxp = factor * rx * yp / ry
    cyp = factor * -ry * xp / rx
    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2
    theta = math.atan2((yp - cyp) / ry, (xp - cxp) / rx)
    delta = math.atan2(
        ((-xp - cxp) / rx) * ((yp - cyp) / ry) - ((-yp - cyp) / ry) * ((xp - cxp) / rx),
        ((xp - cxp) / rx) * ((-xp - cxp) / rx) + ((yp - cyp) / ry) * ((-yp - cyp) / ry),
    )
    if not sweep and delta > 0:
        delta -= math.tau
    elif sweep and delta < 0:
        delta += math.tau
    steps = max(4, min(96, int(abs(delta) * max(rx, ry) / 18) + 1))
    points = []
    for index in range(1, steps + 1):
        angle = theta + delta * index / steps
        points.append((
            cx + cos_phi * rx * math.cos(angle) - sin_phi * ry * math.sin(angle),
            cy + sin_phi * rx * math.cos(angle) + cos_phi * ry * math.sin(angle),
        ))
    points[-1] = end
    return points


def _svg_subpaths(data: str):
    tokens = _SVG_TOKEN.findall(data)
    subpaths = []
    points = []
    current = (0.0, 0.0)
    origin = current
    previous_command = ""
    previous_control = None
    command = None
    index = 0

    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1
            if command in "Zz":
                if points:
                    points.append(origin)
                    subpaths.append(points)
                    points = []
                current = origin
                previous_control = None
                previous_command = command
                command = None
                continue
        if command is None:
            raise ValueError("SVG path data has no active command")
        upper = command.upper()
        count = _ARGUMENTS.get(upper.lower())
        if count is None or index + count > len(tokens):
            raise ValueError("Unsupported or incomplete SVG path command")
        values = [float(token) for token in tokens[index:index + count]]
        index += count
        relative = command.islower()
        base = current

        def point(x, y):
            return (x + base[0], y + base[1]) if relative else (x, y)

        if upper == "M":
            current = point(values[0], values[1])
            if points:
                subpaths.append(points)
            points = [current]
            origin = current
            command = "l" if relative else "L"
        elif upper == "L":
            current = point(values[0], values[1])
            points.append(current)
        elif upper == "H":
            current = (base[0] + values[0], base[1]) if relative else (values[0], base[1])
            points.append(current)
        elif upper == "V":
            current = (base[0], base[1] + values[0]) if relative else (base[0], values[0])
            points.append(current)
        elif upper == "C":
            c1, c2, end = point(values[0], values[1]), point(values[2], values[3]), point(values[4], values[5])
            start = current
            for step in range(1, 13):
                t = step / 12
                u = 1 - t
                points.append((u**3 * start[0] + 3*u*u*t*c1[0] + 3*u*t*t*c2[0] + t**3*end[0],
                               u**3 * start[1] + 3*u*u*t*c1[1] + 3*u*t*t*c2[1] + t**3*end[1]))
            current, previous_control = end, c2
        elif upper == "S":
            c1 = (2 * base[0] - previous_control[0], 2 * base[1] - previous_control[1]) if previous_command.upper() in ("C", "S") and previous_control else base
            c2, end = point(values[0], values[1]), point(values[2], values[3])
            start = current
            for step in range(1, 13):
                t = step / 12
                u = 1 - t
                points.append((u**3 * start[0] + 3*u*u*t*c1[0] + 3*u*t*t*c2[0] + t**3*end[0],
                               u**3 * start[1] + 3*u*u*t*c1[1] + 3*u*t*t*c2[1] + t**3*end[1]))
            current, previous_control = end, c2
        elif upper == "A":
            end = point(values[5], values[6])
            points.extend(_arc_points(current, *values[:5], end))
            current, previous_control = end, None
        previous_command = upper
        if upper not in ("C", "S"):
            previous_control = None

    if points:
        subpaths.append(points)
    return [path for path in subpaths if len(path) > 2]


def render_svg_icon(path: str | Path, *, frame_size: int = 28, content_size: int = 20) -> Image.Image | None:
    """Rasterize the simple SVG path subset used by BookLedger navigation art."""
    try:
        root = ET.parse(path).getroot()
        view_box = [float(part) for part in root.attrib.get("viewBox", "0 0 1024 1024").replace(",", " ").split()]
        if len(view_box) != 4 or view_box[2] <= 0 or view_box[3] <= 0:
            return None
        scale = 4
        canvas_size = frame_size * scale
        scale_factor = min(content_size * scale / view_box[2], content_size * scale / view_box[3])
        x_offset = (canvas_size - view_box[2] * scale_factor) / 2 - view_box[0] * scale_factor
        y_offset = (canvas_size - view_box[3] * scale_factor) / 2 - view_box[1] * scale_factor
        result = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] != "path":
                continue
            fill = element.attrib.get("fill", "black")
            if fill == "none":
                continue
            color = ImageColor.getcolor(fill, "RGBA")
            rings = _svg_subpaths(element.attrib.get("d", ""))
            mask = Image.new("1", (canvas_size, canvas_size), 0)
            for ring in rings:
                ring_mask = Image.new("1", (canvas_size, canvas_size), 0)
                coords = [(round(x * scale_factor + x_offset), round(y * scale_factor + y_offset)) for x, y in ring]
                ImageDraw.Draw(ring_mask).polygon(coords, fill=1)
                mask = ImageChops.logical_xor(mask, ring_mask)
            layer = Image.new("RGBA", (canvas_size, canvas_size), color)
            layer.putalpha(mask.convert("L"))
            result.alpha_composite(layer)
        return result.resize((frame_size, frame_size), Image.Resampling.LANCZOS)
    except (OSError, ValueError, ET.ParseError, ZeroDivisionError, OverflowError):
        return None
