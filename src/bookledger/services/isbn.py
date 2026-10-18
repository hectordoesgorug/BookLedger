from __future__ import annotations
import re


def normalize_isbn(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"[\s-]", "", value).upper()
    return cleaned or None


def equivalent_isbn(value: str | None) -> str | None:
    """Return the ISBN-10/ISBN-13 alias when the ISBN has a safe equivalent."""
    isbn = normalize_isbn(value)
    if not isbn:
        return None
    valid, _message = isbn_check(isbn)
    if not valid:
        return None
    if len(isbn) == 13:
        if not isbn.startswith("978"):
            return None
        body = isbn[3:12]
        total = sum((10 - index) * int(digit) for index, digit in enumerate(body))
        check = (11 - total % 11) % 11
        return body + ("X" if check == 10 else str(check))
    if len(isbn) == 10:
        body = "978" + isbn[:9]
        total = sum(int(digit) * (1 if index % 2 == 0 else 3) for index, digit in enumerate(body))
        return body + str((10 - total % 10) % 10)
    return None


def isbn_check(value: str | None) -> tuple[bool, str]:
    """Validate ISBN-10 or ISBN-13 check digits. Empty input is valid/optional."""
    isbn = normalize_isbn(value)
    if not isbn:
        return True, "ISBN is optional."
    if len(isbn) == 10 and re.fullmatch(r"[0-9]{9}[0-9X]", isbn):
        total = sum((10 - i) * (10 if char == "X" else int(char)) for i, char in enumerate(isbn))
        return total % 11 == 0, "Valid ISBN-10." if total % 11 == 0 else "ISBN-10 check digit is invalid."
    if len(isbn) == 13 and isbn.isdigit():
        total = sum(int(char) * (1 if i % 2 == 0 else 3) for i, char in enumerate(isbn[:12]))
        expected = (10 - total % 10) % 10
        valid = expected == int(isbn[-1])
        return valid, "Valid ISBN-13." if valid else "ISBN-13 check digit is invalid."
    return False, "Enter an ISBN-10 or ISBN-13, or use the manual override."
