# StegoSecure — EC2 Deployment Guide (Local Storage Edition)

This document contains only the fresh Ubuntu EC2 deployment procedure for the `local_storage` branch. It is intentionally separate from `LOCAL_STORAGE_DOCUMENTATION.md`, which explains application architecture, encryption/decryption internals, backend functions and request workflows.

> **Fresh installation:** these steps create a new database and a new local storage directory. They do not migrate existing users, payments, gallery records or encrypted images. Do not run the schema import against a database containing data you need to preserve.

## 1. Create and connect to the EC2 instance

Create an Ubuntu EC2 instance, configure an SSH key pair, and connect:

```bash
ssh -i your-key.pem ubuntu@EC2_PUBLIC_IP
```

For direct testing, configure these inbound Security Group rules:

| Type | Port | Source |
|---|---:|---|
| SSH | 22 | Your IP only |
| Custom TCP | 5000 | Your IP only (temporary direct testing) |

Do **not** expose MySQL port `3306` publicly. Port `5000` is suitable for direct testing, not a recommended public production endpoint. For production, put the application behind HTTPS using a properly configured reverse proxy or load balancer and enable secure cookies.

## 2. Update Ubuntu and install system packages

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git python3 python3-pip python3-venv python3-dev build-essential pkg-config libmysqlclient-dev mysql-server
```

## 3. Clone the correct Git branch

```bash
cd ~
git clone --depth 1 -b local_storage https://github.com/nikhilkadam-lab/StegoSecure.git
cd ~/StegoSecure
```

Confirm the branch and files:

```bash
git branch --show-current
ls
```

The branch should be `local_storage`.

## 4. Create the Python virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip check
```

Expected final `pip check` output:

```text
No broken requirements found.
```

When reconnecting to the instance later, activate the environment again:

```bash
cd ~/StegoSecure
source venv/bin/activate
```

## 5. Start MySQL and create the application database/user

Enable and start MySQL:

```bash
sudo systemctl enable --now mysql
```

Open the local MySQL shell:

```bash
sudo mysql
```

Run the following SQL. Replace the placeholder with a strong password that you create. Do not reuse or publish this password:

```sql
CREATE DATABASE stego_secure
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

CREATE USER 'stego_user'@'localhost'
  IDENTIFIED BY 'YOUR_STRONG_DB_PASSWORD';

GRANT ALL PRIVILEGES ON stego_secure.* TO 'stego_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

The application connects to MySQL on the same EC2 instance using `localhost`; no public MySQL listener is required.

## 6. Import and verify the database schema

From the project root:

```bash
cd ~/StegoSecure
sudo mysql stego_secure < database/schema.sql
sudo mysql -D stego_secure -e "SHOW TABLES;"
sudo mysql -D stego_secure -e "SELECT * FROM system_settings;"
```

The schema should create these eight tables:

- `admins`
- `encryption_limits`
- `gallery`
- `payments`
- `plans`
- `site_settings`
- `system_settings`
- `users`

The initial default encryption limit is seeded as `5`.

## 7. Configure the environment file

Create `.env` from the committed example:

```bash
cd ~/StegoSecure
cp env.example .env
nano .env
```

Configure the values. Use your own generated Flask secret and the MySQL password from Step 5. Razorpay credentials can be left as placeholders until payment testing is needed.

```dotenv
SECRET_KEY=YOUR_RANDOM_SECRET_KEY
COOKIE_SECURE=false

DB_HOST=localhost
DB_PORT=3306
DB_NAME=stego_secure
DB_USER=stego_user
DB_PASSWORD=YOUR_STRONG_DB_PASSWORD

MAX_UPLOAD_MB=50
ENCRYPTED_STORAGE_DIR=private_storage
ENCRYPTED_IMAGE_RETENTION_DAYS=30

