#!/usr/bin/python3
import os

CONFIG_FILE = '/etc/dmj-vault-apps-admin/conf'
CONF_D_DIR = '/etc/dmj-vault-apps-admin/conf.d'


def read_config():
    config = {
        'PORT': '9701',
        'HOST': '127.0.0.1',
        'WORKERS': '2',
    }

    def parse_file(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, _, value = line.partition('=')
                    config[key.strip()] = value.strip()

    if os.path.isfile(CONFIG_FILE):
        parse_file(CONFIG_FILE)

    if os.path.isdir(CONF_D_DIR):
        for fname in sorted(os.listdir(CONF_D_DIR)):
            if fname.endswith('.conf'):
                parse_file(os.path.join(CONF_D_DIR, fname))

    return config


def main():
    config = read_config()
    host = config['HOST']
    port = config['PORT']
    workers = config['WORKERS']

    os.execv('/usr/bin/gunicorn', [
        'gunicorn',
        'dmj_vault.apps.admin.wsgi:app',
        '--bind', f'{host}:{port}',
        '--workers', workers,
    ])
