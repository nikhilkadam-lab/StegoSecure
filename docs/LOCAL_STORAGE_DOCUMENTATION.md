# StegoSecure --- Local Storage Edition

## Project Architecture, Backend Reference, Security Model and Complete Workflows

> **Documentation scope:** This guide describes the `local_storage`
> branch represented by the supplied `StegoSecure-local_storage.zip`
> source snapshot. It is written for developers who want to understand,
> run, maintain, or extend this version.
>
> **Storage model:** MySQL stores structured application data. Encrypted
> output PNG files are stored on the server's local filesystem under
> `private_storage/`. This document does not describe an
> S3/object-storage edition.

------------------------------------------------------------------------

## 1. Project at a glance

StegoSecure is a Flask web application that combines **cryptographic
encryption** with **image steganography**.

A user can hide either text or a file inside a cover image. The
application first encrypts the secret data, packages the ciphertext and
the metadata needed for decryption, then embeds that package into the
least-significant bits (LSBs) of the cover image's RGB channels. The
resulting PNG looks like an ordinary image but carries a hidden
encrypted payload.

StegoSecure supports two ways to protect the encrypted payload:

-   **Security Question (QA):** the user chooses or enters a question
    and supplies an answer. The normalized answer is used as the input
    to a password-based key derivation function.
-   **Secret Key (KEY):** the browser-generated URL-safe Base64 key is
    decoded and used as the key-derivation input. The user must preserve
    this key to decrypt later.

The application also includes user accounts, encryption credits, a
previous-encryptions gallery, Razorpay credit purchases, user profile
management, and a separate administrator console.

### Main capabilities

-   User registration, login and logout
-   User dashboard and profile
-   Username and password changes
-   Text encryption and decryption
-   File encryption and decryption
-   Security-question and secret-key authentication modes
-   Cover-image validation and capacity calculation
-   PNG output with embedded encrypted payload
-   Private local storage of generated encrypted PNGs
-   Previous encrypted-image listing, preview, download and deletion
-   Retention-based gallery visibility
-   Encryption credit balance and atomic credit consumption
-   Credit plans and Razorpay order/payment verification
-   Admin dashboard and user management
-   Admin credit-plan management, including popular-plan selection
-   Admin revenue summary and transaction browsing
-   Admin system settings for default credits
-   Admin banner upload, activation, deactivation, preview and deletion
-   Configurable site banner with default-banner fallback

------------------------------------------------------------------------

## 2. Technology stack

  --------------------------------------------------------------------------
  Area                    Technology                 Responsibility
  ----------------------- -------------------------- -----------------------
  Web framework           Flask 3                    HTTP routes, sessions,
                                                     templates and
                                                     application setup

  Templates               Jinja2 / HTML              Server-rendered user
                                                     and admin pages

  Front-end behavior      JavaScript / CSS           Form behavior, capacity
                                                     display, previews and
                                                     dynamic admin screens

  Database                MySQL                      Users, admins, plans,
                                                     credits, gallery
                                                     metadata, payments and
                                                     settings

  Database driver         `mysql-connector-python`   Python-to-MySQL
                                                     connections

  Image processing        Pillow                     Decode, validate,
                                                     convert and write
                                                     images

  Pixel processing        NumPy                      Efficient RGB channel
                                                     and bit-array
                                                     operations

  Encryption              `cryptography` Fernet      Authenticated symmetric
                                                     encryption

  Key derivation          PBKDF2-HMAC-SHA256         Derive a Fernet key
                                                     from a QA answer or
                                                     secret key plus salt

  Password hashing        `argon2-cffi`              Hash account and
                                                     administrator passwords

  Request protection      Flask-WTF CSRFProtect      CSRF protection for
                                                     form submissions

  Configuration           python-dotenv              Load environment values
                                                     from `.env`

  Payment                 Razorpay Python SDK        Create orders and
                                                     verify payment
                                                     signatures

  Validation              email-validator / Werkzeug Email normalization and
                                                     safe filenames

  Source control          Git / GitHub               Version control and
                                                     collaboration
  --------------------------------------------------------------------------

Exact pinned Python dependencies are in `requirements.txt`.

------------------------------------------------------------------------

## 3. Repository structure

``` text
StegoSecure/
├── app.py
├── config.py
├── db.py
├── create_admin.py
├── requirements.txt
├── env.example
├── .gitignore
├── StegoSecure-default-Banner.png
├── SteogSecure_logo.png
│
├── admin/
│   ├── __init__.py
│   ├── admin_auth.py
│   ├── admin_routes.py
│   ├── dashboard_service.py
│   ├── user_service.py
│   ├── plan_service.py
│   ├── revenue_service.py
│   └── settings_service.py
│
├── database/
│   └── schema.sql
│
├── routes/
│   ├── __init__.py
│   ├── auth_routes.py
│   └── payment_routes.py
│
├── services/
│   ├── __init__.py
│   ├── auth_service.py
│   ├── credit_service.py
│   ├── encryption_service.py
│   ├── gallery_service.py
│   ├── payment_service.py
│   ├── site_service.py
│   ├── steganography_service.py
│   └── storage_service.py
│
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── profile.html
│   ├── credits.html
│   ├── decryption.html
│   ├── previous.html
│   └── admin/
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html
│       ├── users.html
│       ├── credit_plans.html
│       ├── revenue.html
│       └── settings.html
│
└── utils/
    └── validators.py
```

### Runtime-created directories

These directories are created or used at runtime and are not source-code
assets:

``` text
private_storage/       # Private generated encrypted PNGs
instance/
└── banners/           # Administrator-uploaded banner images
venv/                  # Python virtual environment
.env                   # Local secrets and configuration
```

`private_storage/`, `instance/`, `.env`, and the virtual environment
must not be committed. The `.gitignore` file excludes these
runtime/private locations.

------------------------------------------------------------------------

## 4. Architecture and request flow

The project separates HTTP handling from reusable business logic.

``` text
Browser
  |
  v
Flask route (app.py, routes/, admin/)
  |
  +---- Authentication / session checks
  |
  +---- Service layer (services/, admin/*_service.py)
  |        |
  |        +---- Cryptography and steganography
  |        +---- Validation and file storage
  |        +---- Credits, gallery and payments
  |        +---- Admin business rules
  |
  +---- db.py ---- MySQL
  |
  +---- templates/ ---- HTML response
  |
  +---- private_storage/ and instance/banners/ ---- local files
```

### Responsibilities by layer

1.  **Routes** accept HTTP requests, read form/query data, check session
    state, call services and return HTML, JSON, redirects or downloads.
2.  **Services** implement reusable rules such as encryption, image
    embedding, credit consumption, payment verification and gallery
    ownership checks.
3.  **Database layer** opens MySQL connections. Individual services
    execute parameterized SQL and manage commits/rollbacks.
4.  **Storage layer** resolves safe relative storage keys and
    reads/writes private encrypted PNG files.
5.  **Templates** render the user-facing and admin-facing pages.
6.  **Configuration** reads environment values and configures Flask
    session and request limits.

The route layer should not be treated as the cryptographic
implementation. The cryptographic details are in
`services/encryption_service.py`; the image hiding algorithm is in
`services/steganography_service.py`.

------------------------------------------------------------------------

## 5. Encryption and steganography --- core design

Encryption and steganography are two separate operations:

-   **Encryption** makes the secret data unreadable without the correct
    credential.
-   **Steganography** hides the encrypted bytes inside an image so that
    the payload is not plainly visible.

Hiding data is not a replacement for encryption. StegoSecure uses both.

### 5.1 Supported secret payloads

**TEXT** - The submitted text is encoded as UTF-8 bytes. - Empty text is
rejected. - The plaintext size is limited by `MAX_SECRET_BYTES` (12
MiB).

**FILE** - The uploaded file is checked for presence and size. - The
original filename is sanitized with Werkzeug `secure_filename`. - File
bytes are Base64-encoded before Fernet encryption. - The filename is
stored as public payload metadata so the decrypted file can be
downloaded with a safe name. - Empty files and files larger than 12 MiB
are rejected.

The JSON payload itself is capped at 15 MiB. The final encrypted JSON
must also fit the selected cover image's actual capacity.

### 5.2 Authentication modes

#### Mode A --- Security Question (QA)

1.  User selects a predefined question or enters a custom question.
2.  User supplies an answer.
3.  `_normalize_qa_answer()` applies Unicode NFKC normalization, trims
    surrounding whitespace and applies `casefold()`.
4.  The normalized UTF-8 answer becomes the password input to PBKDF2.
5.  The question text is stored in the payload as a hint/metadata. The
    answer is never stored in the payload.

