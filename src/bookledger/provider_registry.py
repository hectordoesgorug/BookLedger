from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from bookledger.services.metadata import GoogleBooksProvider, MetadataProvider, OpenLibraryProvider
from bookledger.services.booktopia import BooktopiaProvider


@dataclass(frozen=True)
class ProviderDescriptor:
    id: str
    name: str
    implemented: bool
    supported_fields: tuple[str, ...]
    factory: Callable[[str], MetadataProvider]


PROVIDER_REGISTRY = (
    ProviderDescriptor(
        "open_library", "Open Library", True,
        ("title", "author", "genre", "publisher", "publication_year", "edition", "page_count"),
        lambda _api_key: OpenLibraryProvider(),
    ),
    ProviderDescriptor(
        "google_books", "Google Books", True,
        ("title", "author", "genre", "book_details", "publisher", "publication_year", "page_count"),
        lambda api_key: GoogleBooksProvider(api_key),
    ),
    ProviderDescriptor(
        "booktopia", "Booktopia", True,
        ("title", "author", "book_details", "publisher", "publication_year", "edition", "page_count", "format"),
        lambda _api_key: BooktopiaProvider(),
    ),
)

DEFAULT_PROVIDER_IDS = tuple(item.id for item in PROVIDER_REGISTRY if item.implemented)
PROVIDERS_BY_ID = {item.id: item for item in PROVIDER_REGISTRY}
PROVIDERS_BY_NAME = {item.name: item for item in PROVIDER_REGISTRY}


def build_providers(settings, google_books_api_key: str = "") -> tuple[MetadataProvider, ...]:
    """Construct implemented, enabled providers in the user's configured order."""
    active = []
    for provider_id in settings.ordered_enabled_ids():
        descriptor = PROVIDERS_BY_ID.get(provider_id)
        if descriptor and descriptor.implemented:
            active.append(descriptor.factory(google_books_api_key))
    return tuple(active)
