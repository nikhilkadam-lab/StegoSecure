import os

import mysql.connector

from config import BASE_DIR
from dotenv import load_dotenv


# Use the same project-level .env file as Flask.
load_dotenv(BASE_DIR / ".env")


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "stego_secure"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        charset="utf8mb4",
        connection_timeout=5,
    )