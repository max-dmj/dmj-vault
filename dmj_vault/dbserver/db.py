import os
import sys

CONFIG_FILE = '/etc/dmj-vault-dbserver/conf'
CONF_D_DIR = '/etc/dmj-vault-dbserver/conf.d'
KEY_FILE = '/etc/dmj-vault-dbserver/key'

REQUIRED = ('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASS')


def read_config():
    config = {}

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
    if os.path.isfile(KEY_FILE):
        parse_file(KEY_FILE)
    if os.path.isdir(CONF_D_DIR):
        for fname in sorted(os.listdir(CONF_D_DIR)):
            if fname.endswith('.conf'):
                parse_file(os.path.join(CONF_D_DIR, fname))

    missing = [k for k in REQUIRED if not config.get(k)]
    if missing:
        sys.exit("%s not set in %s or %s -- run the dmj-vault-dbserver role"
                 % (', '.join(missing), CONFIG_FILE, KEY_FILE))

    return config


def get_db_cursor():
    import MySQLdb as mysql
    cfg = read_config()
    connection = mysql.connect(
        host=cfg['DB_HOST'],
        port=int(cfg['DB_PORT']),
        db=cfg['DB_NAME'],
        user=cfg['DB_USER'],
        passwd=cfg['DB_PASS'],
        autocommit=True)
    return connection.cursor()