RAZORPAY_KEY_ID=YOUR_RAZORPAY_TEST_KEY_ID
RAZORPAY_KEY_SECRET=YOUR_RAZORPAY_TEST_KEY_SECRET
```

Generate a random Flask secret key from the activated virtual environment:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the generated value into `SECRET_KEY`. Keep `.env` private; never commit it to Git or paste its contents into chat. For direct HTTP testing, `COOKIE_SECURE=false` is required because the browser is not using HTTPS. Set `COOKIE_SECURE=true` only after HTTPS is correctly configured.

Save and exit nano with `Ctrl+O`, Enter, then `Ctrl+X`.

## 8. Test the MySQL connection from the application

With the virtual environment active:

```bash
cd ~/StegoSecure
python -c "from db import get_db_connection; conn = get_db_connection(); print('Database connection successful:', conn.is_connected()); conn.close()"
```

Expected output:

```text
Database connection successful: True
```

If this fails, check the `.env` database host, database name, username and password before continuing.

## 9. Create private storage directories

```bash
cd ~/StegoSecure
mkdir -p private_storage instance/banners
chmod 700 private_storage
ls -ld private_storage instance instance/banners
```

- `private_storage/` stores encrypted PNGs used by the user's gallery. It must remain private and must not be exposed as a public static directory.
- `instance/banners/` stores administrator-uploaded banner images.

The default banner image is included in the repository and is used as the fallback when no active administrator banner is configured.

## 10. Create the first administrator account

With the virtual environment active:

```bash
cd ~/StegoSecure
python create_admin.py
```

Follow the interactive prompts to set the administrator username, email and password. The password is stored as a hash; do not put it in source code or commit it.

## 11. Start the application

Run the application in the foreground, as used for this project:

```bash
cd ~/StegoSecure
source venv/bin/activate
python app.py
```

The current `app.py` entry point listens on `0.0.0.0:5000` with debug disabled. Keep this terminal open while testing. Stop the process with `Ctrl+C`. This guide does not configure a background service or a different application runner.

## 12. Open the application and administrator console

Replace `EC2_PUBLIC_IP` with the instance's public IPv4 address:

- User application: `http://EC2_PUBLIC_IP:5000/`
- Admin login: `http://EC2_PUBLIC_IP:5000/secure-console-x7k9/`
- Admin dashboard after login: `http://EC2_PUBLIC_IP:5000/secure-console-x7k9/dashboard`

The admin URL prefix is intentionally `/secure-console-x7k9`; it is not `/admin`.

If the page does not load, confirm that the application terminal shows it is running and the EC2 Security Group permits TCP `5000` from your current public IP.

## 13. Post-deployment verification checklist

- [ ] Register a new user and log in.
- [ ] Confirm the user's initial encryption credit allowance.
- [ ] Encrypt a text payload using QA mode and decrypt it.
- [ ] Encrypt a text payload using KEY mode and decrypt it with the same key.
- [ ] Encrypt a file payload and decrypt/download the original file.
- [ ] Confirm the encrypted result downloads as PNG.
- [ ] Confirm `/previous` lists the signed-in user's encrypted images.
- [ ] Download and delete a previous encrypted image.
- [ ] Confirm decryption does not consume an encryption credit.
- [ ] Update profile details and change the password.
- [ ] Log in to the admin console using the URLs above.
- [ ] Check dashboard and user management.
- [ ] Check credit plans and plan status.
- [ ] Check revenue and payment transaction views.
- [ ] Change the default encryption limit for newly created users.
- [ ] Upload, activate, deactivate and delete an admin banner.
- [ ] Confirm the bundled default banner is used when no admin banner is active.
- [ ] If payment testing is required, configure valid Razorpay test-mode credentials and complete a test transaction.

Razorpay testing requires valid test credentials and any provider-side account setup. Do not treat a payment as successful merely because the browser checkout opened; verify the transaction through the application's payment verification flow and database/admin views.

## 14. Important operational and security notes

1. **Keep `private_storage/` private.** Do not map it to Flask static files or a public web directory.
2. **Use HTTPS for public production traffic.** Enable `COOKIE_SECURE=true` only after TLS works.
3. **Protect `.env`.** It contains the Flask session secret, database password and payment credentials.
4. **Never expose MySQL port 3306 publicly.** The app and database are on the same EC2 instance in this deployment.
5. **Restrict SSH and temporary port 5000 access** to trusted source IPs.
6. **Back up both database and private files.** Gallery records alone are not enough to restore encrypted images; the database and matching `private_storage/` contents must be backed up consistently.
7. **Preserve encrypted PNGs exactly.** Do not resize, recompress, edit or convert them to JPEG. Lossy image processing can destroy the embedded LSB payload.
8. **Keep the original QA answer or secret key safe.** The application does not store the user's credential in the encrypted payload, so losing it prevents decryption.
9. **Retention setting:** `ENCRYPTED_IMAGE_RETENTION_DAYS` controls expiry metadata/filtering in the gallery workflow. The source snapshot does not establish a scheduled background cleanup job that physically deletes every expired file.
10. **This is a deployment guide, not a production hardening checklist.** Before public launch, configure HTTPS, a managed process/restart strategy if desired, monitoring, backups, OS updates, firewall restrictions and a documented recovery procedure.

## 15. Related documentation

- `docs/LOCAL_STORAGE_DOCUMENTATION.md` — architecture, file-by-file backend reference, cryptographic design, capacity formula, and exact encrypt/decrypt request sequences.
