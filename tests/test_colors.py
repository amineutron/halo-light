import pytest

from hue_bridge_mcp.colors import color_to_xy, kelvin_to_mirek, rgb_to_xy
from hue_bridge_mcp.errors import InvalidInputError


def test_primary_colors_land_in_expected_regions():
    rx, ry = rgb_to_xy(255, 0, 0)
    assert rx > 0.6 and ry < 0.4
    gx, gy = rgb_to_xy(0, 255, 0)
    assert gy > 0.5
    bx, by = rgb_to_xy(0, 0, 255)
    assert bx < 0.2 and by < 0.1


def test_white_is_near_the_white_point_and_black_falls_back():
    x, y = rgb_to_xy(255, 255, 255)
    assert abs(x - 0.3227) < 0.01 and abs(y - 0.329) < 0.01
    assert rgb_to_xy(0, 0, 0) == (0.3127, 0.3290)


@pytest.mark.parametrize("value", [-1, 256])
def test_rgb_range_checked(value):
    with pytest.raises(InvalidInputError):
        rgb_to_xy(value, 0, 0)


@pytest.mark.parametrize("name", ["rouge", "ROUGE", "Red", "#ff0000", "ff0000"])
def test_color_names_and_hex(name):
    assert color_to_xy(name) == rgb_to_xy(255, 0, 0)


def test_unknown_color_lists_known_ones():
    with pytest.raises(InvalidInputError) as err:
        color_to_xy("chartreuse-ish")
    assert "rouge" in str(err.value)


@pytest.mark.parametrize(("kelvin", "mirek"), [(2700, 370), (6500, 154), (2000, 500)])
def test_kelvin_to_mirek(kelvin, mirek):
    assert kelvin_to_mirek(kelvin) == mirek


@pytest.mark.parametrize("kelvin", [0, -5, 1000, 20000])
def test_kelvin_out_of_range(kelvin):
    with pytest.raises(InvalidInputError):
        kelvin_to_mirek(kelvin)
