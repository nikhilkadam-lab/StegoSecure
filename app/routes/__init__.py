from flask import Blueprint

main_bp = Blueprint("main", __name__)


@main_bp.get("/health")
def health():
    return {"status": "ok"}