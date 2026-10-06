from pathlib import Path

import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash

from database import database_config


def main():
    script = Path("Database.sql").read_text(encoding="utf-8-sig")
    connection = mysql.connector.connect(**database_config(include_database=False))
    cursor = connection.cursor()
    try:
        for statement in script.split(";"):
            if not statement.strip():
                continue
            try:
                cursor.execute(statement)
            except Error as error:
                # Schema setup is repeatable: existing columns/keys are expected.
                if error.errno not in {1050, 1060, 1061, 1826}:
                    raise

        cursor.execute("SELECT id FROM users WHERE username = %s", ("admin",))
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO users (username, password_hash, full_name, role) VALUES (%s, %s, %s, %s)",
                ("admin", generate_password_hash("admin123"), "System Administrator", "admin"),
            )
        connection.commit()
        print("StudentHub database is ready. Initial admin sign-in: admin / admin123")
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    main()