Because the answer is a human-chosen secret, users should choose a
strong, non-obvious answer and preserve its exact meaning. The
normalization makes case and compatible Unicode variations consistent,
but it does not make a weak answer strong.

#### Mode B --- Secret Key (KEY)

1.  The browser supplies a URL-safe Base64 secret key.
2.  `_decode_secret_key()` validates and decodes it.
3.  The decoded key must be exactly 32 bytes.
4.  Those bytes are passed to PBKDF2 with the payload's random salt.
5.  The secret key is not stored in the encrypted payload.

The key is essential for decryption. If it is lost, the application
cannot recover the original secret.

### 5.3 Key derivation and encryption parameters

The current implementation defines:

  Parameter                              Value
  -------------------------------------- ---------------------------------------------
  Cipher                                 Fernet (authenticated symmetric encryption)
  Key derivation                         PBKDF2-HMAC-SHA256
  PBKDF2 iterations                      600,000
  Derived key length                     32 bytes
  Random salt                            16 bytes per encryption
  Payload format version                 1
  Maximum original secret                12 MiB
  Maximum serialized encrypted payload   15 MiB

For each encryption: 1. Generate a new random 16-byte salt using
`os.urandom`. 2. Derive a 32-byte key using PBKDF2-HMAC-SHA256 and
600,000 iterations. 3. URL-safe Base64 encode the derived key for
Fernet. 4. Encrypt the prepared plaintext with Fernet. 5. Fernet
provides confidentiality and authentication/integrity checking. A wrong
credential or modified ciphertext causes decryption to fail.

A fresh salt is generated for every encryption, so the same answer/key
does not produce the same derived Fernet key across different payloads.

### 5.4 Payload envelope

After encryption, the application serializes a compact UTF-8 JSON
object. It contains public metadata and ciphertext, not the original
credential.

Conceptual example (ciphertext abbreviated):

``` json
{
  "version": 1,
  "encryption_type": "QA",
  "payload_type": "FILE",
  "payload_encoding": "base64",
  "kdf": {
    "name": "PBKDF2-HMAC-SHA256",
    "iterations": 600000,
    "salt": "<Base64-encoded random salt>"
  },
  "question": "A question shown to the recipient",
  "filename": "secret-document.pdf",
  "encrypted_payload": "<Fernet token>"
}
```

Fields vary by mode and payload: - `question` exists for QA mode only. -
`filename` exists for FILE payloads only. - `payload_encoding` is
`utf-8` for text or `base64` for files. - `encrypted_payload` is the
Fernet token. - Credentials are deliberately excluded.

### 5.5 Decryption logic

Decryption reverses the process:

1.  Read the uploaded image and validate it as a supported image.
2.  Require PNG for the encrypted-image upload path.
3.  Convert to RGB and extract the embedded payload using the LSB
    reader.
4.  Parse the JSON and validate its version, authentication type,
    payload type, KDF metadata, salt, ciphertext and conditional
    metadata.
5.  For QA, normalize the entered answer using the same normalization
    function. For KEY, decode and validate the supplied key.
6.  Read the salt from the payload.
7.  Derive the same Fernet key using PBKDF2-HMAC-SHA256.
8.  Ask Fernet to authenticate and decrypt the token.
9.  For TEXT, decode the result as UTF-8.
10. For FILE, Base64-decode the decrypted bytes and enforce the
    file-size limit.
11. Return the recovered data and validated metadata to the route, which
    presents text or sends the recovered file as a download.

If the answer/key is incorrect, or if the ciphertext/image has been
corrupted, Fernet authentication fails and the user receives a
controlled error. The server does not store a copy of the QA answer or
secret key.

### 5.6 Image LSB embedding

The steganography implementation is in
`services/steganography_service.py`.

-   The cover image is converted to RGB.
-   Each RGB channel is an 8-bit value.
-   The algorithm replaces the least-significant bit of successive
    channel values with payload bits.
-   Changing only the lowest bit produces a very small per-channel value
    change.
-   NumPy performs the bit operations in bounded chunks (256 KiB of
    payload per chunk) to avoid constructing an unnecessarily large
    temporary bit array.

**Header format** - The first 4 bytes store the payload length. - The
length is encoded as an unsigned, big-endian 32-bit integer
(`struct.pack(">I", length)`). - The payload bytes follow immediately
after the header. - Both header and payload are written to the LSBs of
the flattened RGB channel array.

**Capacity calculation** - RGB has 3 channels per pixel. - One bit is
stored per channel. - Therefore raw capacity is
`floor(width × height × 3 / 8)` bytes. - The 4-byte header is reserved,
so usable payload capacity is:

`max(0, floor(width × height × 3 / 8) - 4)`

The encrypted JSON payload must fit within this capacity and within the
15 MiB application payload cap.

**Important format behavior:** The generated stego image is saved as
PNG. Lossy formats such as JPEG can alter LSB values and destroy the
embedded data. Users must preserve and share the generated PNG without
converting, recompressing, resizing or otherwise editing it.

### 5.7 Capacity estimation

The browser can request `/encrypt/capacity` to estimate how much
original file data can fit in a selected image. The service models: -
Base64 expansion of file bytes - Fernet padding/token overhead and token
Base64 expansion - JSON metadata - QA question and filename metadata -
15 MiB encrypted payload cap

`get_max_encryptable_file_size()` uses binary search to find the largest
estimated source file size that fits. This estimate is advisory. The
encryption route performs the authoritative check against the actual
serialized encrypted payload length before embedding.

------------------------------------------------------------------------

## 5.8 What happens when the user selects a cover image: capacity calculation

Capacity is calculated in two places for two different purposes: the browser requests an early estimate so the user can choose a suitable file, and the encryption route performs an authoritative check against the real encrypted payload before embedding it.

### Browser-to-server estimate

1. In `templates/home.html`, the `DOMContentLoaded` script keeps the selected cover image dimensions in `coverWidth` and `coverHeight` and tracks whether the image is ready in `imageReady`.
2. When the cover image, authentication method, question, or selected secret-file name changes, `refreshFileCapacity()` is called. It sends a GET request to the URL generated for `encrypt_capacity` (`/encrypt/capacity`).
3. The query string contains `width`, `height`, `authentication_type`, `filename`, and `question`. For QA mode the selected/custom question is included because its serialized metadata occupies bytes in the final payload. The selected file name is included because its sanitized length also affects metadata size. When no file is selected, the browser uses `encrypted_file` as the estimate filename.
4. `app.py -> encrypt_capacity()` parses and validates the dimensions, checks `width * height` against `MAX_IMAGE_PIXELS`, validates QA/KEY mode and the maximum filename/question lengths.
5. It calculates the usable binary payload capacity using:

   ```python
   image_capacity = max(0, (width * height * 3) // 8 - 4)
   ```

   - `width * height` is the number of pixels.
   - Each RGB pixel has 3 colour channels.
   - One least-significant bit (LSB) is available in each channel, so the image has `width * height * 3` payload bits.
   - Divide by 8 to convert bits to bytes, using integer floor division.
   - Subtract 4 bytes because the steganography format first stores a 4-byte payload-length header.

6. `encrypt_capacity()` calls `services/encryption_service.py -> get_max_encryptable_file_size(image_capacity, authentication_type, filename, question)`. This does not encrypt a real file. It uses a binary search between 0 and `MAX_SECRET_BYTES` (12 MiB). For each candidate size, `estimate_file_payload_size()` estimates the serialized JSON payload size, including:
   - Base64 expansion of the original file (`4 * ceil(file_size / 3)`).
   - Fernet token overhead and URL-safe Base64 expansion.
   - JSON metadata, KDF name/iteration count/salt field, payload type and encoding.
   - The sanitized filename, and the security question in QA mode.
   It accepts a candidate only if the estimated payload fits both the image capacity and `MAX_ENCRYPTED_PAYLOAD_BYTES` (15 MiB). The binary search returns the largest original file size that fits.
7. The route returns JSON with `success`, `image_capacity_bytes`, `max_file_bytes`, and `max_file_mb`. On invalid parameters it returns a 400 JSON error; on unexpected failure it returns a 500 JSON error.
8. Back in `home.html`, `refreshFileCapacity()` sets `maxFileBytes`, marks `capacityReady = true`, updates the capacity display, and calls `validateForm()`. If a secret file is already selected, `checkSelectedSecretFile()` rechecks its size against `maxFileBytes`. A request counter (`capacityRequestId`) prevents an older, slower response from overwriting a newer result after the user changes a setting.

**Important distinction:** the displayed maximum is an estimate of the maximum *original file size*, not the number of bytes available for the encrypted JSON. It is mainly useful for the FILE selector. TEXT is ultimately checked using the exact encrypted payload size in `POST /encrypt`. The estimate is advisory; the final check is authoritative.

