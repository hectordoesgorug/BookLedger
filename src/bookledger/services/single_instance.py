from __future__ import annotations

import ctypes
import os
import time
from pathlib import Path
from ctypes import wintypes


ERROR_SHARING_VIOLATION = 32
ERROR_LOCK_VIOLATION = 33
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_ALWAYS = 4
FILE_ATTRIBUTE_HIDDEN = 0x2
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class LibraryAlreadyRunning(Exception):
    """Raised when another process already owns this library."""


class LibraryLockError(RuntimeError):
    """Raised when exclusive library ownership cannot be established."""


class LibraryInstanceLock:
    """Hold an exclusive Windows file handle for this portable library."""

    def __init__(self, library_root: str | Path):
        if os.name != "nt":
            raise LibraryLockError("BookLedger's single-instance lock requires Windows.")

        try:
            lock_path = Path(library_root).resolve() / ".bookledger-instance.lock"
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._kernel32.CreateFileW.argtypes = (
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.LPVOID,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            )
            self._kernel32.CreateFileW.restype = wintypes.HANDLE
            self._kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
            self._kernel32.CloseHandle.restype = wintypes.BOOL
            for attempt in range(5):
                ctypes.set_last_error(0)
                handle = self._kernel32.CreateFileW(
                    str(lock_path),
                    GENERIC_READ | GENERIC_WRITE,
                    0,
                    None,
                    OPEN_ALWAYS,
                    FILE_ATTRIBUTE_HIDDEN,
                    None,
                )
                error = ctypes.get_last_error()
                if handle and handle != INVALID_HANDLE_VALUE:
                    self._handle = handle
                    return
                if error not in (ERROR_SHARING_VIOLATION, ERROR_LOCK_VIOLATION):
                    raise LibraryLockError(f"Could not establish library ownership (Windows error {error}).")
                if attempt < 4:
                    time.sleep(0.05)
        except (OSError, AttributeError, RuntimeError, TypeError, UnicodeError, ValueError) as exc:
            raise LibraryLockError(f"Could not establish library ownership: {exc}") from exc

        raise LibraryAlreadyRunning

    def close(self) -> None:
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        if not self._kernel32.CloseHandle(handle):
            raise LibraryLockError(
                f"Could not release library ownership (Windows error {ctypes.get_last_error()})."
            )
