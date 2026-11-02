"""Case and accent insensitive name resolution."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Sequence
from typing import TypeVar

from .errors import AmbiguousNameError, InvalidInputError, NotFoundError

T = TypeVar("T")

_MAX_LISTED = 15


def normalize(text: str) -> str:
    """Lowercase, strip accents and collapse punctuation/whitespace."""
    decomposed = unicodedata.normalize("NFKD", text)
    no_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[\W_]+", " ", no_marks.casefold()).strip()


def find_matches(query: str, items: Sequence[T], name: Callable[[T], str]) -> list[T]:
    """Exact matches if any, otherwise every partial (substring) match."""
    needle = normalize(query)
    if not needle:
        return []
    exact = [it for it in items if normalize(name(it)) == needle]
    if exact:
        return exact
    return [it for it in items if needle in normalize(name(it))]


def resolve_by_name(
    query: str,
    items: Sequence[T],
    name: Callable[[T], str],
    kind: str,
    label: Callable[[T], str] | None = None,
) -> T:
    """Return the single item named ``query``.

    Exact match first; a partial match is accepted only if it is unique. Ambiguity raises
    ``AmbiguousNameError`` listing the candidates; no match raises ``NotFoundError``.
    """
    if not normalize(query):
        raise InvalidInputError(f"The {kind} name is empty.")
    show = label or name
    matches = find_matches(query, items, name)
    if len(matches) == 1:
        return matches[0]
    if matches:
        candidates = ", ".join(sorted(show(m) for m in matches)[:_MAX_LISTED])
        raise AmbiguousNameError(
            f"Several {kind}s match '{query}': {candidates}. Give a more precise name or an id."
        )
    available = ", ".join(sorted(show(it) for it in items)[:_MAX_LISTED]) or "none"
    raise NotFoundError(f"No {kind} matches '{query}'. Available: {available}.")