### Exact capacity used during encryption

After the uploaded cover image is decoded as RGB, `app.py -> encrypt()` calls `services/steganography_service.py -> get_image_capacity(cover_image)`. That function reads `image.size`, computes `width * height * 3`, integer-divides by 8, subtracts the same 4-byte header, and returns a non-negative integer byte count. After `encrypt_payload()` creates the real encrypted JSON bytes, `encrypt()` compares `len(encrypted_payload)` with this returned capacity. If the real payload is larger, encryption stops with an insufficient-capacity validation message. This check accounts for the real random salt, real Fernet token, exact text/file content, and actual serialized metadata.

## 5.9 Exact click-to-download encryption sequence

This is the runtime sequence for the Encrypt button in the supplied `local_storage` source snapshot. The browser-side code is in `templates/home.html`; the server route and core services are listed at each step.

1. **The user clicks Encrypt.** The `encryptionForm` submit listener in `templates/home.html` intercepts the normal form submission with `event.preventDefault()`.
2. **Browser-side gate checks run.** The handler checks `isAuthenticated`, `imageReady`, the button's disabled state, and the custom QA question requirement. The form's other validation functions also keep the button disabled until required fields and the selected file/capacity checks are valid. If the user is not authenticated, the browser navigates to the login URL.
3. **Duplicate submission is prevented.** The button is disabled, its label changes to `Encrypting...`, and a progress message is displayed.
4. **The browser sends the form.** `fetch(encryptionForm.action, { method: "POST", body: new FormData(encryptionForm), credentials: "same-origin" })` sends a multipart request to `POST /encrypt`. The form includes the CSRF token, cover image, TEXT or FILE choice and data, QA or KEY choice and credential, and optional output name.
5. **Flask receives the request.** `app.py -> encrypt()` first checks `session["user_id"]`. If absent, it flashes a login message and redirects to login.
6. **Credit balance is checked before expensive processing.** `encrypt()` calls `services/credit_service.py -> get_remaining_credits(user_id)`. A missing credit record or zero balance stops the request. This is an early user-friendly check, not the final deduction.
7. **Cover image is validated and loaded.** `encrypt()` gets `cover_image` from `request.files`, calls `utils/validators.py -> validate_cover_image()`, opens it with Pillow, loads its pixel data and converts it to RGB. It then calls `get_image_capacity()` from `services/steganography_service.py`. An image with no usable capacity is rejected.
8. **Secret data is read and validated.** `payload_type` is normalized to TEXT or FILE. TEXT is read from `secret_text` and must not be blank. FILE is checked by `validate_secret_file()` with `MAX_SECRET_BYTES` (12 MiB), its safe filename is retained, and its bytes are read from the beginning of the uploaded stream. Empty files are rejected.
9. **Authentication input is read.** In QA mode, `security_answer` and the selected/custom `security_question` are required. In KEY mode, `secret_key` is required. Any other authentication mode is rejected.
10. **The cryptographic payload is created.** `app.py -> encrypt()` calls `services/encryption_service.py -> encrypt_payload(...)` with payload type, data, auth type, credential, question and filename. Inside that function:
    - `_prepare_secret_data()` converts TEXT to UTF-8 bytes, or FILE bytes to Base64 bytes; it enforces non-empty content and the 12 MiB secret limit.
    - QA credentials pass through `_normalize_qa_answer()` (Unicode NFKC normalization, trim, casefold, UTF-8 conversion and a 1024-byte limit). KEY credentials pass through `_decode_secret_key()`; URL-safe Base64 must decode to exactly 32 bytes.
    - FILE names are sanitized with `secure_filename()` and checked against the 255-character limit.
    - A new random 16-byte salt is generated for every encryption.
    - `_derive_fernet_key()` runs PBKDF2-HMAC-SHA256 for 600,000 iterations to derive 32 bytes and URL-safe-Base64 encodes the result for Fernet.
    - Fernet encrypts the prepared plaintext. The credential itself is never written into the payload.
    - A compact UTF-8 JSON envelope is created with version, auth type, payload type, encoding, KDF details, salt, ciphertext and (where relevant) question/filename. The serialized bytes are returned. Payloads above 15 MiB are rejected.
11. **The real payload is checked against the real image.** `encrypt()` compares `len(encrypted_payload)` with the capacity returned in step 7. This is the final capacity decision. If it does not fit, no embedding or credit deduction occurs.
12. **The encrypted bytes are hidden in the image.** `app.py -> encrypt()` calls `services/steganography_service.py -> embed_payload(cover_image, encrypted_payload)`. `embed_payload()` validates the byte payload and its 15 MiB ceiling, checks capacity again, packs the payload length as a 4-byte unsigned big-endian integer (`struct.pack(">I", len(payload_bytes))`), converts the RGB image to a writable NumPy array, and writes the header followed by payload bits into the least-significant bit of each RGB channel. `_write_bytes_to_pixels()` processes data in chunks of at most 256 KiB. It returns a new RGB Pillow image.
13. **The stego image is encoded as PNG.** `encrypt()` chooses a sanitized output name, writes the result to an in-memory `BytesIO` stream with `format="PNG"`, and obtains the exact PNG bytes. PNG is required because JPEG is lossy and can change LSB values.
14. **A private copy is saved.** `services/storage_service.py -> save_encrypted_image(user_id, output_bytes)` writes the PNG beneath the configured private storage directory and returns a relative storage key plus file size. The image is not placed in a public static directory.
15. **Gallery row and credit deduction are committed together.** `app.py -> encrypt()` calls `services/gallery_service.py -> create_gallery_record_and_consume_credit(...)`. The database operation registers the user's gallery metadata and consumes one credit in a transaction. The earlier balance check is not relied on to protect against two simultaneous requests spending the final credit.
16. **Failure cleanup runs if registration fails.** If the gallery/credit transaction fails or reports that another request used the last credit, `encrypt()` calls `delete_encrypted_image(storage_key)` to remove the just-saved private file, then returns an error. This prevents an orphaned file from remaining after a failed database operation.
17. **The server returns the PNG.** On success, `encrypt()` returns `send_file(...)` with `mimetype="image/png"`, `as_attachment=True`, and the sanitized `.png` download name.
18. **The browser downloads it.** The `fetch()` handler in `home.html` checks that the response is successful and has an image/png content type, reads it as a Blob, obtains the filename from `Content-Disposition`, creates a temporary object URL, clicks a temporary download link, and displays the success message. It then revokes the object URL and reloads the page to refresh the credit balance and reset the form.

**Credit timing:** the early balance check is in step 6. The actual credit consumption is coupled to gallery registration in step 15. A failed validation, failed capacity check, failed encryption, or failed embedding does not consume a credit. If the final DB operation cannot consume the credit, the saved file is removed.

## 5.10 Exact click-to-result decryption sequence

The decryption page deliberately has two server requests: first inspect the image to discover safe public metadata and show the correct credential prompt; then submit the credential and decrypt. The browser code is in `templates/decryption.html`.

### A. Selecting the encrypted PNG and inspecting it

1. **The user opens `/decrypt`.** `app.py -> decryption_page()` requires a logged-in session and renders `templates/decryption.html`.
2. **The user selects an image.** The `change` listener on `encryptedImage` stores the selected file, clears any old result/metadata, hides the authentication fields, and disables the Decrypt button. The browser checks the MIME type is PNG and applies its client-side 40 MiB file-size check.
3. **The preview is created.** The browser creates a temporary object URL for the selected image and displays the preview. This is only a browser preview; it does not decrypt anything.
4. **The browser requests inspection.** `getFormData()` adds `encrypted_image` and the CSRF token. A `fetch()` POST is sent to `/decrypt/inspect` (`url_for('decrypt_inspect')`).
5. **Flask checks authentication.** `app.py -> decrypt_inspect()` returns HTTP 401 if `session["user_id"]` is absent.
6. **The server validates and loads the PNG.** It checks that a file was supplied, calls `load_encrypted_png()` (which calls `validate_cover_image()`, checks the decoded format is PNG, loads it and converts it to RGB), and rejects invalid or non-original JPEG/other formats.
7. **The payload is extracted.** `decrypt_inspect()` calls `services/steganography_service.py -> extract_payload(stego_image)`. That function reads the first 4 bytes from RGB channel LSBs as an unsigned big-endian payload length, validates the length against zero, the 15 MiB maximum and image capacity, then reads exactly that many bytes starting after the 32 header bits. `_read_bytes_from_pixels()` reconstructs bytes in chunks of up to 256 KiB.
8. **Only public metadata is inspected.** `decrypt_inspect()` calls `services/encryption_service.py -> inspect_payload(payload_bytes)`. It parses the JSON and validates version, QA/KEY mode, TEXT/FILE type, KDF name/iteration count, 16-byte salt, encrypted-data presence and the question or safe filename as applicable. It does not decrypt the ciphertext and does not verify that the credential is correct.
9. **The inspection response is returned.** The route returns JSON fields `success`, `authentication_type`, `payload_type`, `question`, and `filename`. The browser stores this metadata, displays the payload type/authentication type, shows the saved security question in QA mode or a secret-key prompt in KEY mode, then enables Decrypt.

