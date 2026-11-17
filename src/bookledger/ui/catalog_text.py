from __future__ import annotations

from collections.abc import Callable


def combined_title(title: str, subtitle: str | None = None) -> str:
    title = str(title or "").strip()
    subtitle = str(subtitle or "").strip()
    return f"{title}: {subtitle}" if subtitle else title


def catalog_display_title(title: str, subtitle: str | None = None) -> str:
    main_title = str(title or "").strip()
    combined = combined_title(main_title, subtitle)
    return combined if combined != main_title and len(combined) < 60 else main_title


def truncate_to_two_lines(text: str, width: int, measure: Callable[[str], int]) -> str:
    """Wrap display text to two measured lines and mark any omitted text."""
    if width <= 0 or not text.strip():
        return ""

    lines = []
    current = ""
    truncated = False
    for word in text.split():
        candidate = f"{current} {word}" if current else word
        if measure(candidate) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
            if len(lines) == 2:
                truncated = True
                break
        while measure(word) > width:
            split_at = len(word)
            while split_at > 1 and measure(word[:split_at]) > width:
                split_at -= 1
            if len(lines) == 1:
                current = word[:split_at]
                truncated = True
                break
            lines.append(word[:split_at])
            word = word[split_at:]
        if truncated:
            break
        current = word
    else:
        if current:
            lines.append(current)

    if truncated:
        if current:
            lines.append(current)
        lines = lines[:2]
        last = lines[-1]
        marker = "…"
        while last and measure(last + marker) > width:
            last = last[:-1].rstrip()
        lines[-1] = last + marker if measure(marker) <= width else last
    return "\n".join(lines)
