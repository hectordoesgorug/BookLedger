from __future__ import annotations

APP_NAME = "BookLedger"
APP_VERSION = "0.1.0"

# The approved v1 genre vocabulary. Metadata providers may return other labels,
# but those labels must be explicitly recategorized before a copy can be saved.
APPROVED_GENRES = (
    "Science",
    "Social Science",
    "Politics",
    "Fiction",
    "Medical",
    "History",
    "Art",
    "Biography",
    "Humor",
    "Religion/New Age",
    "Children",
    "General Knowledge",
    "Miscellaneous",
)

# Initial values for the configurable Format list. Existing assignments are
# retained as compatibility entries when this list is first persisted.
DEFAULT_FORMATS = (
    "Paperback",
    "Hardcover",
    "Mass Market Paperback",
    "Board Book",
    "Other",
)

COPY_STATUSES = ("Available", "Not for Sale", "Listed", "Sold")
DEFAULT_LOCATION = "Not Specified"
CURRENCY = "PHP"
PHOTO_MAX_EDGE = 1600
PHOTO_JPEG_QUALITY = 82