### B. User submits the answer or key and decrypts

10. **The user enters the credential and clicks Decrypt.** The click handler requires both the selected file and inspected metadata, checks that the credential is not blank, disables the button, clears old results, and adds `credential` to the multipart form data.
11. **The browser sends the decrypt request.** It sends `POST /decrypt` with the encrypted PNG, CSRF token and credential.
12. **The server checks the session and image again.** `app.py -> decrypt()` requires login, validates the uploaded file, calls `load_encrypted_png()` and extracts the payload again with `extract_payload()`. The second extraction is intentional: the actual decrypt endpoint processes the image it received in this request rather than trusting browser-supplied metadata from the earlier inspection call.
13. **The credential is validated and the cryptographic key is reconstructed.** `decrypt()` calls `services/encryption_service.py -> decrypt_payload(payload_bytes, credential)`. That function calls `inspect_payload()` again, parses the envelope, normalizes the QA answer with `_normalize_qa_answer()` or decodes the 32-byte KEY with `_decode_secret_key()`, reads the embedded salt and calls `_derive_fernet_key()` using the same PBKDF2-HMAC-SHA256 settings (600,000 iterations).
14. **Fernet authenticates and decrypts.** `Fernet(...).decrypt(...)` verifies the token's authentication tag as well as decrypting the ciphertext. A wrong answer/key or altered ciphertext raises `InvalidToken` and is converted into a controlled `ValueError` message. This is the point at which the credential is actually verified; the earlier inspection only revealed the public prompt/type metadata.
15. **The original content is reconstructed.** For TEXT, the decrypted bytes are decoded as UTF-8. For FILE, the decrypted Base64 bytes are decoded back to the original file bytes and checked against the 12 MiB maximum. The result includes validated metadata and the recovered data.
16. **The route returns the correct response type.** TEXT is returned as JSON (`success`, `payload_type: TEXT`, and `data`). FILE is returned with `send_file()` as an attachment-compatible file response, using a sanitized filename and MIME type inferred with `mimetypes.guess_type()`; `X-File-Name` and `X-File-Mime` headers tell the browser how to label it.
17. **The browser displays or prepares the result.** For TEXT, `templates/decryption.html` reads the JSON and puts the plaintext in the result textarea. For FILE, it reads the response as a Blob, uses the response headers (falling back to inspected metadata), creates a Blob URL, displays the original filename, and enables the relevant preview/download actions.
18. **No credit is consumed.** The decryption routes do not call the credit-consumption service. Credits are charged for successful encryption only.

### What inspection does and does not prove

- It proves that the image contains a structurally valid StegoSecure payload with supported public metadata.
- It reveals whether the payload is TEXT or FILE and whether it expects QA or KEY authentication; QA mode also reveals the stored question.
- It does **not** prove the supplied answer/key is correct, decrypt the secret, or guarantee that the ciphertext is intact. Fernet authentication during `decrypt_payload()` provides that verification.

## 6. Complete user workflows

### 6.1 Registration

1.  Visitor opens `/register`.
2.  `routes/auth_routes.py` receives the form.
3.  `services/auth_service.py` validates username, normalizes email and
    validates password.
4.  Password is hashed with Argon2; the plaintext password is not
    stored.
5.  A user row is inserted.
6.  A corresponding `encryption_limits` row is created using the current
    system default encryption limit.
7.  The user can then log in.

### 6.2 Login and session

1.  User submits email and password at `/login`.
2.  Email is normalized.
3.  The stored Argon2 password hash is verified.
4.  Inactive or invalid accounts are rejected.
5.  Successful authentication clears/refreshes the session and stores
    the authenticated user identifier and display details used by
    protected routes.
6.  Logout clears the user session.

### 6.3 Encrypt text or file

1.  User signs in and opens the home/encryption section.
2.  User selects a cover image.
3.  The browser can request capacity information from
    `/encrypt/capacity`.
4.  User selects TEXT or FILE.
5.  For TEXT, the text field is required. For FILE, the secret file is
    selected.
6.  User selects QA or KEY authentication and supplies the required
    credential.
7.  User optionally sets an output filename.
8.  The browser submits the form to `POST /encrypt`.
9.  The route checks login state and current credit balance before
    processing.
10. The cover image is validated by actual image content, format and
    pixel count, then decoded and converted to RGB.
11. Secret data and credential fields are validated.
12. `encrypt_payload()` prepares, derives a key, encrypts and serializes
    the payload.
13. The actual encrypted payload length is compared with the image
    capacity.
14. `embed_payload()` writes the header and encrypted JSON into RGB
    LSBs.
15. The resulting image is encoded as PNG.
16. `save_encrypted_image()` writes the PNG to private local storage and
    returns a relative storage key and file size.
17. `create_gallery_record_and_consume_credit()` records the gallery
    entry and consumes one credit in a database transaction.
18. If gallery/credit registration fails, the newly saved private file
    is deleted to avoid an orphaned file.
19. The PNG is returned to the browser as a download.

**Credit behavior:** The route checks the balance early for a friendly
response. The final credit consumption occurs with the gallery database
operation so concurrent requests cannot both spend the same last credit.

### 6.4 Decrypt text or file

1.  User opens `/decrypt`.
2.  User selects the original encrypted PNG.
3.  The UI can first submit the image to `/decrypt/inspect` to discover
    validated public metadata, such as payload type and (for QA) the
    security question.
4.  User supplies the answer or secret key.
5.  The form is submitted to `POST /decrypt`.
6.  The route validates the uploaded PNG, extracts the payload, and
    calls `decrypt_payload()`.
7.  TEXT is displayed to the user.
8.  FILE is returned as a download using the sanitized original
    filename.
9.  Invalid image, malformed payload, wrong credential or corrupted
    ciphertext produces a controlled error.

Decryption does not consume an encryption credit.

### 6.5 Previous encrypted images

1.  Signed-in user opens `/previous`.
2.  The route requests the current user's unexpired gallery rows.
3.  Gallery records contain metadata and a relative storage key; the
    image bytes remain in `private_storage/`.
4.  User can preview a protected image, download the original PNG or
    delete the gallery item.
5.  Ownership is checked using both the authenticated user ID and image
    ID.
6.  Expired items are not shown in the normal gallery/download/preview
    queries.
7.  Deletion removes the database gallery record and the corresponding
    local file where applicable.

The gallery is a convenience/history feature. Users should still
download and keep their own encrypted PNG and preserve the corresponding
credential.

### 6.6 Buy encryption credits

1.  Signed-in user opens `/credits`.
2.  The page displays active credit plans.
3.  User chooses a plan and submits a purchase request.
4.  `POST /payments/create-order` asks the payment service to create a
    Razorpay order.
5.  The pending payment record is saved in MySQL with user, plan, amount
    and order reference/snapshots.
6.  Razorpay Checkout completes the payment interaction in the browser.
7.  The browser submits the Razorpay payment ID, order ID and signature
    to `POST /payments/verify`.
8.  The backend verifies the signature using the configured Razorpay
    secret and checks that the order/payment belongs to the expected
    user/payment record.
9.  A successful payment is marked successful and the purchased credits
    are added to the user's credit balance within a database
    transaction.
10. Repeated verification must not credit the same payment twice; the
    service uses payment/order identity and transaction state to enforce
    idempotent crediting.
11. Payment history is available to the signed-in user.

Use Razorpay test credentials for test-mode development. Real payment
processing requires the correct live credentials and operational
configuration.

### 6.7 Profile management

The user profile page supports: - Viewing account information - Updating
username - Changing password after verifying the current password

Password updates are validated and re-hashed with Argon2. The current
password is checked before accepting a change. Profile actions require
an authenticated user session.

### 6.8 Admin console

The administrator interface is mounted under the non-default prefix:

`/secure-console-x7k9`

Important URLs: - Admin login: `/secure-console-x7k9/` - Admin
dashboard: `/secure-console-x7k9/dashboard` - Users:
`/secure-console-x7k9/users` - Credit plans:
`/secure-console-x7k9/credit-plans` - Revenue:
`/secure-console-x7k9/revenue` - System settings:
`/secure-console-x7k9/settings`

