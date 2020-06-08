import locale
import os

SECRET = "sikretfordevonly"
JWT_ALGORITHM = "HS256"
REQUIRE_TOKEN = False
SEND_EMAILS = False
SMTP_HOST = "mail.gandi.net"
SMTP_PASSWORD = ""
SMTP_LOGIN = ""
FROM_EMAIL = "contact@egapro.org"
LOCALE = "fr_FR.UTF-8"
SITE_DESCRIPTION = "Egapro"
EMAIL_SIGNATURE = "Egapro"
DBNAME = "egapro"
DBHOST = "localhost"
DBUSER = "postgres"
DBPASS = "postgres"
DBMAXSIZE = 10


def init():
    for key, value in globals().items():
        if key.isupper():
            env_key = "EGAPRO_" + key
            typ = type(value)
            if typ == list:
                typ = lambda x: x.split()
            if env_key in os.environ:
                globals()[key] = typ(os.environ[env_key])
    locale.setlocale(locale.LC_ALL, LOCALE)


init()
