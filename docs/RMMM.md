# Risk mitigation, monitoring and management (Exp 6, Risk 204)

Risk 204 (60% probability, moderate impact): vehicle availability mismatch, poor data quality, wrong vehicle categories.

| Risk | Mitigation built into the system |
|---|---|
| Sold vehicle confirmed to a second customer | Atomic conditional `UPDATE ... WHERE status='available'` during purchase; pending test drives auto-cancelled; proven by the 4-thread race test |
| Inaccurate vehicle data | `clean_vehicle_form` validation (required fields, realistic year, positive integer price, unique vehicle number) and admin-only editing |
| Wrong categorisation | Category limited to Hatchback / Sedan / SUV / EV from a fixed list |
| Incorrect quotations | Single `calculate_price` function with unit tests; tax rate and handling charge configured centrally |
| Stock reconciliation across branches | Single source of truth in one table; per-category inventory summary on the admin dashboard |
| Monitoring | Sales and inventory reports, e-mail outbox as audit trail |