The admin prefix is intentionally different from the normal `/admin`
convention. Use the configured prefix from `admin/admin_routes.py`.

Admin login uses the separate `admins` table and Argon2 password hashes.
Protected admin routes use `admin_required`, which checks that the
session's admin ID still maps to an active administrator. Admin logout
clears admin session values.

#### Dashboard

Shows application-level statistics such as users, credits, plans and
payment/revenue metrics, as assembled by `admin/dashboard_service.py`.

#### User management

-   Fetches users in bounded batches with ID-based cursor pagination.
-   Supports search and status filtering.
-   Allows the administrator to activate/deactivate a user.
-   Allows the administrator to adjust remaining encryption credits.
-   API operations validate input and use database updates.

#### Credit plan management

-   Lists plans.
-   Creates plans with name, price, credit quantity and popular flag.
-   Updates plan details.
-   Activates/deactivates plans.
-   Deletes plans where database constraints allow it.
-   Maintains a single popular-plan selection according to the plan
    service logic.
-   Active plans are the plans exposed to customers for purchase.

#### Revenue management

-   Provides summary figures based on successful payments.
-   Lists transactions by status (success, pending or failed).
-   Supports search across payment/order identifiers and user identity
    fields.
-   Uses bounded page sizes and ID cursor pagination to avoid loading
    the entire payment table at once.
-   Stores and displays plan/credit snapshots so historical transaction
    display is not dependent only on a plan's current name/credit
    amount.

#### System settings and banners

-   Reads and updates the default encryption limit for newly registered
    users.
-   Updating the default does not retroactively reset existing users'
    credit balances.
-   Lists administrator-uploaded banners stored under
    `instance/banners/`.
-   Accepts PNG, JPG/JPEG and WEBP only.
-   Enforces an 8 MiB upload limit and a 25-million-pixel limit.
-   Generates server-side filenames beginning with `admin_`.
-   Allows one active admin banner setting at a time.
-   Supports activate, deactivate, preview and delete operations.
-   Deleting an active banner clears its active setting before removing
    the file.
-   The bundled `StegoSecure-default-Banner.png` is the fallback when no
    uploaded banner is active. The default bundled banner is not treated
    as an uploaded admin banner and must not be deleted through the
    admin upload-management flow.

------------------------------------------------------------------------

## 7. Backend file-by-file reference

This section explains the responsibility of every backend Python module
and its principal functions in the supplied source snapshot.

### 7.1 `app.py` --- Flask application and core encryption routes

Creates the Flask application, loads `Config`, refuses to start without
a `SECRET_KEY`, checks the configured upload limit, enables CSRF
protection, and registers the authentication, payment and admin
blueprints.

-   `load_encrypted_png(uploaded)` --- Reuses the cover-image validator,
    then requires the uploaded image's actual format to be PNG, fully
    loads it and returns RGB data. This ensures decryption uses the
    original lossless output format.
-   `serve_logo()` --- Serves the project logo file.
-   `home()` --- Renders the landing/encryption page, obtains the
    signed-in user's remaining credits when available, and supplies the
    active banner endpoint URL.
-   `encrypt()` --- Main encryption POST workflow: login/credit checks,
    cover and secret validation, credential handling, payload
    encryption, capacity enforcement, LSB embedding, PNG serialization,
    private storage, atomic gallery/credit registration, rollback
    cleanup and file download response.
-   `encrypt_capacity()` --- Validates requested image dimensions and
    authentication metadata, calculates usable image capacity and
    returns an estimated maximum secret-file size for the UI.
-   `previous_images()` --- Requires login and renders the current
    user's unexpired gallery.
-   `download_previous_image(image_id)` --- Checks ownership and
    retention, resolves the safe storage key and sends the encrypted PNG
    as a private no-cache download.
-   `previous_image_file(image_id)` --- Returns a protected image
    response for preview use; requires login and ownership/retention
    checks.
-   `delete_previous_image(image_id)` --- Deletes only a gallery record
    owned by the current user and coordinates removal of its stored
    file.
-   `decryption_page()` --- Renders the decryption interface.
-   `decrypt_inspect()` --- Validates an uploaded encrypted PNG,
    extracts the payload and returns validated public metadata to the UI
    before the user submits the credential.
-   `decrypt()` --- Validates the encrypted PNG, extracts and decrypts
    the payload, then returns recovered text or a file download.
-   `site_banner()` --- Serves the currently selected admin banner, or
    the bundled default banner when no valid uploaded banner is active.

### 7.2 `config.py` --- Application configuration

-   `BASE_DIR` --- Absolute project directory used to load `.env`
    consistently.
-   `Config` --- Defines Flask secret key, Razorpay credentials, cookie
    flags, session lifetime and maximum multipart request size.
    -   `SECRET_KEY` comes from `.env`.
    -   `SESSION_COOKIE_HTTPONLY=True` prevents browser JavaScript from
        reading the session cookie.
    -   `SESSION_COOKIE_SAMESITE="Lax"` provides a same-site cookie
        policy.
    -   `SESSION_COOKIE_SECURE` is controlled by `COOKIE_SECURE`; enable
        it when HTTPS is configured.
    -   `PERMANENT_SESSION_LIFETIME` is 7,200 seconds.
    -   `MAX_CONTENT_LENGTH` is derived from `MAX_UPLOAD_MB`.

### 7.3 `db.py` --- MySQL connection factory

-   `get_db_connection()` --- Opens a MySQL connection using `DB_HOST`,
    `DB_PORT`, `DB_NAME`, `DB_USER` and `DB_PASSWORD`, with UTF-8 MB4
    charset and a connection timeout. Callers are responsible for
    closing cursors and connections.

### 7.4 `create_admin.py` --- Initial administrator creation

-   `create_admin()` --- Interactive CLI utility. Prompts for admin
    username, normalized email and password (password input is hidden),
    validates the password, hashes it with Argon2 and inserts an
    administrator record. It handles duplicate username/email errors and
    closes database resources. Run it once to provision an initial
    admin; do not put admin passwords in source code.

### 7.5 `utils/validators.py` --- Shared input and upload validation

-   `normalize_email(email)` --- Validates and returns a normalized
    lowercase email address without performing deliverability checks.
-   `validate_username(username)` --- Normalizes whitespace and permits
    2--50 characters containing letters, spaces, dots, hyphens or
    apostrophes.
-   `validate_password(password)` --- Requires 8--128 characters, at
    least one uppercase letter, one digit and one special character.
-   `validate_cover_image(file_storage, max_pixels)` --- Validates
    actual image bytes, supported format (PNG/JPEG/BMP/WEBP), positive
    dimensions and pixel-count ceiling; verifies and fully decodes the
    image to reject corrupt uploads; resets the stream position.
-   `validate_secret_file(file_storage, max_bytes)` --- Checks file
    presence, non-empty content, byte-size limit and returns a sanitized
    filename and size.

Constants: - `MAX_IMAGE_PIXELS = 40_000_000` -
`ALLOWED_IMAGE_FORMATS = PNG, JPEG, BMP, WEBP`

### 7.6 `services/encryption_service.py` --- Cryptographic payload engine

Constants: - `PAYLOAD_VERSION` --- Payload schema version (1). -
`KDF_NAME` --- PBKDF2-HMAC-SHA256. - `KDF_ITERATIONS` --- 600,000. -
`KDF_SALT_BYTES` --- 16. - `MAX_SECRET_BYTES` --- 12 MiB. -
`MAX_QUESTION_LENGTH` --- 500 characters. - `MAX_FILENAME_LENGTH` ---
255 characters. - `MAX_ENCRYPTED_PAYLOAD_BYTES` --- 15 MiB.

Functions: - `_fernet_token_size(plaintext_size)` --- Calculates Fernet
token size including block padding and URL-safe Base64 expansion; used
for capacity estimation. -
`estimate_file_payload_size(file_size, authentication_type, filename, question)`
--- Estimates final JSON payload length for a file, including Base64 and
Fernet overhead and metadata. -
`get_max_encryptable_file_size(image_capacity, authentication_type, filename, question)`
--- Binary-searches the maximum original file size that is estimated to
fit both the image and application payload cap. -
`_normalize_qa_answer(answer)` --- Applies NFKC, trim and case-fold
normalization, checks non-empty input and enforces a 1,024-byte UTF-8
limit. - `_decode_secret_key(secret_key)` --- Validates URL-safe Base64
input and requires exactly 32 decoded bytes. -
`_derive_fernet_key(password_bytes, salt)` --- Runs PBKDF2-HMAC-SHA256
to derive 32 bytes, then URL-safe Base64 encodes them for Fernet. -
`_prepare_secret_data(payload_type, data)` --- Converts text to UTF-8
bytes or file bytes to Base64 bytes and enforces empty/size/type
rules. - `encrypt_payload(...)` --- Validates mode/type, prepares secret
data and credential, sanitizes a file name, creates a random salt,
derives the key, encrypts with Fernet and returns compact JSON bytes
containing metadata and ciphertext. - `inspect_payload(payload_bytes)`
--- Parses and validates payload size, JSON structure, version, modes,
KDF parameters, salt, ciphertext and mode-specific question/filename
metadata; returns safe metadata without decrypting. -
`decrypt_payload(payload_bytes, credential)` --- Revalidates metadata,
derives the key from the supplied credential and salt,
authenticates/decrypts with Fernet, decodes text or Base64 file bytes,
enforces the output size and returns metadata plus recovered data.

