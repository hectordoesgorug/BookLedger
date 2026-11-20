"""Deterministic, extractive shortening for book descriptions."""

import re


TARGET_CHARACTERS = 300
_NON_TERMINAL_ABBREVIATIONS = {
    "dr.", "mr.", "mrs.", "ms.", "prof.", "rev.", "jr.", "sr.",
    "e.g.", "i.e.", "u.s.", "u.k.", "u.n.", "jan.", "feb.", "mar.",
    "apr.", "jun.", "jul.", "aug.", "sep.", "sept.", "oct.", "nov.",
    "dec.",
}
_TOKEN_BEFORE_PERIOD = re.compile(r"(?:[A-Za-z]+\.)+$|(?:[A-Za-z]+\.)*[A-Za-z]+\.$")
_RETAIL_SECTION = re.compile(
    r"^\s*(?:about the author|industry reviews|shipping and returns|frequently asked questions|"
    r"you may also like|you might also like|readers also enjoyed|buy\b.{0,300}?\bfrom booktopia)\b",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    sentences: list[str] = []
    start = 0
    index = 0
    while index < len(normalized):
        if normalized[index] not in ".!?":
            index += 1
            continue
        punctuation_end = index + 1
        while punctuation_end < len(normalized) and normalized[punctuation_end] in ".!?":
            punctuation_end += 1
        while punctuation_end < len(normalized) and normalized[punctuation_end] in '\"\'”’)]}':
            punctuation_end += 1
        if (
            normalized[index] == "."
            and index > 0
            and punctuation_end < len(normalized)
            and normalized[index - 1].isdigit()
            and normalized[punctuation_end].isdigit()
        ):
            index = punctuation_end
            continue
        if punctuation_end < len(normalized) and normalized[punctuation_end].isspace():
            token_start = max(normalized.rfind(" ", start, index), normalized.rfind("\t", start, index)) + 1
            token = normalized[token_start:index + 1].casefold().lstrip("([{\"'“‘")
            abbreviation = _TOKEN_BEFORE_PERIOD.fullmatch(token)
            if abbreviation and token in _NON_TERMINAL_ABBREVIATIONS:
                index = punctuation_end + 1
                continue
            sentence = normalized[start:punctuation_end].strip()
            if sentence:
                sentences.append(sentence)
            start = punctuation_end
            while start < len(normalized) and normalized[start].isspace():
                start += 1
            index = start
            continue
        index = punctuation_end
    tail = normalized[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def shorten_description(text: str | None, *, target: int = TARGET_CHARACTERS) -> str | None:
    """Return a coherent sentence-prefix, or None when no useful shortening is safe."""
    if not isinstance(text, str) or len(text.strip()) <= target or target < 1:
        return None
    sentences = []
    for sentence in _sentences(text):
        if _RETAIL_SECTION.search(sentence):
            break
        sentences.append(sentence)
    selected: list[str] = []
    for sentence in sentences:
        candidate = " ".join((*selected, sentence))
        if len(candidate) > target:
            if not selected and len(sentence) <= target + 50:
                selected.append(sentence)
            break
        selected.append(sentence)
    shortened = " ".join(selected)
    if not shortened or len(shortened) >= len(text.strip()):
        return None
    if len(text.strip()) - len(shortened) < max(20, int(len(text.strip()) * 0.1)):
        return None
    return shortened
