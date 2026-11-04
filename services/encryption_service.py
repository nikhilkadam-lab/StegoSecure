
import base64
import json
import os
import unicodedata

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from werkzeug.utils import secure_filename


PAYLOAD_VERSION = 1

KDF_NAME = "PBKDF2-HMAC-SHA256"
KDF_ITERATIONS = 600_000
KDF_SALT_BYTES = 16

MAX_SECRET_BYTES = 12 * 1024 * 1024
MAX_QUESTION_LENGTH = 500
MAX_FILENAME_LENGTH = 255

# Maximum serialized encrypted payload size.
MAX_ENCRYPTED_PAYLOAD_BYTES = 15 * 1024 * 1024

def _fernet_token_size(plaintext_size):
    """Calculate the exact Fernet token size for a plaintext length."""
    import math

    ciphertext_size = ((plaintext_size // 16) + 1) * 16
    token_size = 1 + 8 + 16 + ciphertext_size + 32

    # Fernet tokens are URL-safe Base64 encoded.
    return 4 * math.ceil(token_size / 3)


def estimate_file_payload_size(
    file_size,
    authentication_type="QA",
    filename="encrypted_file",
    question="",
):
    """
    Estimate the serialized encrypted payload size without encrypting data.
    """
    import math

    if file_size < 0:
        raise ValueError("Invalid file size.")

    authentication_type = authentication_type.upper()

    if authentication_type not in {"QA", "KEY"}:
        raise ValueError("Invalid authentication method.")

    safe_filename = secure_filename(filename) or "encrypted_file"

    # Base64 encoding of original file.
    encoded_size = 4 * math.ceil(file_size / 3)

    # Fernet encryption and token encoding.
    encrypted_size = _fernet_token_size(encoded_size)

    # JSON metadata size, matching encrypt_payload().
    metadata = {
        "version": PAYLOAD_VERSION,
        "encryption_type": authentication_type,
        "payload_type": "FILE",
        "payload_encoding": "base64",
        "kdf": {
            "name": KDF_NAME,
            "iterations": KDF_ITERATIONS,
            "salt": base64.b64encode(b"\0" * KDF_SALT_BYTES).decode("ascii"),
        },
        "encrypted_payload": "A" * encrypted_size,
        "filename": safe_filename,
    }

    if authentication_type == "QA":
        metadata["question"] = question.strip()

    return len(
        json.dumps(
            metadata,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def get_max_encryptable_file_size(
    image_capacity,
    authentication_type="QA",
    filename="encrypted_file",
    question="",
):
    """
    Calculate the maximum original file size that fits the image,
    respecting existing application safety limits.
    """
    low = 0
    high = MAX_SECRET_BYTES

    while low < high:
        middle = (low + high + 1) // 2

        estimated_size = estimate_file_payload_size(
            middle,
            authentication_type,
            filename,
            question,
        )

        if (
            estimated_size <= image_capacity
            and estimated_size <= MAX_ENCRYPTED_PAYLOAD_BYTES
        ):
            low = middle
        else:
            high = middle - 1

    return low


def _normalize_qa_answer(answer):
    """Normalize QA answers consistently before key derivation."""

    if not isinstance(answer, str):
        raise ValueError("Please enter your security answer.")

    answer = unicodedata.normalize("NFKC", answer).strip().casefold()

    if not answer:
        raise ValueError("Security answer cannot be empty.")

    if len(answer.encode("utf-8")) > 1024:
        raise ValueError("Security answer is too long.")

    return answer.encode("utf-8")


def _decode_secret_key(secret_key):
    """
    Decode the browser-generated URL-safe Base64 key.

    The decoded key must contain exactly 32 random bytes.
    """

    if not isinstance(secret_key, str) or not secret_key:
        raise ValueError("Please provide your secret key.")

    try:
        encoded = secret_key.encode("ascii")
        padded = encoded + b"=" * (-len(encoded) % 4)

        raw_key = base64.b64decode(
            padded,
            altchars=b"-_",
            validate=True,
        )

        if len(raw_key) != 32:
            raise ValueError("Invalid secret key.")

        return raw_key

    except (ValueError, UnicodeEncodeError) as exc:
        raise ValueError(
            "Invalid secret key. Please generate a new key."
        ) from exc


def _derive_fernet_key(password_bytes, salt):
    """Derive a Fernet-compatible key using PBKDF2-HMAC-SHA256."""

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )

    derived_key = kdf.derive(password_bytes)

    return base64.urlsafe_b64encode(derived_key)


def _prepare_secret_data(payload_type, data):
    """Prepare TEXT or FILE data for encryption."""

    if payload_type == "TEXT":
        if not isinstance(data, str):
            raise ValueError("Secret text must be a string.")

        plaintext = data.encode("utf-8")

        if not plaintext:
            raise ValueError("Secret text cannot be empty.")

        if len(plaintext) > MAX_SECRET_BYTES:
            raise ValueError("Secret text exceeds the maximum allowed size.")

        return plaintext, "utf-8"

    if payload_type == "FILE":
        if not isinstance(data, bytes):
            raise ValueError("Secret file data must be bytes.")

        if not data:
            raise ValueError("Secret file cannot be empty.")

        if len(data) > MAX_SECRET_BYTES:
            raise ValueError("Secret file exceeds the maximum allowed size.")

        encoded_data = base64.b64encode(data)

        return encoded_data, "base64"

    raise ValueError("Unsupported payload type.")


def encrypt_payload(
    payload_type,
    data,
    authentication_type,
    credential,
    question=None,
    filename=None,
):
    """
    Encrypt a TEXT or FILE payload and serialize its metadata as JSON.

    authentication_type:
        QA  - credential is the user's security answer.
        KEY - credential is the browser-generated Base64 key.

    Returns:
        UTF-8 encoded JSON bytes ready for image embedding.
    """

    payload_type = (
        payload_type.upper()
        if isinstance(payload_type, str)
        else ""
    )

    authentication_type = (
        authentication_type.upper()
        if isinstance(authentication_type, str)
        else ""
    )

    if payload_type not in {"TEXT", "FILE"}:
        raise ValueError("Unsupported payload type.")

    if authentication_type not in {"QA", "KEY"}:
        raise ValueError("Unsupported authentication type.")

    plaintext, payload_encoding = _prepare_secret_data(
        payload_type,
        data,
    )

    # Prepare the credential. Never store it in the payload.
    if authentication_type == "QA":
        password_bytes = _normalize_qa_answer(credential)

        if not isinstance(question, str):
            raise ValueError("Please select a security question.")

        question = question.strip()

        if not question or len(question) > MAX_QUESTION_LENGTH:
            raise ValueError("Please provide a valid security question.")

    else:
        password_bytes = _decode_secret_key(credential)
        question = None

    # FILE payloads must retain a safe original filename.
    safe_filename = None

    if payload_type == "FILE":
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError("Secret filename is required.")

        safe_filename = secure_filename(filename)

        if not safe_filename:
            raise ValueError("Invalid secret filename.")

        if len(safe_filename) > MAX_FILENAME_LENGTH:
            raise ValueError("Secret filename is too long.")

    # Generate a fresh salt for every encryption.
    salt = os.urandom(KDF_SALT_BYTES)

    fernet_key = _derive_fernet_key(password_bytes, salt)

    encrypted_data = Fernet(fernet_key).encrypt(plaintext)

    # Only public metadata and ciphertext are stored in the image.
    payload = {
        "version": PAYLOAD_VERSION,
        "encryption_type": authentication_type,
        "payload_type": payload_type,
        "payload_encoding": payload_encoding,
        "kdf": {
            "name": KDF_NAME,
            "iterations": KDF_ITERATIONS,
            "salt": base64.b64encode(salt).decode("ascii"),
        },
        "encrypted_payload": encrypted_data.decode("ascii"),
    }

    if authentication_type == "QA":
        payload["question"] = question

    if payload_type == "FILE":
        payload["filename"] = safe_filename

    payload_bytes = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    if len(payload_bytes) > MAX_ENCRYPTED_PAYLOAD_BYTES:
        raise ValueError(
            "Encrypted payload exceeds the maximum allowed size."
        )

    return payload_bytes


def inspect_payload(payload_bytes):
    """Inspect and validate the public metadata of an encrypted payload."""

    if not isinstance(payload_bytes, bytes) or not payload_bytes:
        raise ValueError("No encrypted payload was found.")

    if len(payload_bytes) > MAX_ENCRYPTED_PAYLOAD_BYTES:
        raise ValueError("Encrypted payload exceeds the allowed size.")

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError(
            "This image does not contain a valid StegoSecure payload."
        )

    if not isinstance(payload, dict) or payload.get("version") != PAYLOAD_VERSION:
        raise ValueError("Unsupported or invalid encrypted payload.")

    auth_type = payload.get("encryption_type")
    payload_type = payload.get("payload_type")

    if auth_type not in {"QA", "KEY"}:
        raise ValueError("Invalid authentication metadata.")

    if payload_type not in {"TEXT", "FILE"}:
        raise ValueError("Invalid payload metadata.")

    kdf_info = payload.get("kdf")

    if not isinstance(kdf_info, dict):
        raise ValueError("Invalid encryption metadata.")

    if (
        kdf_info.get("name") != KDF_NAME
        or kdf_info.get("iterations") != KDF_ITERATIONS
    ):
        raise ValueError("Unsupported encryption settings.")

    try:
        salt = base64.b64decode(
            kdf_info.get("salt", ""),
            validate=True,
        )
    except (ValueError, TypeError):
        raise ValueError("Invalid encryption salt.")

    if len(salt) != KDF_SALT_BYTES:
        raise ValueError("Invalid encryption salt.")

    encrypted_data = payload.get("encrypted_payload")

    if not isinstance(encrypted_data, str) or not encrypted_data:
        raise ValueError("Encrypted data is missing.")

    if len(encrypted_data) > MAX_ENCRYPTED_PAYLOAD_BYTES:
        raise ValueError("Encrypted data exceeds the allowed size.")

    if auth_type == "QA":
        question = payload.get("question")

        if (
            not isinstance(question, str)
            or not question.strip()
            or len(question) > MAX_QUESTION_LENGTH
        ):
            raise ValueError("Invalid security question.")
    else:
        question = None

    if payload_type == "FILE":
        filename = payload.get("filename")

        if not isinstance(filename, str) or not filename:
            raise ValueError("Original filename is missing.")

        filename = secure_filename(filename)

        if not filename or len(filename) > MAX_FILENAME_LENGTH:
            raise ValueError("Invalid original filename.")
    else:
        filename = None

    return {
        "authentication_type": auth_type,
        "payload_type": payload_type,
        "question": question,
        "filename": filename,
    }


def decrypt_payload(payload_bytes, credential):
    """Decrypt a StegoSecure payload using its original credential."""

    metadata = inspect_payload(payload_bytes)
    payload = json.loads(payload_bytes.decode("utf-8"))

    if metadata["authentication_type"] == "QA":
        password_bytes = _normalize_qa_answer(credential)
    else:
        password_bytes = _decode_secret_key(credential)

    salt = base64.b64decode(payload["kdf"]["salt"])

    fernet_key = _derive_fernet_key(password_bytes, salt)

    try:
        decrypted_data = Fernet(fernet_key).decrypt(
            payload["encrypted_payload"].encode("ascii")
        )
    except (InvalidToken, ValueError):
        raise ValueError(
            "Incorrect answer or secret key, or the image is corrupted."
        )

    if metadata["payload_type"] == "TEXT":
        try:
            result = decrypted_data.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("Decrypted text is invalid.")

    else:
        try:
            result = base64.b64decode(decrypted_data, validate=True)
        except (ValueError, TypeError):
            raise ValueError("Decrypted file data is invalid.")

        if len(result) > MAX_SECRET_BYTES:
            raise ValueError("Decrypted file exceeds the allowed size.")

    return {
        **metadata,
        "data": result,
    }
