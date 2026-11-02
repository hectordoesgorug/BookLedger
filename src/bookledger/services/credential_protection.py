from __future__ import annotations

import base64
import ctypes
import os
from ctypes import wintypes


_PREFIX = "dpapi:v1:"


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _blob(value: bytes):
    buffer = ctypes.create_string_buffer(value)
    blob = _DataBlob(
        len(value),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buffer


def _protect(value: bytes, *, decrypt: bool) -> bytes:
    if os.name != "nt":
        raise OSError("Windows Data Protection is available only on Windows.")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    source, source_buffer = _blob(value)
    target = _DataBlob()
    flags = 0x1  # CRYPTPROTECT_UI_FORBIDDEN
    if decrypt:
        succeeded = crypt32.CryptUnprotectData(
            ctypes.byref(source),
            None,
            None,
            None,
            None,
            flags,
            ctypes.byref(target),
        )
    else:
        succeeded = crypt32.CryptProtectData(
            ctypes.byref(source),
            "BookLedger mobile pairing token",
            None,
            None,
            None,
            flags,
            ctypes.byref(target),
        )
    if not succeeded:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree(target.pbData)
        del source_buffer


def protect_secret(secret: str) -> str:
    if not isinstance(secret, str) or not secret:
        raise ValueError("A non-empty secret is required.")
    protected = _protect(secret.encode("utf-8"), decrypt=False)
    return _PREFIX + base64.b64encode(protected).decode("ascii")


def unprotect_secret(value: str) -> str:
    if not isinstance(value, str) or not value.startswith(_PREFIX):
        raise ValueError("The stored credential has an unsupported format.")
    try:
        protected = base64.b64decode(value[len(_PREFIX) :], validate=True)
        secret = _protect(protected, decrypt=True).decode("utf-8")
    except (ValueError, UnicodeError) as exc:
        raise ValueError("The stored credential could not be decrypted.") from exc
    if not secret:
        raise ValueError("The stored credential is empty.")
    return secret
