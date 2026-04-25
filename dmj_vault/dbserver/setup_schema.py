#!/usr/bin/python3


def main():
    initial_setup()
    apply_migrations()


def initial_setup():
    from dmj_vault.dbserver.db import get_db_cursor
    cursor = get_db_cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS `API_KEY` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `uid` char(128) NOT NULL,
            `permissions` text NOT NULL,
            `is_valid` tinyint(1) NOT NULL DEFAULT 0,
            `ts_created` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `ts_expires` datetime DEFAULT NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uid` (`uid`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
    """)
    cursor.fetchall()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS `ADMIN` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `login` char(128) NOT NULL,
            `password` char(255) NOT NULL DEFAULT '*',
            PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
    """)
    cursor.fetchall()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS `IP_WHITELIST` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `api_key_id` int(11) NOT NULL,
            `src_ip_address` char(45) NOT NULL,
            PRIMARY KEY (`id`),
            KEY `api_key_id` (`api_key_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
    """)
    cursor.fetchall()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS `_VERSION` (
            `id` int(11) NOT NULL,
            `migration` char(128) DEFAULT NULL,
            `dt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
                                   ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
    """)
    cursor.fetchall()

    cursor.execute("SELECT * FROM `_VERSION`;")
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO `_VERSION` (`id`, `migration`) VALUES (1, '0');")
        cursor.fetchall()

    cursor.close()


def apply_migrations():
    from dmj_vault.dbserver.db import get_db_cursor
    cursor = get_db_cursor()

    cursor.execute("SELECT * FROM `_VERSION` WHERE id = 1;")
    row = cursor.fetchone()

    import os
    migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
    latest_applied_migration = os.path.join(migrations_dir, row[1])
    print("Latest applied migration:", latest_applied_migration)

    migrations = [
        os.path.join(migrations_dir, f)
        for f in os.listdir(migrations_dir)
        if os.path.isfile(os.path.join(migrations_dir, f))
           and os.path.join(migrations_dir, f) > latest_applied_migration
    ]
    migrations.sort()
    print("New migrations:", migrations)

    import subprocess
    for migration in migrations:
        print("Applying '%s' migration." % migration)
        subprocess.run(['python3', migration], check=True)
        cursor.execute(
            "UPDATE `_VERSION` SET migration='%s' WHERE id = 1;"
            % os.path.basename(migration))
        cursor.fetchall()
        print("Migration '%s' successfully applied." % migration)

    cursor.close()


if __name__ == '__main__':
    main()
