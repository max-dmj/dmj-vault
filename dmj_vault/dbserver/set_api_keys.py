#!/usr/bin/python3
import argparse
import getpass
import json
import os
import sys
from datetime import datetime

FIELDS = {'name', 'uid', 'permissions', 'is_valid', 'ts_created', 'ts_expires', 'whitelist'}
TS_FORMATS = ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d')


def main():
    args = parse_args()

    if os.geteuid() != 0:
        die("this command must be run as root.")

    from_stdin = args.spec is sys.stdin
    keys = parse_spec(read_spec(args.spec))
    login, password = credentials(from_stdin)

    from dmj_vault.dbserver.db import get_db_cursor
    cursor = get_db_cursor()
    authenticate(cursor, login, password)
    deleted = replace_keys(cursor, keys)
    cursor.close()

    print("keys=%d deleted=%d" % (len(keys), deleted))


def parse_args():
    parser = argparse.ArgumentParser(
        prog='dmj-vault-set-api-keys',
        description="Replace the entire API_KEY table with the keys in a JSON spec. "
                    "Every key and IP whitelist entry not in the spec is deleted.",
        epilog="Admin credentials come from VAULT_ADMIN_LOGIN and VAULT_ADMIN_PASSWORD, "
               "or are prompted for. Reading the spec from stdin consumes the terminal, "
               "so both variables are required in that case.")
    parser.add_argument(
        'spec', metavar='SPEC', type=argparse.FileType('r'),
        help="JSON key spec; - reads stdin")
    return parser.parse_args()


def die(message):
    print("Error: %s" % message, file=sys.stderr)
    sys.exit(1)


def read_spec(stream):
    try:
        raw = stream.read()
    except OSError as exc:
        die("cannot read spec: %s" % exc)

    try:
        return json.loads(raw)
    except ValueError as exc:
        die("spec is not valid JSON: %s" % exc)


def parse_spec(doc):
    if not isinstance(doc, dict) or not isinstance(doc.get('keys'), list):
        die("spec must be an object with a 'keys' list.")

    keys = []
    names = set()
    uids = set()

    for entry in doc['keys']:
        if not isinstance(entry, dict):
            die("each entry of 'keys' must be an object.")

        unknown = set(entry) - FIELDS
        if unknown:
            die("key '%s': unknown field(s) %s."
                % (entry.get('name', '?'), ', '.join(sorted(unknown))))

        name = str(entry.get('name', '')).strip()
        if not name or len(name) > 255:
            die("key name must be non-empty and at most 255 characters.")
        if name in names:
            die("key '%s': duplicate name." % name)
        names.add(name)

        uid = str(entry.get('uid', '')).strip()
        if not uid or len(uid) > 128:
            die("key '%s': uid must be non-empty and at most 128 characters." % name)
        if uid in uids:
            die("key '%s': duplicate uid." % name)
        uids.add(uid)

        permissions = entry.get('permissions')
        if not isinstance(permissions, dict) or not permissions:
            die("key '%s': permissions must be a non-empty object." % name)
        for scope, access in permissions.items():
            if access not in ('read', 'write'):
                die("key '%s': scope '%s' must grant 'read' or 'write'." % (name, scope))

        is_valid = entry.get('is_valid', True)
        if not isinstance(is_valid, bool):
            die("key '%s': is_valid must be true or false." % name)

        whitelist = entry.get('whitelist', [])
        if not isinstance(whitelist, list):
            die("key '%s': whitelist must be a list of IP addresses." % name)
        for ip in whitelist:
            if not isinstance(ip, str) or not ip.strip() or len(ip.strip()) > 45:
                die("key '%s': whitelist entries must be non-empty IP addresses." % name)

        ts_created = timestamp(name, 'ts_created', entry.get('ts_created'))
        keys.append({
            'name': name,
            'uid': uid,
            'permissions': json.dumps(permissions, sort_keys=True),
            'is_valid': int(is_valid),
            'ts_created': ts_created if ts_created else datetime.now(),
            'ts_expires': timestamp(name, 'ts_expires', entry.get('ts_expires')),
            'whitelist': sorted({ip.strip() for ip in whitelist}),
        })

    return keys


def timestamp(name, field, value):
    if value is None:
        return None
    for fmt in TS_FORMATS:
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            pass
    die("key '%s': %s must be YYYY-MM-DD HH:MM:SS." % (name, field))


def credentials(from_stdin):
    login = os.environ.get('VAULT_ADMIN_LOGIN')
    password = os.environ.get('VAULT_ADMIN_PASSWORD')

    # The spec has consumed stdin, so there is no terminal left to prompt on.
    if from_stdin and not (login and password):
        die("VAULT_ADMIN_LOGIN/VAULT_ADMIN_PASSWORD are required "
            "when the spec is read from stdin.")

    login = login or input("Admin login: ").strip()
    if not login:
        die("login cannot be empty.")

    password = password or getpass.getpass("Admin password: ")
    if not password:
        die("password cannot be empty.")

    return login, password


def authenticate(cursor, login, password):
    from werkzeug.security import check_password_hash

    cursor.execute("SELECT `login`, `password` FROM `ADMIN`;")
    row = cursor.fetchone()
    if row is None:
        die("no admin account is set; run dmj-vault-set-admin-account first.")

    try:
        valid = row[0] == login and check_password_hash(row[1], password)
    except ValueError:
        valid = False

    if not valid:
        die("invalid admin credentials.")


def replace_keys(cursor, keys):
    import MySQLdb

    cursor.execute("SELECT COUNT(*) FROM `API_KEY`;")
    deleted = cursor.fetchone()[0]

    cursor.execute("START TRANSACTION;")
    try:
        cursor.execute("DELETE FROM `IP_WHITELIST`;")
        cursor.execute("DELETE FROM `API_KEY`;")

        for key in keys:
            cursor.execute(
                "INSERT INTO `API_KEY` "
                "(`uid`, `name`, `permissions`, `is_valid`, `ts_created`, `ts_expires`) "
                "VALUES (%s, %s, %s, %s, %s, %s);",
                (key['uid'], key['name'], key['permissions'],
                 key['is_valid'], key['ts_created'], key['ts_expires']))
            api_key_id = cursor.lastrowid

            for ip in key['whitelist']:
                cursor.execute(
                    "INSERT INTO `IP_WHITELIST` (`api_key_id`, `src_ip_address`) "
                    "VALUES (%s, %s);",
                    (api_key_id, ip))

        cursor.execute("COMMIT;")
    except MySQLdb.Error as exc:
        cursor.execute("ROLLBACK;")
        die("database error, no keys were changed: %s" % exc)

    return deleted


if __name__ == '__main__':
    main()
