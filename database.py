import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def database_config(include_database=True):
    config = {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", "Uday@2006"),
    }
    if include_database:
        config["database"] = os.getenv("MYSQL_DATABASE", "studenthub")
    return config


def get_connection():
    return mysql.connector.connect(**database_config())
