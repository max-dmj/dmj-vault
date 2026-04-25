DB_CONFIG = {'SERVER': '127.0.0.1', 'DBNAME': 'DMJ_VAULT', 'USER': 'vault_admin', 'PASSWORD': ''}


def get_db_cursor():
    import MySQLdb as mysql
    connection = mysql.connect(
        host=DB_CONFIG['SERVER'],
        db=DB_CONFIG['DBNAME'],
        user=DB_CONFIG['USER'],
        passwd=DB_CONFIG['PASSWORD'],
        autocommit=True)
    return connection.cursor()
