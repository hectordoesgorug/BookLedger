from __future__ import annotations

import time
import urllib.request
from typing import Callable, Iterable

from bookledger.services.metadata_contract import (
    MetadataProvider,
    MetadataResult,
    failure_kind as _failure_kind,
    normalize_provider_title,
)
from bookledger.services.google_books import GoogleBooksProvider
from bookledger.services.open_library import OpenLibraryProvider


def _provider_outcome(result: MetadataResult) -> str:
    """Return a short, user-facing status without exposing provider diagnostics."""
    if result.failure_kind == "unavailable":
        return "Product unavailable"
    if result.status == "Lookup failed":
        return {
            "timeout": "Timed out",
            "network": "Connection failed",
            "provider": "HTTP/provider error",
            "unexpected": "Unexpected response error",
        }.get(result.failure_kind, "Unexpected response error")
    if result.status == "No data" and result.failure_kind == "unverified":
        return "Results returned · ISBN not confirmed"
    if result.record_found is True and not result.values:
        return "Record found · supported metadata unavailable"
    if result.status == "No data":
        return "No matching record"
    if result.values:
        return "Metadata retrieved · some fields missing" if result.partial else "Metadata retrieved"
    return "Unexpected response error"


class MetadataLookupService:
    """Fill metadata from enabled providers in configured order."""

    def __init__(self, providers: Iterable[MetadataProvider] | None = None):
        if providers is None:
            from bookledger.provider_registry import build_providers
            from bookledger.provider_settings import ProviderSettings

            providers = build_providers(ProviderSettings.defaults())
        self.providers = tuple(providers)

    def lookup(
        self,
        isbn: str,
        *,
        on_status: Callable[[str], None] | None = None,
        on_provider_status: Callable[[str, str], None] | None = None,
    ) -> MetadataResult:
        started = time.monotonic()
        failures: list[MetadataResult] = []
        primary_failure: MetadataResult | None = None
        unverified_result: MetadataResult | None = None
        combined: dict = {}
        sources: list[str] = []
        any_record_found = False
        # Capabilities live in the registry. This lets the result distinguish a
        # supported field that remained empty from a field no enabled source can fill.
        from bookledger.provider_registry import PROVIDERS_BY_NAME
        all_supported = frozenset(
            field for descriptor in PROVIDERS_BY_NAME.values() for field in descriptor.supported_fields
            if field != "srp"
        )
        enabled_supported: set[str] = set()
        for provider in self.providers:
            descriptor = PROVIDERS_BY_NAME.get(provider.name)
            if descriptor:
                enabled_supported.update(descriptor.supported_fields)
            else:
                enabled_supported.update(all_supported)
        provider_statuses: dict[str, str] = {}
        provider_durations: dict[str, float] = {}

        def set_provider_status(name: str, status: str) -> None:
            provider_statuses[name] = status
            if on_provider_status:
                on_provider_status(name, status)

        for index, provider in enumerate(self.providers):
            descriptor = PROVIDERS_BY_NAME.get(provider.name)
            fields_for_provider = frozenset(descriptor.supported_fields) if descriptor else all_supported
            if not any(combined.get(key) in (None, "") for key in fields_for_provider):
                set_provider_status(provider.name, "Not needed (skipped)")
                continue
            if on_status:
                on_status(f"Searching ISBN: {provider.name}")
                on_status("Fetching Data…")
            set_provider_status(provider.name, f"Retrieving from {provider.name}…")
            provider_started = time.monotonic()
            try:
                result = provider.lookup(isbn)
            except Exception as exc:
                result = MetadataResult("Lookup failed", {}, provider.name, str(exc), _failure_kind(exc))
            provider_durations[provider.name] = max(
                result.duration_seconds or time.monotonic() - provider_started, 0.0
            )
            any_record_found = any_record_found or result.record_found is True
            values = {
                key: value for key, value in result.values.items()
                if value not in (None, "") and (key in fields_for_provider or key == "isbn")
            }
            normalized_values = dict(values)
            if "title" in normalized_values:
                normalized_values["title"] = normalize_provider_title(str(normalized_values["title"]))
            provider_partial = any(normalized_values.get(key) in (None, "") for key in fields_for_provider)
            set_provider_status(provider.name, _provider_outcome(
                MetadataResult(result.status, normalized_values, result.source, result.error, result.failure_kind,
                               result.record_found, partial=provider_partial)
            ))
            if "title" in values:
                values["title"] = normalize_provider_title(str(values["title"]))
            if values:
                added_value = False
                for key, value in values.items():
                    if combined.get(key) in (None, ""):
                        combined[key] = value
                        added_value = True
                if added_value and result.source:
                    sources.append(result.source)
            if result.status == "Lookup failed":
                failures.append(result)
                if index == 0:
                    primary_failure = result
            elif result.status == "No data" and result.failure_kind == "unverified":
                unverified_result = result

        if combined:
            missing = frozenset(field for field in enabled_supported if combined.get(field) in (None, ""))
            unsupported = all_supported - enabled_supported
            partial = bool(failures) or bool(missing)
            if primary_failure is not None and len(sources) == 1 and sources[0] != primary_failure.source:
                # A matching fallback result is a successful lookup even when the
                # primary provider was unavailable; retain that failure for diagnostics.
                return MetadataResult(
                    "Retrieved", combined, " + ".join(dict.fromkeys(sources)),
                    primary_failure.error, primary_failure.failure_kind,
                    provider_statuses=provider_statuses, partial=True,
                    supported_fields=frozenset(enabled_supported), missing_fields=missing,
                    unsupported_fields=unsupported, provider_durations=provider_durations,
                    duration_seconds=time.monotonic() - started,
                )
            if failures and len(sources) <= 1:
                failure = failures[0]
                return MetadataResult("Retrieved", combined, ", ".join(sources) or failure.source, failure.error, failure.failure_kind,
                                      provider_statuses=provider_statuses, partial=True,
                                      supported_fields=frozenset(enabled_supported), missing_fields=missing,
                                      unsupported_fields=unsupported, provider_durations=provider_durations,
                                      duration_seconds=time.monotonic() - started)
            return MetadataResult("Retrieved", combined, " + ".join(dict.fromkeys(sources)),
                                  provider_statuses=provider_statuses, partial=partial,
                                  supported_fields=frozenset(enabled_supported), missing_fields=missing,
                                  unsupported_fields=unsupported, provider_durations=provider_durations,
                                  duration_seconds=time.monotonic() - started)
        if failures:
            # The first provider is primary; its specific error is the most useful
            # explanation when the fallback also fails or returns no matching record.
            failure = failures[0]
            failure.provider_statuses = provider_statuses
            failure.supported_fields = frozenset(enabled_supported)
            failure.missing_fields = frozenset(enabled_supported)
            failure.unsupported_fields = all_supported - enabled_supported
            failure.provider_durations = provider_durations
            failure.duration_seconds = time.monotonic() - started
            return failure
        source = self.providers[-1].name if self.providers else None
        if unverified_result is not None:
            return MetadataResult(
                "No data", {}, unverified_result.source, unverified_result.error,
                unverified_result.failure_kind, record_found=False,
                provider_statuses=provider_statuses,
                supported_fields=frozenset(enabled_supported), missing_fields=frozenset(enabled_supported),
                unsupported_fields=all_supported - enabled_supported, provider_durations=provider_durations,
                duration_seconds=time.monotonic() - started,
            )
        return MetadataResult("No data", {}, source, record_found=any_record_found, provider_statuses=provider_statuses,
                              supported_fields=frozenset(enabled_supported), missing_fields=frozenset(enabled_supported),
                              unsupported_fields=all_supported - enabled_supported, provider_durations=provider_durations,
                              duration_seconds=time.monotonic() - started)
