"""Unit tests - mock payment gateway."""
from datetime import datetime

import pytest

from vsms.payment import charge, luhn_valid

NOW = datetime(2026, 10, 4)


def test_luhn():
    assert luhn_valid("4242424242424242")
    assert not luhn_valid("4242424242424241")


def test_approved_returns_reference_and_last4():
    r = charge("4242 4242 4242 4242", "12/29", "123", 1000, now=NOW)
    assert r.success and r.reference.startswith("PAY-") and r.last4 == "4242"


@pytest.mark.parametrize("card,exp,cvv,amt,msg", [
    ("1234", "12/29", "123", 10, "card number"),
    ("4242424242424242", "01/20", "123", 10, "expired"),
    ("4242424242424242", "13/29", "123", 10, "expired"),
    ("4242424242424242", "garbage", "123", 10, "expired"),
    ("4242424242424242", "12/29", "12", 10, "CVV"),
    ("4242424242424242", "12/29", "abc", 10, "CVV"),
    ("4242424242424242", "12/29", "123", 0, "amount"),
    ("4000000000000002", "12/29", "123", 10, "declined"),
])
def test_rejections(card, exp, cvv, amt, msg):
    r = charge(card, exp, cvv, amt, now=NOW)
    assert not r.success and msg.lower() in r.message.lower()


def test_expiry_current_month_is_valid():
    assert charge("4242424242424242", "10/26", "123", 10, now=NOW).success
