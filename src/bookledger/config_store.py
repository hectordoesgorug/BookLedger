from __future__ import annotations

import copy
import json
import os
import sqlite3
import tempfile
import threading
from pathlib import Path

from bookledger.config import APPROVED_GENRES, DEFAULT_FORMATS


class ConfigurationError(ValueError):
    """A configuration document cannot be updated without risking user data."""


class AppConfigStore:
    """Atomic, coordinated access to BookLedger's root configuration document."""

    def __init__(self, canonical_path: str | Path, fallback_path: str | Path | None = None):
        self.canonical_path = Path(canonical_path)
        self.fallback_path = Path(fallback_path) if fallback_path else None
        self.active_path = self.canonical_path
        self.warning: str | None = None
        self.migration_warnings: tuple[str, ...] = ()
        self._write_blocked = False
        self._lock = threading.RLock()

    @staticmethod
    def _read(path: Path) -> dict | None:
        if not path.is_file():
            return None
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Could not read configuration at {path} ({type(exc).__name__}).") from exc
        if not isinstance(document, dict):
            raise ConfigurationError(f"Configuration at {path} must contain a JSON object.")
        return document

    @staticmethod
    def _merge_missing(base: dict, overlay: dict) -> dict:
        merged = copy.deepcopy(base)
        for key, value in overlay.items():
            if key not in merged:
                merged[key] = copy.deepcopy(value)
            elif isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = AppConfigStore._merge_missing(merged[key], value)
        return merged

    def load_document(self) -> dict:
        """Load the root document, using the existing profile file only as fallback."""
        with self._lock:
            self.warning = None
            self._write_blocked = False
            try:
                canonical = self._read(self.canonical_path)
            except ConfigurationError as root_error:
                fallback = None
                if self.fallback_path is not None:
                    try:
                        fallback = self._read(self.fallback_path)
                    except ConfigurationError:
                        fallback = None
                    if fallback is not None:
                        self.active_path = self.fallback_path
                        self.warning = f"Root configuration was preserved; using the existing fallback at {self.fallback_path}."
                        return copy.deepcopy(fallback)
                self.active_path = self.fallback_path or self.canonical_path
                self.warning = str(root_error)
                self._write_blocked = self.fallback_path is None or (
                    self.fallback_path.exists() and fallback is None
                )
                return {}

            if canonical is None:
                self.active_path = self.canonical_path
                try:
                    fallback = self._read(self.fallback_path) if self.fallback_path else None
                except ConfigurationError:
                    fallback = None
                return copy.deepcopy(fallback) if fallback is not None else {}

            self.active_path = self.canonical_path
            try:
                fallback = self._read(self.fallback_path) if self.fallback_path else None
            except ConfigurationError:
                fallback = None
            if fallback is None:
                return copy.deepcopy(canonical)
            fallback_marker = fallback.get("_bookledger_runtime")
            if isinstance(fallback_marker, dict) and fallback_marker.get("active_fallback") is True:
                self.active_path = self.fallback_path
                self.warning = f"Using the existing fallback configuration at {self.fallback_path}."
                return copy.deepcopy(fallback)
            return self._merge_missing(canonical, fallback)

    @staticmethod
    def _atomic_write(path: Path, document: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(document, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise

    def update_document(self, update) -> Path:
        """Apply a small update to the latest document, preserving unrelated keys."""
        with self._lock:
            current = self.load_document()
            if self._write_blocked:
                raise ConfigurationError("Configuration could not be read safely; the existing file was preserved and no changes were written.")
            target = self.active_path
            changed = update(copy.deepcopy(current))
            if not isinstance(changed, dict):
                raise ConfigurationError("Configuration update must produce a JSON object.")
            if changed == current:
                return target
            if target == self.fallback_path and target != self.canonical_path:
                changed = copy.deepcopy(changed)
                runtime = changed.setdefault("_bookledger_runtime", {})
                if not isinstance(runtime, dict):
                    raise ConfigurationError("Fallback configuration metadata is invalid.")
                runtime["active_fallback"] = True
            try:
                self._atomic_write(target, changed)
                written = self._read(target)
            except (OSError, ConfigurationError) as exc:
                if target == self.canonical_path and self.fallback_path is not None:
                    fallback = self._read(self.fallback_path) or {}
                    recovered = self._merge_missing(fallback, changed)
                    runtime = recovered.setdefault("_bookledger_runtime", {})
                    if not isinstance(runtime, dict):
                        raise ConfigurationError("Fallback configuration metadata is invalid.") from exc
                    runtime["active_fallback"] = True
                    try:
                        self._atomic_write(self.fallback_path, recovered)
                        written = self._read(self.fallback_path)
                        target = self.fallback_path
                        self.active_path = target
                        self.warning = f"Root configuration could not be written; using fallback at {target}."
                    except (OSError, ConfigurationError):
                        raise OSError("Could not safely save application configuration; existing files were preserved.") from exc
                else:
                    raise
            if written != changed and target == self.canonical_path:
                raise OSError("Configuration write verification failed; the previous settings were preserved.")
            self.active_path = target
            return target

    def get(self, path: tuple[str, ...], default=None):
        document = self.load_document()
        value = document
        for part in path:
            if not isinstance(value, dict) or part not in value:
                return copy.deepcopy(default)
            value = value[part]
        return copy.deepcopy(value)

    def set(self, path: tuple[str, ...], value) -> Path:
        if not path:
            raise ValueError("A configuration path is required.")

        def update(document):
            current = document
            for part in path[:-1]:
                child = current.get(part)
                if child is None:
                    child = {}
                    current[part] = child
                if not isinstance(child, dict):
                    raise ConfigurationError(f"Configuration section '{part}' is invalid and was preserved.")
                current = child
            current[path[-1]] = copy.deepcopy(value)
            return document

        return self.update_document(update)

    def remove(self, path: tuple[str, ...]) -> Path:
        if not path:
            raise ValueError("A configuration path is required.")

        def update(document):
            current = document
            for part in path[:-1]:
                current = current.get(part)
                if not isinstance(current, dict):
                    return document
            current.pop(path[-1], None)
            return document

        return self.update_document(update)

    @staticmethod
    def _valid_list(values, field: str) -> list[str]:
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise ConfigurationError(f"The configured {field} list is invalid and was preserved.")
        result = []
        seen = set()
        for raw in values:
            value = raw.strip()
            if value and value.casefold() not in seen:
                result.append(value)
                seen.add(value.casefold())
        return result

    @staticmethod
    def _read_legacy_list(conn, key: str, defaults: tuple[str, ...]) -> list[str]:
        row = conn.execute("SELECT value FROM app_meta WHERE key=?", (key,)).fetchone()
        if not row:
            return list(defaults)
        try:
            values = json.loads(row[0])
        except (ValueError, TypeError) as exc:
            raise ConfigurationError(f"Legacy {key} settings are malformed and were preserved.") from exc
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise ConfigurationError(f"Legacy {key} settings are invalid and were preserved.")
        return AppConfigStore._valid_list(values, key)

    @staticmethod
    def _append_assigned(values: list[str], assigned) -> tuple[list[str], bool]:
        result = list(values)
        seen = {value.casefold() for value in result}
        changed = False
        for raw in assigned:
            value = str(raw[0] or "").strip()
            if value and value.casefold() not in seen:
                result.append(value)
                seen.add(value.casefold())
                changed = True
        return result, changed

    @staticmethod
    def _legacy_google_key(path: Path) -> tuple[str | None, str | None, bool]:
        if not path.is_file():
            return None, None, False
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            return None, f"Legacy Google Books settings at {path} could not be read ({type(exc).__name__}); it was preserved.", False
        if not isinstance(document, dict):
            return None, f"Legacy Google Books settings at {path} were not an object; the file was preserved.", False
        value = document.get("api_key")
        if value is None:
            return "", None, bool(document)
        if not isinstance(value, str):
            return None, f"Legacy Google Books key at {path} was invalid; the file was preserved.", False
        return value, None, bool(set(document) - {"api_key"})

    def migrate_legacy_settings(
        self,
        db,
        legacy_google_path: str | Path | None = None,
        profile_google_path: str | Path | None = None,
    ) -> tuple[str, ...]:
        """Import prior settings once, preserving canonical values and inventory assignments."""
        warnings: list[str] = []
        legacy_google_path = Path(legacy_google_path) if legacy_google_path else None
        profile_google_path = Path(profile_google_path) if profile_google_path else None
        legacy_sources = [path for path in (legacy_google_path, profile_google_path) if path is not None]
        with self._lock:
            document = self.load_document()
            original = copy.deepcopy(document)
            migrations = document.setdefault("migration_state", {})
            if not isinstance(migrations, dict):
                self.migration_warnings = ("Configuration migration metadata is invalid; settings were left unchanged.",)
                return self.migration_warnings
            try:
                preferences = document.setdefault("preferences", {})
                if not isinstance(preferences, dict):
                    raise ConfigurationError("The preferences section is invalid and was preserved.")
                api_keys = document.setdefault("api_keys", {})
                if not isinstance(api_keys, dict):
                    raise ConfigurationError("The API key section is invalid and was preserved.")
                logging_section = document.setdefault("logging", {})
                if not isinstance(logging_section, dict):
                    raise ConfigurationError("The logging section is invalid and was preserved.")
                original_preferences = original.get("preferences")
                original_preferences = original_preferences if isinstance(original_preferences, dict) else {}

                with db.connect() as conn:
                    migration_complete = migrations.get("configuration_v1") is True
                    for field, meta_key, table, column, defaults in (
                        ("genres", "genre_options", "book_records", "genre", APPROVED_GENRES),
                        ("formats", "format_options", "copies", "format", DEFAULT_FORMATS),
                    ):
                        assigned = conn.execute(
                            f"SELECT DISTINCT trim({column}) FROM {table} WHERE trim({column})<>'' ORDER BY trim({column}) COLLATE NOCASE"
                        ).fetchall()
                        if field in preferences:
                            values = self._valid_list(preferences[field], field)
                        elif migration_complete:
                            values = list(defaults) if field != "locations" else []
                        else:
                            values = self._read_legacy_list(conn, meta_key, defaults)
                        values, added = self._append_assigned(values, assigned)
                        preferences[field] = values
                        if added and field in original_preferences:
                            warnings.append(f"Assigned historical {field} values were retained in configuration.")

                    assigned_locations = conn.execute(
                        "SELECT DISTINCT trim(location) FROM copies WHERE trim(location)<>'' ORDER BY trim(location) COLLATE NOCASE"
                    ).fetchall()
                    if "locations" in preferences:
                        locations = self._valid_list(preferences["locations"], "locations")
                    elif migration_complete:
                        locations = []
                    else:
                        locations = [row[0] for row in conn.execute("SELECT name FROM locations ORDER BY name COLLATE NOCASE")]
                    locations, added_locations = self._append_assigned(locations, assigned_locations)
                    preferences["locations"] = locations
                    if added_locations and "locations" in original_preferences:
                        warnings.append("Assigned historical Location values were retained in configuration.")

                    if "enabled" not in logging_section:
                        old_logging = conn.execute(
                            "SELECT value FROM app_meta WHERE key='diagnostic_logging_enabled'"
                        ).fetchone()
                        logging_section["enabled"] = bool(old_logging and old_logging[0] == "1")
                    elif not isinstance(logging_section["enabled"], bool):
                        raise ConfigurationError("The logging enabled setting is invalid and was preserved.")

                    migrations["configuration_v1"] = True
                    retire_legacy = False
                    if migrations.get("google_books_legacy_checked") is not True:
                        legacy_values = []
                        malformed_legacy = False
                        for source in legacy_sources:
                            value, warning, has_unrelated_settings = self._legacy_google_key(source)
                            if warning:
                                warnings.append(warning)
                                malformed_legacy = True
                            elif value is not None:
                                legacy_values.append((source, value, has_unrelated_settings))

                        if "google_books" in api_keys:
                            canonical_key = api_keys["google_books"]
                            if not isinstance(canonical_key, str):
                                raise ConfigurationError("The canonical Google Books API key setting is invalid and was preserved.")
                            if any(value != canonical_key for _path, value, _extras in legacy_values):
                                warnings.append("The canonical Google Books key took precedence over a different legacy key; the legacy copy was preserved but is inactive.")
                            retire_legacy = not malformed_legacy and not any(
                                value != canonical_key for _path, value, _extras in legacy_values
                            )
                            if any(extras for _path, _value, extras in legacy_values):
                                warnings.append("Unrecognized Google Books settings were preserved in the legacy file; the migrated key is canonical and the legacy file is inactive.")
                                retire_legacy = False
                            migrations["google_books_legacy_checked"] = True
                        elif legacy_values:
                            # The portable data file is the established first choice. A
                            # profile copy is considered only when it is the sole source.
                            selected_path, selected_key, _selected_extras = legacy_values[0]
                            api_keys["google_books"] = selected_key
                            conflicts = [value for path, value, _extras in legacy_values[1:] if value != selected_key]
                            if conflicts:
                                warnings.append("The portable Google Books setting took precedence over a different profile copy; the conflicting profile file was preserved but is inactive.")
                                retire_legacy = False
                            else:
                                retire_legacy = not malformed_legacy and selected_path == legacy_google_path and not _selected_extras
                            if any(extras for _path, _value, extras in legacy_values):
                                warnings.append("Unrecognized Google Books settings were preserved in the legacy file; the migrated key is canonical and the legacy file is inactive.")
                                retire_legacy = False
                            if not malformed_legacy:
                                migrations["google_books_legacy_checked"] = True
                        elif malformed_legacy:
                            # Retry a malformed source on a later launch; do not mark
                            # the credential migration complete while it may hold a key.
                            migrations.pop("google_books_legacy_checked", None)
                        else:
                            api_keys["google_books"] = ""
                            migrations["google_books_legacy_checked"] = True

                if document != original:
                    self.update_document(lambda _current: document)
                    written = self._read(self.active_path)
                    if written is not None:
                        written.pop("_bookledger_runtime", None)
                    if written != document:
                        raise OSError("Configuration migration could not be verified after writing.")

                if retire_legacy and self.active_path == self.canonical_path and legacy_google_path and legacy_google_path.is_file():
                    try:
                        # The verified root document and migration marker are now the
                        # only active source. Remove only the known legacy file.
                        legacy_google_path.unlink()
                    except OSError as exc:
                        warnings.append(f"The legacy Google Books file could not be retired ({type(exc).__name__}); the migration marker prevents it from being re-imported.")
                elif retire_legacy and legacy_google_path and legacy_google_path.is_file():
                    warnings.append("The Google Books legacy file was preserved because the root configuration is unavailable; it will be retried after configuration recovery.")
            except (ConfigurationError, sqlite3.Error, OSError) as exc:
                warnings.append(f"Configuration migration was incomplete: {exc}")

            self.migration_warnings = tuple(warnings)
            if warnings:
                self.warning = " ".join(warnings)
            return self.migration_warnings