### 7.7 `services/steganography_service.py` --- RGB LSB engine

Constants: - `HEADER_SIZE = 4` --- Four-byte payload-length header. -
`CHANNELS_PER_PIXEL = 3` --- RGB. - `BITS_PER_BYTE = 8`. -
`CHUNK_SIZE = 256 KiB`. - `MAX_PAYLOAD_BYTES = 15 MiB`.

Functions: - `get_image_capacity(image)` --- Calculates usable bytes in
RGB channels after reserving the four-byte header. -
`_write_bytes_to_pixels(flat_pixels, start_channel, data)` --- Converts
each data chunk to bits and writes those bits into channel LSBs. -
`_read_bytes_from_pixels(flat_pixels, start_channel, byte_count)` ---
Reads channel LSBs in chunks and repacks them into bytes. -
`embed_payload(cover_image, payload_bytes)` --- Validates payload and
capacity, writes the big-endian length header followed by payload bytes,
and returns a new RGB Pillow image. - `extract_payload(stego_image)` ---
Reads and validates the length header, checks size/capacity bounds and
returns the embedded payload bytes.

### 7.8 `services/storage_service.py` --- Private local filesystem storage

-   `_get_safe_path(storage_key)` --- Rejects invalid/absolute/traversal
    storage keys and resolves the key under the configured storage root
    to prevent escaping the private directory.
-   `save_encrypted_image(user_id, image_bytes)` --- Creates a
    user-specific private storage location, writes the generated
    encrypted PNG and returns a relative storage key plus saved byte
    count.
-   `get_encrypted_image_path(storage_key)` --- Resolves a safe key and
    returns a path only when the file exists.
-   `delete_encrypted_image(storage_key)` --- Safely resolves and
    deletes the stored encrypted image.

The root is controlled by `ENCRYPTED_STORAGE_DIR` and defaults to
`private_storage`. The storage service does not expose this directory as
a public static folder; protected routes stream files after
authorization.

### 7.9 `services/gallery_service.py` --- Gallery records, retention and credit transaction

-   `create_gallery_record_and_consume_credit(user_id, storage_key, original_filename, output_filename, file_size_bytes, retention_days)`
    --- In one database transaction, locks/checks the user's credit row,
    rejects missing/zero credits, inserts the gallery metadata with an
    expiry date and decrements one credit. This is the final atomic
    credit-consumption point.
-   `get_user_gallery(user_id)` --- Returns the user's non-expired
    gallery records, newest first.
-   `get_user_gallery_image(user_id, image_id)` --- Returns a specific
    unexpired record only when it belongs to that user.
-   `delete_user_gallery_record(user_id, image_id)` --- Deletes a record
    only for its owner and handles the corresponding stored file.
-   `get_user_gallery_image_for_delete(user_id, image_id)` --- Retrieves
    the owner's record even when expired so cleanup/deletion can still
    be performed.

The source snapshot contains repeated definitions of some gallery
functions. In Python, the later definition of a function name replaces
the earlier definition at module import time. The effective behavior is
therefore the last definition in the file; this is an implementation
detail worth keeping in mind when refactoring.

### 7.10 `services/credit_service.py` --- Credit balance operations

-   `get_remaining_credits(user_id)` --- Reads the user's remaining
    encryption attempts/credits and returns the balance (or a
    missing-record result).
-   `consume_encryption_credit(user_id)` --- Provides a guarded
    credit-decrement operation. The main encryption/gallery workflow
    uses the gallery service's transaction so gallery insertion and
    decrement are coordinated atomically.

### 7.11 `services/auth_service.py` --- User account business logic

-   `register_user(username, email, password)` --- Validates user
    fields, hashes password with Argon2, inserts the user and
    initializes the credit row from the configured default.
-   `authenticate_user(email, password)` --- Normalizes email, loads the
    account and verifies the Argon2 hash; rejects invalid or inactive
    accounts.
-   `get_user_profile(user_id)` --- Loads the current user's profile
    fields.
-   `update_username(user_id, new_username)` --- Validates and updates
    username, handling uniqueness conflicts.
-   `verify_current_password(user_id, current_password)` --- Checks the
    supplied current password against the stored Argon2 hash.
-   `update_user_password(user_id, new_password)` --- Validates, hashes
    and updates the password.

### 7.12 `routes/auth_routes.py` --- User-facing authentication and profile routes

Blueprint: `auth_bp`.

-   `register()` --- GET renders registration; POST validates and
    creates an account, then reports success/errors.
-   `login()` --- GET renders login; POST authenticates and creates the
    user session; supports a safe post-login destination.
-   `dashboard()` --- Renders the authenticated user's dashboard.
-   `profile()` --- Requires login and renders profile/account
    information.
-   `change_username()` --- Handles the profile username update POST.
-   `change_password()` --- Verifies current password, validates the new
    password and updates its Argon2 hash.
-   `logout()` --- Clears the user session and redirects to the public
    page.

### 7.13 `routes/payment_routes.py` --- Customer payment endpoints

Blueprint: `payment_bp`.

-   `credits_page()` --- Displays available credit plans and the user's
    payment/credit information.
-   `create_order()` --- Requires a signed-in user, validates the
    selected plan and requests a Razorpay order from the payment
    service.
-   `verify_payment()` --- Receives Razorpay payment details and
    delegates signature verification and crediting to the payment
    service.

### 7.14 `services/payment_service.py` --- Razorpay and payment persistence

-   `get_active_plans()` --- Returns active credit plans available for
    purchase.
-   `create_razorpay_order(user_id, plan_id, key_id, key_secret)` ---
    Validates plan availability, creates a Razorpay order, and stores a
    pending payment record with amount and plan/credit snapshots.
-   `verify_and_credit_payment(user_id, payment_id, order_id, signature, key_id, key_secret)`
    --- Verifies the Razorpay signature, checks the local pending
    payment/order/user relationship, and transactionally marks the
    payment successful and adds credits without double-crediting an
    already processed payment.
-   `get_user_payment_history(user_id)` --- Returns the signed-in user's
    payment history.

### 7.15 `services/site_service.py` --- Active site banner lookup

-   `get_active_banner()` --- Reads the active banner filename from
    `site_settings` and returns the selected uploaded banner when it is
    valid/available; otherwise the application uses the bundled default
    banner.

### 7.16 `admin/admin_auth.py` --- Admin authorization

-   `get_active_admin(admin_id)` --- Loads an administrator only if the
    account exists and is active.
-   `admin_required(view)` --- Decorator that protects admin endpoints,
    checks the admin session and active status, and redirects
    unauthenticated/inactive admins to the admin login route.

### 7.17 `admin/admin_routes.py` --- Admin HTTP interface

Blueprint name: `admin_bp`.

URL prefix: `/secure-console-x7k9`.

-   `login()` --- Handles admin login against the `admins` table,
    verifies Argon2 password hash and establishes admin session values.
-   `dashboard()` --- Requires admin authorization and renders dashboard
    statistics.
-   `users()` --- Renders the user-management page.
-   `credit_plans()` --- Renders credit-plan management.
-   `users_api()` --- Returns paginated/searchable/filterable user data.
-   `update_user_status_api(user_id)` --- Activates/deactivates a user.
-   `update_user_credits_api(user_id)` --- Updates a user's remaining
    credits.
-   `credit_plans_api()` --- Returns plan records for the admin UI.
-   `create_plan_api()` --- Validates and creates a credit plan.
-   `update_plan_api(plan_id)` --- Updates plan name, price, credit
    amount and popular selection.
-   `update_plan_status_api(plan_id)` --- Enables/disables a plan.
-   `delete_plan_api(plan_id)` --- Deletes a plan when allowed by
    database relationships.
-   `revenue()` --- Renders the revenue page.
-   `revenue_summary_api()` --- Returns revenue summary figures.
-   `revenue_transactions_api()` --- Returns transaction batches with
    status/search/cursor parameters.
-   `settings()` --- Renders system settings.
-   `settings_limit_api()` --- Reads the current default encryption
    limit.
