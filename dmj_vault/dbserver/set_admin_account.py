#!/usr/bin/python3
import getpass
import os
import sys


def main():
    if os.geteuid() != 0:
        print("Error: this command must be run as root.", file=sys.stderr)
        sys.exit(1)

    login = input("Admin login: ").strip()
    if not login:
        print("Error: login cannot be empty.", file=sys.stderr)
        sys.exit(1)

    password = getpass.getpass("Admin password: ")
    if not password:
        print("Error: password cannot be empty.", file=sys.stderr)
        sys.exit(1)

    from werkzeug.security import generate_password_hash
    password_hash = generate_password_hash(password)

    from dmj_vault.dbserver.db import get_db_cursor
    cursor = get_db_cursor()

    cursor.execute("DELETE FROM `ADMIN`;")
    cursor.fetchall()
    cursor.execute(
        "INSERT INTO `ADMIN` (`login`, `password`) VALUES (%s, %s);",
        (login, password_hash))
    cursor.fetchall()
    cursor.close()

    print("Admin account set successfully.")


if __name__ == '__main__':
    main()
