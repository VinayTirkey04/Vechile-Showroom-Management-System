"""Unit test - Indian digit grouping used for rupee amounts."""
import pytest

from vsms import indian_grouping


@pytest.mark.parametrize("n,expected", [(0, "0"), (999, "999"), (1000, "1,000"), (12345, "12,345"),
                                         (100000, "1,00,000"), (1490000, "14,90,000"), (123456789, "12,34,56,789"), (-1500, "-1,500")])
def test_indian_grouping(n, expected):
    assert indian_grouping(n) == expected
