from __future__ import annotations

import os

import pytest

from bookledger.services.credential_protection import (
    protect_secret,
    unprotect_secret,
)


pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="Desktop credentials use Windows DPAPI."
)


def test_protected_secret_round_trips_without_plaintext():
    secret = "mobile-token-" + "x" * 48

    protected = protect_secret(secret)

    assert protected.startswith("dpapi:v1:")
    assert secret not in protected
    assert unprotect_secret(protected) == secret


@pytest.mark.parametrize("value", ["", "not-dpapi", "dpapi:v1:not-base64!?"])
def test_invalid_protected_secret_is_rejected(value):
    with pytest.raises((ValueError, OSError)):
        unprotect_secret(value)


def test_empty_secret_is_rejected():
    with pytest.raises(ValueError):
        protect_secret("")
