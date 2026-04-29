#!/usr/bin/python3


def main():
    from dmj_vault.dbserver.db import get_db_cursor
    cursor = get_db_cursor()
    cursor.execute(
        "ALTER TABLE `API_KEY` ADD COLUMN `name` varchar(255) NOT NULL DEFAULT '' AFTER `uid`;"
    )
    cursor.fetchall()
    cursor.close()


if __name__ == '__main__':
    main()
