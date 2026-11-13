import json
import os
import urllib.error
import urllib.request


def send_email(to_email, subject, html_content, text_content=None):
    """
    Send a transactional email using the provider selected in .env.
    Currently supported: Brevo.
    """
    provider = os.getenv("EMAIL_PROVIDER", "brevo").strip().lower()

    if provider != "brevo":
        raise RuntimeError(
            f"Email provider '{provider}' is not implemented yet."
        )

    api_key = os.getenv("BREVO_API_KEY", "").strip()
    sender_email = os.getenv("EMAIL_FROM_ADDRESS", "").strip()
    sender_name = os.getenv("EMAIL_FROM_NAME", "StegoSecure").strip()

    if not api_key or not sender_email:
        raise RuntimeError("Brevo email configuration is incomplete.")

    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }

    if text_content:
        payload["textContent"] = text_content

    request = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status not in (200, 201, 202):
                raise RuntimeError(
                    f"Brevo returned unexpected status {response.status}."
                )
    except urllib.error.HTTPError as exc:
        # Do not log or expose the API key or provider response body.
        raise RuntimeError(
            f"Brevo rejected the email request (HTTP {exc.code})."
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Unable to connect to the email provider.") from exc
