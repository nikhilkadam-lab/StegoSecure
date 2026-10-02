import sys
from pathlib import Path
import getpass

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app import create_app
from app.extensions import db
from app.models import Admin
from app.utils import hash_password, normalize_email, validate_password


def main():
    app = create_app()

    with app.app_context():
        name = input("Admin name: ").strip()
        email_input = input("Admin email: ")
        password = getpass.getpass("Admin password: ")
        password_confirm = getpass.getpass("Confirm password: ")

        if not name:
            print("Error: Admin name is required.")
            return

        email = normalize_email(email_input)

        if email is None:
            print("Error: Enter a valid email address.")
            return

        password_valid, password_error = validate_password(password)

        if not password_valid:
            print(f"Error: {password_error}")
            return

        if password != password_confirm:
            print("Error: Passwords do not match.")
            return

        existing_admin = db.session.execute(
            db.select(Admin).filter_by(email=email)
        ).scalar_one_or_none()

        if existing_admin is not None:
            print("Error: An admin with this email already exists.")
            return

        admin = Admin(
            name=name,
            email=email,
            password_hash=hash_password(password),
            is_active=True,
        )

        db.session.add(admin)
        db.session.commit()

        print(f"Admin created successfully: {admin.email}")


if __name__ == "__main__":
    main()