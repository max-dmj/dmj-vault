#!/usr/bin/python3
import os
import sys

REQUIRED = ('HOST', 'PORT', 'WORKERS')


def main():
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        sys.exit("%s not set -- run the dmj-vault-apps-admin role"
                 % ', '.join(missing))

    os.execv('/usr/bin/gunicorn', [
        'gunicorn',
        'dmj_vault.apps.admin.wsgi:app',
        '--bind', f"{os.environ['HOST']}:{os.environ['PORT']}",
        '--workers', os.environ['WORKERS'],
    ])
