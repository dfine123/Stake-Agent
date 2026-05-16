"""Vibe seed generator.

Turns the user's vibe text + lucky numbers into a deterministic hex seed string
that gets pushed to Stake's `changeClientSeed` mutation, so the user's vibe is
provably mixed into every roll's RNG. Same vibe → same seed every time.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

# Stake's client seed field length is undocumented. SHA-256 hex is 64 chars.
# On the first live `set_client_seed` call, verify the full 64-char hex is
# accepted; if Stake rejects it, drop this to 32 and re-test.
SEED_LENGTH = 64


def generate_seed(text: str, lucky_numbers: Iterable[int]) -> str:
    """Return a deterministic hex seed derived from vibe inputs.

    Format hashed: ``f"{text}:{n1,n2,n3}"`` — order-sensitive, exact match required
    for reproducibility. Empty text and empty numbers are both fine.
    """
    numbers_part = ",".join(str(n) for n in lucky_numbers)
    payload = f"{text}:{numbers_part}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return digest[:SEED_LENGTH]
