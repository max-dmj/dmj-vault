#!/usr/bin/python3
import os
import subprocess

CONFIG_FILE = '/etc/dmj-vault-apps-api/conf'
CONF_D_DIR = '/etc/dmj-vault-apps-api/conf.d'

NGINX_SITE = '/etc/nginx/sites-available/dmj-vault-apps-api'
NGINX_ENABLED = '/etc/nginx/sites-enabled/dmj-vault-apps-api'


def read_config():
    config = {
        'GUNICORN_PORT': '9702',
        'GUNICORN_HOST': '127.0.0.1',
        'GUNICORN_WORKERS': '4',
        'NGINX_PORT': '9800',
        'NGINX_HOST': '127.0.0.1',
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


def update_nginx_main():
    config = read_config()
    nginx_host = config['NGINX_HOST']
    nginx_port = config['NGINX_PORT']
    gunicorn_host = config['GUNICORN_HOST']
    gunicorn_port = config['GUNICORN_PORT']

    nginx_config = (
        f"server {{\n"
        f"    listen {nginx_host}:{nginx_port};\n"
        f"    location / {{\n"
        f"        proxy_pass http://{gunicorn_host}:{gunicorn_port};\n"
        f"        proxy_set_header X-Real-IP $remote_addr;\n"
        f"        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
        f"    }}\n"
        f"}}\n"
    )

    with open(NGINX_SITE, 'w') as f:
        f.write(nginx_config)

    if not os.path.islink(NGINX_ENABLED):
        os.symlink(NGINX_SITE, NGINX_ENABLED)

    subprocess.run(['nginx', '-t'], check=True)
    subprocess.run(['nginx', '-s', 'reload'], check=True)


def main():
    config = read_config()
    host = config['GUNICORN_HOST']
    port = config['GUNICORN_PORT']
    workers = config['GUNICORN_WORKERS']

    os.execv('/usr/bin/gunicorn', [
        'gunicorn',
        'dmj_vault.apps.api.wsgi:app',
        '--worker-class', 'uvicorn.workers.UvicornWorker',
        '--bind', f'{host}:{port}',
        '--workers', workers,
    ])
