# Testing

Follows the SRS testing plan: unit -> integration -> system, plus white-box, security and non-functional tests.

| Level | File | Tests | Focus |
|---|---|---|---|
| Unit | `test_unit_accounts.py` | 14 | registration rules, hashing, login, password change/reset |
| Unit | `test_unit_search_pricing.py` | 12 | search filters, SQL-injection input, price maths, rounding |
| Unit | `test_unit_payment.py` | 11 | Luhn, expiry, CVV, decline |
| Unit | `test_unit_format.py` | 8 | Indian rupee digit grouping |
| Integration | `test_integration_booking.py` | 16 | booking + overlap + e-mail + cancel/reschedule |
| Integration | `test_integration_purchase.py` | 9 | payment -> inventory -> invoice -> notifications -> service records -> reports |
| System | `test_system_e2e.py` | 9 | full customer, admin and service journeys over HTTP |
| White-box | `test_whitebox.py` | 28 | every branch of overlap, form validation, expiry, delete rules |
| Security | `test_security.py` | 11 | RBAC, open redirect, XSS escaping, CSRF, headers, upload validation, data at rest |
| Non-functional | `test_nonfunctional.py` | 2 | 3,000-vehicle search time, 4 threads racing for one vehicle |

**Result: 120 passed, about 91% statement coverage.**

## Mutation sanity checks

To confirm the tests would actually catch bugs, three defects were injected into `services.py` one at a time:

| Injected defect | Caught by |
|---|---|
| overlap check ignores the end boundary | 4 tests incl. `test_has_overlap_boundaries[11-12-False]` |
| purchase skips the "still available" condition | `test_cannot_buy_same_vehicle_twice` |
| tax rounded down instead of half-up | `test_calculate_price_rounds_half_up` |

## Running

```bash
pytest -q
pytest --cov=vsms --cov-report=html     # open htmlcov/index.html
```
