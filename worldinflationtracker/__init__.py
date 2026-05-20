from .celery import app as celery_app

__all__ = ('celery_app',)

# Use PyMySQL as MySQLdb replacement (no system libraries needed)
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass
