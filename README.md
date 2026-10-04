# Vehicle Showroom Management System (VSMS)

A web application that lets customers browse vehicles, book test drives, buy online and view their history,
while administrators and staff manage inventory, pricing, customers, bookings, service records and reports.

Built for the **Software Engineering Lab** (Xavier Institute of Engineering, Mumbai). Every module traces back to the
lab experiments - SRS (Exp 2), function-point estimate (Exp 3), UML (Exp 4), DFD (Exp 5), RMMM (Exp 6),
SCM (Exp 7), white-box testing (Exp 8) and the Jira/Trello plan (Exp 9).

## Run it

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app run seed        # loads demo vehicles and users
python run.py               # http://127.0.0.1:5000
```

| Role | Email | Password |
|---|---|---|
| Administrator | admin@showroom.test | Admin@1234 |
| Sales staff | sales@showroom.test | Sales@1234 |
| Service staff | service@showroom.test | Service@1234 |
| Customer | customer@showroom.test | Customer@1234 |

Demo payment cards: `4242 4242 4242 4242` is approved, `4000 0000 0000 0002` is declined (any future expiry, any 3-digit CVV).

## Features (SRS section 4)

* **Registration & login** with validation, unique email, salted password hashing, role-based access
* **Vehicle search** by brand, model, category and price range, with live availability
* **Test drives**: book, reschedule, cancel; double-booking prevented; 60-minute slots inside showroom hours; e-mail confirmations
* **Purchase**: price = ex-showroom + configurable tax + handling; mock payment gateway; atomic inventory claim; invoice generated and e-mailed
* **History**: bookings, purchases and service records per customer
* **Admin**: vehicle CRUD with image upload, pricing, customers/staff, password reset, tax configuration, sales report with CSV export
* **Service staff**: create and update service records

## Tests

```bash
pytest                                  # 120 tests
pytest --cov=vsms --cov-report=term     # coverage (about 91%)
```

Unit, integration, system (end-to-end HTTP), white-box (branch/boundary), security, and non-functional
(performance + concurrent-purchase) tests. See `docs/TESTING.md`.

## Project layout

```
vsms/            application package (models, services = business rules, routes, templates, static)
tests/           pytest suite
docs/            traceability matrix, testing, SCM, RMMM, estimation, diagrams, screenshots
run.py           entry point
```

## Using MySQL (SRS 2.4)

SQLite is the zero-setup default. For MySQL: `pip install pymysql` and set
`DATABASE_URL=mysql+pymysql://user:pass@localhost/vsms`. The code uses SQLAlchemy only, but this repo has been
tested on SQLite only.

## Limitations (kept honest)

* The payment gateway and e-mail are **simulated** (SRS TBD-1). E-mails are stored in an outbox table; swap in SMTP inside `services.notify()`.
* Card numbers are validated and then discarded - only the last four digits are stored.
* No password-reset-by-email: an administrator issues a temporary password.
* Brute-force login throttling and HTTPS termination are deployment concerns not built in here.

## Publishing to GitHub

Create an empty repository on GitHub (no README), then from this folder:

```bash
git remote add origin https://github.com/<your-username>/vehicle-showroom-management-system.git
git push -u origin main develop --tags
git push origin --all          # also pushes the feature/* and docs/* branches
```

The full project report is in `docs/VSMS_Project_Report.docx`.
