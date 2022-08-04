import mariadb

from ..strings import errors


def get_db(settings):
    conn_params = {
        "user": settings.ScAdmin.db_user,
        "password": settings.ScAdmin.db_password,
        "host": settings.ScAdmin.db_host,
        "database": settings.ScAdmin.db_name,
    }
    try:
        conn = mariadb.connect(**conn_params)
    except mariadb.Error as err:
        print(errors["DB_CONNECTION_ERROR"].format(err))
        exit(1)
    else:
        return conn
