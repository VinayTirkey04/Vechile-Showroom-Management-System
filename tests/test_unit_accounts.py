"""Unit tests - registration and login (REQ-REG-1..4), password security."""
import pytest

from vsms import services
from vsms.models import User
from vsms.services import BusinessError


def test_register_success_hashes_password(app):
    u = services.register_user("Asha Rao", "Asha@Example.com", "9876543210", "Strong123")
    assert u.email == "asha@example.com"            # stored lower-case
    assert u.password_hash != "Strong123"           # never plain text
    assert u.password_hash.startswith(("scrypt:", "pbkdf2:"))  # salted hash
    assert u.role == "customer"


def test_register_duplicate_email_rejected_case_insensitive(app, customer):
    with pytest.raises(BusinessError, match="already exists"):
        services.register_user("X", "CUST@test.com", "9876543210", "Passw0rd1")


@pytest.mark.parametrize("name,email,phone,pw", [
    ("", "a@b.com", "9876543210", "Passw0rd1"),          # empty name
    ("A", "not-an-email", "9876543210", "Passw0rd1"),     # bad email
    ("A", "a@b.com", "12345", "Passw0rd1"),               # short phone
    ("A", "a@b.com", "98765abcde", "Passw0rd1"),          # non-numeric phone
    ("A", "a@b.com", "9876543210", "short1"),             # short password
    ("A", "a@b.com", "9876543210", "allletters"),         # no digit
    ("A", "a@b.com", "9876543210", "12345678"),           # no letter
])
def test_register_validation_failures(app, name, email, phone, pw):
    with pytest.raises(BusinessError):
        services.register_user(name, email, phone, pw)
    assert User.query.count() == 0


def test_authenticate_valid_and_invalid(app, customer):
    assert services.authenticate("cust@test.com", "Passw0rd1").id == customer.id
    assert services.authenticate("CUST@test.com ", "Passw0rd1") is not None   # case/space tolerant
    assert services.authenticate("cust@test.com", "wrong") is None
    assert services.authenticate("nobody@test.com", "Passw0rd1") is None
    assert services.authenticate("", "") is None


def test_deactivated_account_cannot_login(app, customer, admin):
    services.set_account_active(admin, customer.id, False)
    assert services.authenticate("cust@test.com", "Passw0rd1") is None


def test_admin_cannot_deactivate_self(app, admin):
    with pytest.raises(BusinessError):
        services.set_account_active(admin, admin.id, False)


def test_change_password(app, customer):
    with pytest.raises(BusinessError, match="incorrect"):
        services.change_password(customer, "bad", "NewPass123")
    with pytest.raises(BusinessError):
        services.change_password(customer, "Passw0rd1", "weak")
    services.change_password(customer, "Passw0rd1", "NewPass123")
    assert services.authenticate("cust@test.com", "NewPass123")


def test_admin_reset_password_issues_working_temp_password(app, customer):
    temp = services.admin_reset_password(customer.id)
    assert services.authenticate("cust@test.com", temp)
    assert not services.authenticate("cust@test.com", "Passw0rd1")