-   `update_settings_limit_api()` --- Validates and updates the default
    for new users.
-   `settings_banners_api()` --- Lists uploaded banners and active
    state.
-   `upload_banner_api()` --- Validates and stores an uploaded banner.
-   `update_banner_status_api(filename)` --- Activates or deactivates a
    selected uploaded banner.
-   `delete_banner_api(filename)` --- Deletes an uploaded banner and
    clears active selection if needed.
-   `preview_banner_api(filename)` --- Serves a validated admin-uploaded
    banner for preview.
-   `logout()` --- Clears administrator session values.

### 7.18 Admin service modules

#### `admin/dashboard_service.py`

-   `get_dashboard_statistics()` --- Queries and returns the aggregate
    values required by the admin dashboard.

#### `admin/user_service.py`

-   `get_users(limit, before_id, search, status)` --- Fetches a bounded
    batch of users using ID-based cursor pagination, optional search and
    account-status filtering.
-   `update_user_status(user_id, is_active)` --- Updates the user's
    active/inactive state.
-   `update_user_credits(user_id, remaining_credits)` --- Validates and
    updates the user's remaining credit count.

#### `admin/plan_service.py`

-   `get_all_plans()` --- Returns credit plans for admin management.
-   `create_plan(name, price, credits, is_popular)` --- Validates and
    inserts a plan, including popular-plan handling.
-   `get_popular_plan_id()` --- Returns the current popular plan
    identifier.
-   `update_plan(plan_id, name, price, credits, is_popular)` --- Updates
    plan fields and maintains popular selection.
-   `update_plan_status(plan_id, is_active)` --- Changes plan
    availability.
-   `delete_plan(plan_id)` --- Deletes a plan only where relational
    constraints permit it.

#### `admin/revenue_service.py`

-   `get_revenue_summary()` --- Computes revenue totals using successful
    payment records only.
-   `get_transactions(status, limit, before_id, search)` --- Returns one
    bounded status-specific transaction batch, with cursor pagination
    and search across payment/order identifiers and user identity.

#### `admin/settings_service.py`

-   `_banner_directory(instance_path)` --- Creates and returns the
    `instance/banners` directory.
-   `get_default_encryption_limit()` --- Reads the configured default;
    returns 5 if the setting row is absent.
-   `update_default_encryption_limit(value)` --- Validates a whole
    number in the supported range and upserts the setting.
-   `list_uploaded_banners(instance_path)` --- Reads the active banner
    setting and lists eligible `admin_` banner files with size, modified
    time and active state.
-   `save_uploaded_banner(file_storage, instance_path)` --- Enforces
    size, format and pixel limits, generates a UUID-based filename and
    writes the file.
-   `_validate_uploaded_filename(filename, instance_path)` --- Rejects
    path traversal/invalid names and confirms the file exists inside the
    banner directory.
-   `activate_banner(filename, instance_path)` --- Validates the file
    and stores it as the active banner.
-   `deactivate_banner(filename, instance_path)` --- Clears the active
    setting only when it references the selected file.
-   `delete_uploaded_banner(filename, instance_path)` --- Clears any
    active setting referencing the file, then deletes the file.

------------------------------------------------------------------------

## 8. Database schema and relationships

The schema is defined in `database/schema.sql`. It creates the
`stego_secure` database and the following tables.

  ----------------------------------------------------------------------------
  Table                   Purpose                 Important relationships/data
  ----------------------- ----------------------- ----------------------------
  `users`                 Customer accounts       Unique username/email;
                                                  Argon2 password hash; active
                                                  and email-verification flags

  `admins`                Admin accounts          Separate credentials and
                                                  active status

  `plans`                 Credit products         Name, price, encryption
                                                  quantity, active status

  `system_settings`       Integer system settings Includes
                                                  `default_encryption_limit`

  `encryption_limits`     User credit balance     One row per user; cascades
                                                  when user is deleted

  `gallery`               Previous                User ID, private storage
                          encrypted-image         key, filenames, size,
                          metadata                created and expiry dates

  `payments`              Razorpay transactions   User, plan, payment/order
                                                  IDs, amount, status and
                                                  plan/credit snapshots

  `site_settings`         String settings         Includes `active_banner`
                                                  filename
  ----------------------------------------------------------------------------

### Key relational behavior

-   A user has one `encryption_limits` row.
-   A user can have many gallery records.
-   A user can have many payment records.
-   A payment references a plan.
-   Payment foreign keys restrict deletion where historical records
    depend on the user/plan.
-   Gallery and credit rows are tied to users.
-   Unique indexes protect usernames/emails and Razorpay payment/order
    identifiers.
-   The schema uses InnoDB and UTF-8 MB4.

The seed statement inserts `default_encryption_limit = 5` only when the
key is absent. Re-importing the schema does not overwrite an
administrator's existing configured value.

------------------------------------------------------------------------

## 9. Local storage design

This edition deliberately stores generated encrypted PNGs on the
EC2/local machine rather than in a cloud object store.

### Encrypted image storage

-   Root directory: `ENCRYPTED_STORAGE_DIR` (default `private_storage`).
-   The storage service creates user-specific storage paths and returns
    a relative storage key.
-   The database stores the storage key in `gallery.image_path`, not the
    full public URL.
-   The directory is not exposed through Flask's static-file route.
-   A protected route checks login, ownership and expiry before
    streaming the image.
-   `chmod 700 private_storage` is recommended on Linux so only the
    application OS user can access the directory.

### Banner storage

-   Administrator-uploaded banners live in `instance/banners/`.
-   The active banner filename is stored in `site_settings`.
-   The bundled default banner is part of the repository and is the
    fallback.
-   `instance/` is ignored by Git because it contains runtime
    uploads/settings-related files.

### Retention

`ENCRYPTED_IMAGE_RETENTION_DAYS` controls the expiry date stored for new
gallery records. Normal gallery retrieval and download/preview
operations filter out expired records. Retention metadata does not mean
a scheduled cleanup job exists; filesystem/database cleanup should be
reviewed as a separate operational task if automatic physical deletion
of expired items is required.

------------------------------------------------------------------------

## 10. HTTP route reference

### Public and encryption routes (`app.py`)

  ---------------------------------------------------------------------------------
  Method                  Path                              Purpose
  ----------------------- --------------------------------- -----------------------
  GET                     `/`                               Home/encryption page

  GET                     `/SteogSecure_logo.png`           Project logo

  POST                    `/encrypt`                        Encrypt and download a
                                                            PNG

  GET                     `/encrypt/capacity`               Calculate image
                                                            capacity and estimated
                                                            file limit

  GET                     `/previous`                       Current user's previous
                                                            encrypted images

  GET                     `/previous/<image_id>/download`   Download a previous
                                                            encrypted PNG

  GET                     `/previous/<image_id>/file`       Protected image
                                                            response for preview

  POST                    `/previous/<image_id>/delete`     Delete a previous
                                                            gallery item

  GET                     `/decrypt`                        Decryption page

  POST                    `/decrypt/inspect`                Inspect encrypted PNG
                                                            metadata

  POST                    `/decrypt`                        Decrypt text or file

  GET                     `/site-banner`                    Active/default banner
                                                            response
  ---------------------------------------------------------------------------------

### Authentication/profile routes (`routes/auth_routes.py`)

  Method      Path                  Purpose
  ----------- --------------------- ------------------
  GET, POST   `/register`           Register account
  GET, POST   `/login`              User login
  GET         `/home`               User dashboard
  GET         `/profile`            Profile page
  POST        `/profile/username`   Change username
  POST        `/profile/password`   Change password
  POST        `/logout`             User logout

### Payment routes (`routes/payment_routes.py`)

  Method   Path                       Purpose
  -------- -------------------------- -----------------------------------
  GET      `/credits`                 Credit plans and purchase history
  POST     `/payments/create-order`   Create Razorpay order
  POST     `/payments/verify`         Verify payment and credit account

### Admin routes (`admin/admin_routes.py`)

