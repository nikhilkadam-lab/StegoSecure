import re
from email_validator import EmailNotValidError, validate_email


def normalize_email(email):
    if not isinstance(email, str):
        raise ValueError("Please enter a valid email address.")

    try:
        result = validate_email(
            email.strip(),
            check_deliverability=False,
        )
        return result.normalized.lower()
    except EmailNotValidError:
        raise ValueError("Please enter a valid email address.")


def validate_username(username):
    if not isinstance(username, str):
        raise ValueError("Please enter your name.")

    username = " ".join(username.split())

    if not 2 <= len(username) <= 50:
        raise ValueError("Name must be between 2 and 50 characters.")

    if not all(char.isalpha() or char in " .'-" for char in username):
        raise ValueError("Name can contain letters, spaces, dots, hyphens, and apostrophes only.")

    if not any(char.isalpha() for char in username):
        raise ValueError("Please enter a valid name.")

    return username


def validate_password(password):
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise ValueError("Password must be between 8 and 128 characters.")

    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")

    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one number.")

    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("Password must contain at least one special character.")

    return password
