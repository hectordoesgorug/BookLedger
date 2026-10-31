from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from bookledger.services.google_books import GoogleBooksProvider
from bookledger.services.metadata_contract import MetadataProvider
from bookledger.services.archive_org import ArchiveOrgProvider
from bookledger.services.open_library import OpenLibraryProvider
from bookledger.services.booktopia import BooktopiaProvider
from bookledger.services.bigbook import BigbookProvider
from bookledger.services.hardcover import HardcoverProvider


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
        lambda _credential: OpenLibraryProvider(),
    ),
    ProviderDescriptor(
        "google_books", "Google Books", True,
        ("title", "author", "genre", "book_details", "publisher", "publication_year", "page_count"),
        lambda credential: GoogleBooksProvider(credential),
    ),
    ProviderDescriptor(
        "archive_org", "Archive.org", True,
        ("title", "author", "book_details", "publisher", "publication_year", "edition"),
        lambda _credential: ArchiveOrgProvider(),
    ),
    ProviderDescriptor(
        "booktopia", "Booktopia", True,
        ("title", "author", "book_details", "publisher", "publication_year", "edition", "page_count", "format"),
        lambda _credential: BooktopiaProvider(),
    ),
    ProviderDescriptor(
        "bigbook", "Bigbook", True,
        ("title", "author", "isbn", "book_details", "publication_year", "page_count"),
        lambda credential: BigbookProvider(credential),
    ),
    ProviderDescriptor(
        "hardcover", "Hardcover", True,
        ("title", "author", "isbn", "genre", "book_details", "publisher", "publication_year", "edition", "page_count"),
        lambda credential: HardcoverProvider(credential),
    ),
)

DEFAULT_PROVIDER_IDS = tuple(item.id for item in PROVIDER_REGISTRY if item.implemented)
PROVIDERS_BY_ID = {item.id: item for item in PROVIDER_REGISTRY}
PROVIDERS_BY_NAME = {item.name: item for item in PROVIDER_REGISTRY}


def build_providers(settings, google_books_api_key: str = "", *, credentials: dict[str, str] | None = None) -> tuple[MetadataProvider, ...]:
    """Construct implemented, enabled providers in the user's configured order."""
    provider_credentials = dict(credentials or {})
    # Keep the original positional Google Books argument compatible with callers.
    if google_books_api_key:
        provider_credentials.setdefault("google_books", google_books_api_key)
    active = []
    for provider_id in settings.ordered_enabled_ids():
        descriptor = PROVIDERS_BY_ID.get(provider_id)
        if descriptor and descriptor.implemented:
            active.append(descriptor.factory(provider_credentials.get(descriptor.id, "")))
    return tuple(active)
