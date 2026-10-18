from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from bookledger.provider_registry import DEFAULT_PROVIDER_IDS, PROVIDERS_BY_ID


CONFIG_VERSION = 1


@dataclass
class ProviderSettings:
    order: list[str]
    enabled: dict[str, bool]

    @classmethod
    def defaults(cls) -> "ProviderSettings":
        return cls(list(DEFAULT_PROVIDER_IDS), {provider_id: True for provider_id in DEFAULT_PROVIDER_IDS})

    def ordered_enabled_ids(self) -> list[str]:
        return [provider_id for provider_id in self.order if self.enabled.get(provider_id, False)]

    @classmethod
    def from_document(cls, document: object) -> "ProviderSettings":
        defaults = cls.defaults()
        if not isinstance(document, dict):
            raise ValueError("Configuration root must be a JSON object")
        version = document.get("version", CONFIG_VERSION)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1 or version > CONFIG_VERSION:
            raise ValueError(f"Unsupported configuration version: {version!r}")
        providers = document.get("metadata_providers", {})
        if providers is None:
            providers = {}
        if not isinstance(providers, dict):
            raise ValueError("metadata_providers must be a JSON object")
        raw_order = providers.get("order", defaults.order)
        raw_enabled = providers.get("enabled", {})
        if not isinstance(raw_order, list) or not all(isinstance(item, str) for item in raw_order):
            raise ValueError("metadata_providers.order must be a list of provider IDs")
        if not isinstance(raw_enabled, dict) or not all(isinstance(k, str) and isinstance(v, bool) for k, v in raw_enabled.items()):
            raise ValueError("metadata_providers.enabled must map provider IDs to booleans")
        valid_ids = set(DEFAULT_PROVIDER_IDS)
        order = list(dict.fromkeys(item for item in raw_order if item in valid_ids))
        order.extend(item for item in defaults.order if item not in order)
        enabled = {provider_id: raw_enabled.get(provider_id, True) for provider_id in defaults.order}
        return cls(order, enabled)

    def to_document(self, existing: object = None) -> dict:
        document = dict(existing) if isinstance(existing, dict) else {}
        document["version"] = CONFIG_VERSION
        document["metadata_providers"] = {
            "order": [provider_id for provider_id in self.order if provider_id in PROVIDERS_BY_ID],
            "enabled": {provider_id: bool(self.enabled.get(provider_id, True)) for provider_id in DEFAULT_PROVIDER_IDS},
        }
        return document


class ProviderSettingsStore:
    """Versioned provider configuration with a per-user fallback for read-only roots."""

    def __init__(self, portable_path: Path, fallback_path: Path):
        self.portable_path = Path(portable_path)
        self.fallback_path = Path(fallback_path)
        self.warning: str | None = None
        self.active_path = self.portable_path

    def load(self) -> ProviderSettings:
        prior_warning = None
        for path in (self.portable_path, self.fallback_path):
            if not path.is_file():
                continue
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
                settings = ProviderSettings.from_document(document)
                self.active_path = path
                if path == self.fallback_path or prior_warning:
                    reason = f" The portable config could not be read: {prior_warning}" if prior_warning else ""
                    self.warning = f"Using per-user provider settings at {path}.{reason}"
                else:
                    self.warning = None
                return settings
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                prior_warning = f"{path}: {exc}; the file was preserved"
        if prior_warning:
            self.warning = f"{prior_warning}. Safe provider defaults are active."
            self.active_path = self.fallback_path
        return ProviderSettings.defaults()

    def save(self, settings: ProviderSettings) -> Path:
        path = self.active_path
        existing = {}
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(existing, dict):
                    raise ValueError("Configuration root must be a JSON object")
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                # Never replace a malformed settings file. A clean fallback keeps
                # the user's existing bytes available for recovery.
                path = self.fallback_path
                existing = {}
        try:
            self._atomic_write(path, settings.to_document(existing))
        except OSError:
            if path == self.fallback_path:
                raise
            path = self.fallback_path
            fallback_existing = {}
            if path.exists():
                try:
                    fallback_existing = json.loads(path.read_text(encoding="utf-8"))
                    if not isinstance(fallback_existing, dict):
                        fallback_existing = {}
                except (OSError, UnicodeError, json.JSONDecodeError):
                    # Preserve malformed fallback too; report rather than overwrite.
                    raise OSError(f"Could not safely save provider settings; malformed fallback config was preserved: {path}")
            self._atomic_write(path, settings.to_document(fallback_existing))
        self.active_path = path
        self.warning = None if path == self.portable_path else f"Provider settings are stored in the per-user fallback: {path}"
        return path

    @staticmethod
    def _atomic_write(path: Path, document: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(document, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        except Exception:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise
