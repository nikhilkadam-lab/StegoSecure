
import mimetypes
from io import BytesIO
from pathlib import Path

from flask import (
    Flask,
    redirect,
    url_for,
    render_template,
    send_from_directory,
    request,
    session,
    flash,
    send_file,
    jsonify,
)

from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename
from PIL import Image

from config import BASE_DIR, Config
from services.site_service import get_active_banner

from services.encryption_service import (
    encrypt_payload,
    inspect_payload,
    decrypt_payload,
    get_max_encryptable_file_size,
    MAX_SECRET_BYTES,
)

from services.steganography_service import (
    embed_payload,
    extract_payload,
    get_image_capacity,
)

from utils.validators import (
    validate_cover_image,
    validate_secret_file,
    MAX_IMAGE_PIXELS,
)


app = Flask(__name__)
app.config.from_object(Config)

if not app.config.get("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY is missing from the .env file.")

if app.config["MAX_CONTENT_LENGTH"] <= 0:
    raise RuntimeError("MAX_UPLOAD_MB must be greater than zero.")

CSRFProtect(app)

from routes.auth_routes import auth_bp

app.register_blueprint(auth_bp)


def load_encrypted_png(uploaded):
    """
    Validate and load an encrypted PNG image.

    Uses the existing image validator to enforce the configured
    image-format and pixel-count restrictions.
    """
    validate_cover_image(uploaded)

    uploaded.stream.seek(0)

    with Image.open(uploaded.stream) as image:
        if image.format != "PNG":
            raise ValueError("Please upload the original encrypted PNG.")

        image.load()
        return image.convert("RGB")


@app.route("/")
def home():
    return render_template(
        "home.html",
        banner_url=url_for("site_banner"),
    )


@app.route("/encrypt", methods=["POST"])
def encrypt():
    if "user_id" not in session:
        flash("Please log in before encrypting data.", "error")
        return redirect(
            url_for(
                "auth.login",
                next=url_for("home", _anchor="encryption"),
            )
        )

    try:
        # 1. Validate and load the cover image
        cover = request.files.get("cover_image")

        validate_cover_image(cover)

        with Image.open(cover.stream) as source:
            source.load()
            cover_image = source.convert("RGB")

        # Calculate actual available payload capacity.
        # This excludes the 4-byte steganography header.
        image_capacity = get_image_capacity(cover_image)

        if image_capacity <= 0:
            raise ValueError("The selected image has no usable embedding capacity.")

        # 2. Read secret data
        payload_type = request.form.get("payload_type", "").upper()
        filename = None

        if payload_type == "TEXT":
            secret_data = request.form.get("secret_text", "")

            if not secret_data.strip():
                raise ValueError("Please enter your secret text.")

        elif payload_type == "FILE":
            secret_file = request.files.get("secret_file")

            file_info = validate_secret_file(
                secret_file,
                max_bytes=MAX_SECRET_BYTES,
            )

            filename = file_info["filename"]

            # Ensure reading starts at the beginning of the uploaded file.
            secret_file.stream.seek(0)
            secret_data = secret_file.read()

            if not secret_data:
                raise ValueError("The selected file is empty.")

        else:
            raise ValueError("Invalid data type selected.")

        # 3. Read authentication details
        auth_type = request.form.get("authentication_type", "").upper()

        if auth_type == "QA":
            credential = request.form.get("security_answer", "")
            question_choice = request.form.get("security_question", "")

            if question_choice == "custom":
                question = request.form.get("custom_question", "").strip()
            else:
                question = question_choice.strip()

            if not credential.strip() or not question:
                raise ValueError(
                    "Please provide your security question and answer."
                )

        elif auth_type == "KEY":
            credential = request.form.get("secret_key", "")
            question = None

            if not credential.strip():
                raise ValueError("Please provide your secret key.")

        else:
            raise ValueError("Invalid authentication method.")

        # 4. Encrypt the secret data
        encrypted_payload = encrypt_payload(
            payload_type=payload_type,
            data=secret_data,
            authentication_type=auth_type,
            credential=credential,
            question=question,
            filename=filename,
        )

        # 5. Check actual encrypted payload size against image capacity.
        # This is authoritative; frontend estimates are only advisory.
        if len(encrypted_payload) > image_capacity:
            raise ValueError(
                "Image capacity insufficient. "
                f"Available: {image_capacity / (1024 * 1024):.2f} MB; "
                f"Required: {len(encrypted_payload) / (1024 * 1024):.2f} MB."
            )

        # 6. Embed encrypted payload into the cover image
        stego_image = embed_payload(
            cover_image,
            encrypted_payload,
        )

        # 7. Prepare downloadable PNG
        requested_name = request.form.get("output_name", "").strip()

        if not requested_name:
            requested_name = Path(cover.filename or "stegosecure").stem

        output_name = secure_filename(requested_name)

        if output_name.lower().endswith(".png"):
            output_name = output_name[:-4]

        if not output_name:
            output_name = "stegosecure_encrypted"

        output = BytesIO()
        stego_image.save(output, format="PNG")
        output.seek(0)

        return send_file(
            output,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{output_name}.png",
        )

    except ValueError as exc:
        app.logger.warning("Encryption validation failed: %s", exc)
        flash(str(exc), "encryption_error")
        return redirect(url_for("home", _anchor="encryption"))

    except Exception:
        app.logger.exception("Encryption operation failed")
        flash("Encryption failed. Please try again.", "error")
        return redirect(url_for("home", _anchor="encryption"))


@app.route("/encrypt/capacity", methods=["GET"])
def encrypt_capacity():
    try:
        width = int(request.args.get("width", 0))
        height = int(request.args.get("height", 0))

        auth_type = request.args.get("authentication_type", "QA").upper()
        filename = request.args.get("filename", "encrypted_file")
        question = request.args.get("question", "")

        if width <= 0 or height <= 0:
            raise ValueError("Invalid image dimensions.")

        if width * height > MAX_IMAGE_PIXELS:
            raise ValueError("Image exceeds the maximum allowed dimensions.")

        if auth_type not in {"QA", "KEY"}:
            raise ValueError("Invalid authentication method.")

        if len(filename) > 255 or len(question) > 500:
            raise ValueError("Invalid capacity estimation parameters.")

        # Calculate actual usable embedding capacity.
        image_capacity = max(
            0,
            (width * height * 3) // 8 - 4
        )

        # Calculate maximum original file size that can fit.
        max_file_bytes = get_max_encryptable_file_size(
            image_capacity=image_capacity,
            authentication_type=auth_type,
            filename=filename,
            question=question,
        )

        return jsonify({
            "success": True,
            "image_capacity_bytes": image_capacity,
            "max_file_bytes": max_file_bytes,
            "max_file_mb": round(
                max_file_bytes / (1024 * 1024), 2
            ),
        })

    except (ValueError, TypeError) as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 400

    except Exception:
        app.logger.exception("Capacity estimation failed")
        return jsonify({
            "success": False,
            "error": "Unable to calculate image capacity.",
        }), 500



@app.route("/decrypt", methods=["GET"])
def decryption_page():
    if "user_id" not in session:
        return redirect(
            url_for("auth.login", next=url_for("decryption_page"))
        )

    return render_template("decryption.html")


@app.route("/decrypt/inspect", methods=["POST"])
def decrypt_inspect():
    if "user_id" not in session:
        return jsonify({"error": "Please log in first."}), 401

    try:
        # 1. Validate and load encrypted PNG
        uploaded = request.files.get("encrypted_image")

        if not uploaded or not uploaded.filename:
            raise ValueError("Please select an encrypted image.")

        stego_image = load_encrypted_png(uploaded)

        # 2. Extract embedded payload
        payload_bytes = extract_payload(stego_image)

        # 3. Inspect payload metadata
        metadata = inspect_payload(payload_bytes)

        return jsonify({
            "success": True,
            "authentication_type": metadata["authentication_type"],
            "payload_type": metadata["payload_type"],
            "question": metadata["question"],
            "filename": metadata["filename"],
        })

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    except Exception:
        app.logger.exception("Encrypted image inspection failed")
        return jsonify({
            "error": "Unable to inspect this image."
        }), 500


@app.route("/decrypt", methods=["POST"])
def decrypt():
    if "user_id" not in session:
        return jsonify({"error": "Please log in first."}), 401

    try:
        # 1. Validate and load encrypted PNG
        uploaded = request.files.get("encrypted_image")

        if not uploaded or not uploaded.filename:
            raise ValueError("Please upload an encrypted image.")

        stego_image = load_encrypted_png(uploaded)

        # 2. Extract embedded payload
        payload_bytes = extract_payload(stego_image)

        # 3. Read authentication credential
        credential = request.form.get("credential", "")

        if not credential:
            raise ValueError("Please enter your answer or secret key.")

        # 4. Decrypt payload
        result = decrypt_payload(payload_bytes, credential)

        # 5. Return decrypted text or file
        if result["payload_type"] == "TEXT":
            return jsonify({
                "success": True,
                "payload_type": "TEXT",
                "data": result["data"],
            })

        filename = secure_filename(result["filename"])

        if not filename:
            filename = "decrypted_file"

        mime_type = (
            mimetypes.guess_type(filename)[0]
            or "application/octet-stream"
        )

        response = send_file(
            BytesIO(result["data"]),
            mimetype=mime_type,
            as_attachment=False,
            download_name=filename,
        )

        response.headers["X-File-Name"] = filename
        response.headers["X-File-Mime"] = mime_type

        return response

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    except Exception:
        app.logger.exception("Decryption failed")
        return jsonify({
            "error": "Decryption failed. Please try again."
        }), 500


@app.route("/site-banner")
def site_banner():
    filename = get_active_banner()

    if filename:
        banner_directory = Path(app.instance_path) / "banners"
        banner_path = banner_directory / filename

        if banner_path.is_file():
            return send_from_directory(
                str(banner_directory),
                filename,
            )

    # Default banner when no admin banner exists.
    return send_from_directory(
        str(BASE_DIR),
        "StegoSecure Banner.png",
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
    )