All admin routes are prefixed with `/secure-console-x7k9`.

  ---------------------------------------------------------------------------------------------------------------
  Method                  Path                                                            Purpose
  ----------------------- --------------------------------------------------------------- -----------------------
  GET, POST               `/secure-console-x7k9/`                                         Admin login

  GET                     `/secure-console-x7k9/dashboard`                                Admin dashboard

  GET                     `/secure-console-x7k9/users`                                    User management page

  GET                     `/secure-console-x7k9/credit-plans`                             Credit plan page

  GET                     `/secure-console-x7k9/users/api`                                User list API

  POST                    `/secure-console-x7k9/users/<user_id>/status`                   Change user status

  POST                    `/secure-console-x7k9/users/<user_id>/credits`                  Change user credits

  GET                     `/secure-console-x7k9/credit-plans/api`                         Plan list API

  POST                    `/secure-console-x7k9/credit-plans`                             Create plan

  PUT                     `/secure-console-x7k9/credit-plans/<plan_id>`                   Update plan

  POST                    `/secure-console-x7k9/credit-plans/<plan_id>/status`            Change plan status

  DELETE                  `/secure-console-x7k9/credit-plans/<plan_id>`                   Delete plan

  GET                     `/secure-console-x7k9/revenue`                                  Revenue page

  GET                     `/secure-console-x7k9/revenue/api/summary`                      Revenue summary API

  GET                     `/secure-console-x7k9/revenue/api/transactions`                 Revenue transaction API

  GET                     `/secure-console-x7k9/settings`                                 System settings page

  GET                     `/secure-console-x7k9/settings/api/limit`                       Read default credit
                                                                                          limit

  POST                    `/secure-console-x7k9/settings/api/limit`                       Update default credit
                                                                                          limit

  GET                     `/secure-console-x7k9/settings/api/banners`                     List uploaded banners

  POST                    `/secure-console-x7k9/settings/api/banners`                     Upload banner

  POST                    `/secure-console-x7k9/settings/api/banners/<filename>/status`   Activate/deactivate
                                                                                          banner

  DELETE                  `/secure-console-x7k9/settings/api/banners/<filename>`          Delete uploaded banner

  GET                     `/secure-console-x7k9/settings/api/banners/<filename>/image`    Preview uploaded banner

  POST                    `/secure-console-x7k9/logout`                                   Admin logout
  ---------------------------------------------------------------------------------------------------------------

------------------------------------------------------------------------

## 11. Configuration reference

Create `.env` from `env.example`. Example keys:

``` dotenv
SECRET_KEY=replace_with_a_long_random_secret
COOKIE_SECURE=false

DB_HOST=localhost
DB_PORT=3306
DB_NAME=stego_secure
DB_USER=stego_user
DB_PASSWORD=replace_with_a_strong_database_password

MAX_UPLOAD_MB=50
ENCRYPTED_STORAGE_DIR=private_storage
ENCRYPTED_IMAGE_RETENTION_DAYS=30

RAZORPAY_KEY_ID=your_razorpay_test_key_id
RAZORPAY_KEY_SECRET=your_razorpay_test_key_secret
```

-   `SECRET_KEY` --- Required by Flask for session security. The app
    stops at startup if it is missing.
-   `COOKIE_SECURE` --- Keep `false` only for local HTTP testing. Set
    `true` when HTTPS is correctly configured.
-   `DB_*` --- MySQL connection information.
-   `MAX_UPLOAD_MB` --- Maximum total multipart request size, not just
    the secret file size.
-   `ENCRYPTED_STORAGE_DIR` --- Local private storage root.
-   `ENCRYPTED_IMAGE_RETENTION_DAYS` --- Retention interval used when
    new gallery records are created.
-   `RAZORPAY_*` --- Payment gateway credentials. Use test keys for test
    mode; do not commit real credentials.

Generate a Flask secret with:

``` bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Never commit `.env`, database passwords, Razorpay secrets, user
credentials or secret keys.

------------------------------------------------------------------------

## 12. Start the application for local development

Activate the project virtual environment, ensure the local `.env` and MySQL database are configured, and run the application in the foreground:

```bash
source venv/bin/activate
python app.py
```

The development entry point in this branch listens on `0.0.0.0:5000` with debug disabled. Stop it with `Ctrl+C`. Fresh EC2 installation, MySQL setup, environment configuration, admin creation, network rules and deployment verification are documented separately in `docs/EC2_DEPLOYMENT.md`.

------------------------------------------------------------------------

## 13. Security and operational notes

1.  **Keep encrypted storage private.** Do not configure
    `private_storage/` as a public static directory.
2.  **Use HTTPS in production.** Enable `COOKIE_SECURE=true` after TLS
    is configured.
3.  **Protect `.env`.** It contains the Flask secret, database
    credentials and payment secrets.
4.  **Keep the secret key/QA answer.** The server does not retain the
    encryption credential; losing it means losing access to that
    payload.
5.  **Preserve the output PNG.** Do not convert it to JPEG, resize it,
    recompress it or edit it.
6.  **Use strong QA answers.** Human-selected answers can be vulnerable
    to guessing if they are predictable.
7.  **Restrict network access.** Do not expose MySQL port 3306 to the
    public internet. Restrict SSH and direct testing port 5000 to
    trusted IPs.
8.  **Back up both database and files.** A usable gallery restore
    requires MySQL records and the corresponding `private_storage/`
    files.
9.  **Retention is metadata-driven.** Review cleanup/backup policy
    separately; expired records are filtered from normal gallery access.
10. **Razorpay secrets stay server-side.** Never place the secret key in
    browser JavaScript or commit it.
11. **Admin URL obscurity is not authorization.** The admin blueprint
    still relies on session checks and active-admin validation.
12. **Do not run multiple ad-hoc copies against one storage directory**
    without understanding shared database and filesystem ownership.

------------------------------------------------------------------------

## 14. Known implementation details to understand before changing code

-   The encryption route checks credits before doing expensive
    image/crypto work, then the gallery service performs the
    authoritative transactional decrement when recording the successful
    result.
-   The generated encrypted image is stored locally before the
    gallery/credit transaction. If the database transaction fails, the
    route deletes that just-written file.
-   Capacity estimates are advisory; the final serialized payload length
    is checked immediately before embedding.
-   The decryption inspection endpoint reveals only validated public
    metadata. It does not decrypt the payload or verify that the user
    knows the credential.
-   The gallery stores file metadata and a relative storage key; the
    actual PNG is on disk.
-   The active banner selection is stored in `site_settings`, while the
    banner bytes are in `instance/banners/`.
-   The default encryption limit applies when a user is registered.
    Changing the setting does not automatically rewrite existing
    balances.
-   Payment plan snapshots preserve the plan name/credit quantity
    associated with a transaction even if the plan is later edited.
-   The source has duplicate definitions for several gallery service
    function names. Python uses the last definition in the module.
    Review the effective final definitions before modifying that module.
-   The app uses CSRF protection globally. Any browser form or
    JavaScript request that performs a protected state-changing action
    must send the expected CSRF token/header.

------------------------------------------------------------------------

## 15. Suggested developer change map

  -------------------------------------------------------------------------
  If you want to change...            Start with...
  ----------------------------------- -------------------------------------
  Encryption algorithm, payload       `services/encryption_service.py`
  metadata or credential              
  normalization                       

  LSB bit layout, header, capacity or `services/steganography_service.py`
  extraction                          

  Cover/secret upload rules           `utils/validators.py`

  Encrypt/decrypt HTTP behavior       `app.py`

  Private encrypted PNG filesystem    `services/storage_service.py`
  behavior                            

  Previous-encryption history and     `services/gallery_service.py`,
  credit transaction                  `services/credit_service.py`

  User registration/login/password    `routes/auth_routes.py`,
  behavior                            `services/auth_service.py`

  Credit purchase/payment             `routes/payment_routes.py`,
  verification                        `services/payment_service.py`

  User/admin database connection      `db.py`, `.env`

  Admin authorization and admin       `admin/admin_auth.py`,
  endpoints                           `admin/admin_routes.py`

  Admin dashboard statistics          `admin/dashboard_service.py`

  Admin user/credit controls          `admin/user_service.py`

  Admin plans and popular plan        `admin/plan_service.py`

  Admin revenue and transactions      `admin/revenue_service.py`

  Default credits and banner settings `admin/settings_service.py`,
                                      `services/site_service.py`

  Database tables and constraints     `database/schema.sql`

  Flask cookie/upload settings        `config.py`

  Initial administrator provisioning  `create_admin.py`

  User/admin page markup              Corresponding files under
                                      `templates/`
  -------------------------------------------------------------------------

------------------------------------------------------------------------

## 16. Summary

StegoSecure's main pipeline is:

**User secret → validation → credential normalization/key decoding →
PBKDF2 key derivation → Fernet encryption → JSON payload → RGB LSB
embedding → PNG output → private local storage → gallery record + one
credit consumed.**

The reverse pipeline is:

**Encrypted PNG → PNG validation → LSB extraction → payload metadata
validation → credential input → PBKDF2 key derivation → Fernet
authentication/decryption → UTF-8 text or original file bytes.**

MySQL holds application state and metadata; the local filesystem holds
private encrypted PNGs and admin-uploaded banners. The modular backend
separates routes, services, validation, database access and templates so
each part can be understood and maintained independently.
