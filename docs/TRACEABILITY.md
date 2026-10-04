# Requirements traceability matrix

Every SRS requirement (Exp 2) maps to code and to at least one automated test.

| Requirement | Implemented in | Verified by |
|---|---|---|
| REQ-REG-1 register with name/email/phone/password | `services.register_user`, `routes/auth.register` | `test_unit_accounts::test_register_success_hashes_password`, `test_system_e2e::test_full_customer_journey` |
| REQ-REG-2 unique, well-formed email | `services.validate_registration` | `test_register_duplicate_email_rejected_case_insensitive`, `test_register_validation_failures` |
| REQ-REG-3 login with email + password | `services.authenticate` | `test_authenticate_valid_and_invalid` |
| REQ-REG-4 error on invalid credentials | `routes/auth.login` | `test_invalid_login_message` |
| REQ-SRCH-1 search by brand/model/price | `services.search_vehicles` | `test_unit_search_pricing.py` (8 tests) |
| REQ-SRCH-2 availability in results | `vehicles.html` badge | `test_search_available_only_excludes_sold` |
| REQ-SRCH-3 vehicle detail | `routes/customer.vehicle_detail` | `test_full_customer_journey` |
| REQ-TD-1 book test drive | `services.book_test_drive` | `test_book_success_creates_booking_and_email` |
| REQ-TD-2 view/reschedule/cancel | `reschedule_test_drive`, `cancel_test_drive` | `test_cancel_frees_the_slot`, `test_reschedule_*` |
| REQ-TD-3 e-mail on booking/cancel | `services.notify` | `test_book_success_...`, `test_cancel_frees_the_slot` |
| REQ-TD-4 no double booking | `services.has_overlap` | `test_double_booking_*`, `test_has_overlap_boundaries` |
| REQ-PUR-1 initiate purchase | `routes/customer.purchase` | `test_full_customer_journey` |
| REQ-PUR-2 total incl. tax/charges | `services.calculate_price` | `test_calculate_price_*` |
| REQ-PUR-3 payment gateway | `payment.charge` | `test_unit_payment.py` |
| REQ-PUR-4 status -> sold | `services.purchase_vehicle` | `test_purchase_marks_sold_...` |
| REQ-PUR-5 invoice e-mailed | `services.purchase_vehicle` | `test_purchase_marks_sold_...` |
| REQ-HIST-1/2 booking, purchase, service history | `routes/customer.bookings`, `history` | `test_service_staff_flow`, `test_full_customer_journey` |
| REQ-ADM-1/2 manage inventory and pricing | `routes/admin.vehicle_*`, `services.clean_vehicle_form` | `test_admin_journey_inventory_pricing_reports`, `test_clean_form_*` |
| REQ-ADM-3 manage customers | `routes/admin.customers` | `test_admin_user_management_actions` |
| REQ-ADM-4 only admins | `helpers.roles_required` | `test_customer_cannot_reach_staff_pages`, `test_sales_staff_limited_...` |
| REQ-SVC-1 invoice per purchase | `Invoice` model | `test_purchase_marks_sold_...` |
| REQ-SVC-2 service records | `services.create_service_record` | `test_service_records_lifecycle` |
| REQ-SVC-3 sales/service reports | `services.sales_report`, `service_report` | `test_reports_reflect_sales` |
| 5.1 search < 3 s | indexed columns | `test_search_returns_within_three_seconds_on_large_inventory` |
| 5.2 no double booking / accurate availability | conditional UPDATE claim | `test_two_customers_racing_for_one_vehicle_only_one_wins` |
| 5.3 authentication, RBAC, hashing, data protection | Flask-Login, CSRF, headers, `card_last4` only | `test_security.py` (11 tests) |
| 5.5 sold vehicles unavailable | `book_test_drive`, `purchase_vehicle` | `test_sold_vehicle_cannot_be_booked`, `test_cannot_buy_same_vehicle_twice` |
| DFD 1.3 new password, 1.4 tax update | `admin_reset_password`, `update_pricing_config` | `test_admin_reset_password_...`, `test_pricing_config_update_...` |

**Not implemented (out of scope, noted in the SRS as TBD):** real payment provider (TBD-1), peak-load targets (TBD-2),
data-retention policy (TBD-3), real SMTP delivery, 24x7 availability (a deployment property).
