"""Mock payment gateway (SRS TBD-1: provider not finalised).

Behaves like a real gateway client: validates the card with the Luhn check,
checks expiry/CVV and returns an approval reference or a decline. Full card
numbers are never persisted - callers only keep the last four digits.

Test cards:  4242424242424242 -> approved    4000000000000002 -> declined
"""
import secrets
from dataclasses import dataclass
from datetime import datetime

DECLINE_CARDS = {"4000000000000002"}


@dataclass
class PaymentResult:
    success: bool
    reference: str = ""
    message: str = ""
    last4: str = ""


def luhn_valid(number: str) -> bool:
    digits = [int(c) for c in number]
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _expiry_ok(expiry: str, now: datetime) -> bool:
    try:
        month_s, year_s = expiry.split("/")
        month, year = int(month_s), 2000 + int(year_s)
    except (ValueError, AttributeError):
        return False
    if not 1 <= month <= 12:
        return False
    return (year, month) >= (now.year, now.month)


def charge(card_number: str, expiry: str, cvv: str, amount: int, now: datetime | None = None) -> PaymentResult:
    now = now or datetime.now()
    card = "".join(ch for ch in (card_number or "") if ch.isdigit())
    if not 13 <= len(card) <= 19 or not luhn_valid(card):
        return PaymentResult(False, message="Invalid card number.")
    if not _expiry_ok(expiry or "", now):
        return PaymentResult(False, message="Card expired or expiry format invalid (use MM/YY).")
    if not (cvv or "").isdigit() or len(cvv) not in (3, 4):
        return PaymentResult(False, message="Invalid CVV.")
    if amount <= 0:
        return PaymentResult(False, message="Invalid amount.")
    if card in DECLINE_CARDS:
        return PaymentResult(False, message="Payment declined by the issuing bank.")
    return PaymentResult(True, reference="PAY-" + secrets.token_hex(6).upper(),
                         message="Approved", last4=card[-4:])
