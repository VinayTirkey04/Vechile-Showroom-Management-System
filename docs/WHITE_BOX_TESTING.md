# White-box testing notes

Cyclomatic complexity measured with `radon cc` (average **A, 3.05** across 100 blocks). The highest-complexity
functions were chosen for branch testing:

| Function | CC | Branches covered by `test_whitebox.py` |
|---|---|---|
| `payment.charge` | 14 | bad card number, expired, bad CVV, bad amount, decline-list card, success |
| `services.clean_vehicle_form` | 16 | each required-field error, invalid category, year not a number / unrealistic, price not a number / <= 0, duplicate number, edit-self exemption |
| `services.has_overlap` | 3 | 7 boundary cases (before, touching start, same, inside, touching end, containing), cancelled and other-vehicle bookings ignored |
| `services.delete_vehicle` | 6 | not found, sold, active booking, free vehicle |
| `payment._expiry_ok` | 3 | current month, past month, past year, month 00/13, malformed, None |

Overlap rule: two slots clash when `existing.start < new.end AND existing.end > new.start`; touching slots (10-11 and 11-12) are
allowed. The boundary test table proves both halves of that condition.
