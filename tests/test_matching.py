import pytest

from hue_bridge_mcp.errors import AmbiguousNameError, InvalidInputError, NotFoundError
from hue_bridge_mcp.matching import find_matches, normalize, resolve_by_name

NAMES = ["Salon Plafond", "Salon Lampadaire", "Lampe Café", "Chevet", "Bureau", "Bureau Haut"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Café", "cafe"),
        ("ÉNERGIE", "energie"),
        ("  Salon   Plafond ", "salon plafond"),
        ("Lampe-de_chevet", "lampe de chevet"),
        ("Straße", "strasse"),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("chevet", "Chevet"),  # case
        ("CHEVET", "Chevet"),
        ("lampe cafe", "Lampe Café"),  # accents
        ("lampe café", "Lampe Café"),
        ("plafond", "Salon Plafond"),  # unique partial match
        ("bureau", "Bureau"),  # exact wins over the longer "Bureau Haut"
    ],
)
def test_resolve_ok(query, expected):
    assert resolve_by_name(query, NAMES, str, "light") == expected


def test_partial_ambiguity_lists_candidates():
    with pytest.raises(AmbiguousNameError) as err:
        resolve_by_name("salon", NAMES, str, "light")
    message = str(err.value)
    assert "Salon Plafond" in message and "Salon Lampadaire" in message
    assert "Chevet" not in message


def test_duplicate_exact_names_are_ambiguous():
    with pytest.raises(AmbiguousNameError):
        resolve_by_name("relax", ["Relax", "relax"], str, "scene")


def test_not_found_lists_available():
    with pytest.raises(NotFoundError) as err:
        resolve_by_name("grenier", NAMES, str, "light")
    assert "Chevet" in str(err.value)


@pytest.mark.parametrize("query", ["", "   ", "---"])
def test_empty_query_rejected(query):
    with pytest.raises(InvalidInputError):
        resolve_by_name(query, NAMES, str, "light")


def test_find_matches_returns_all_partial():
    assert find_matches("salon", NAMES, str) == ["Salon Plafond", "Salon Lampadaire"]
    assert find_matches("", NAMES, str) == []
