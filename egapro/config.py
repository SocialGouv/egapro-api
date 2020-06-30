import os

SECRET = "sikretfordevonly"
JWT_ALGORITHM = "HS256"
REQUIRE_TOKEN = False
SEND_EMAILS = False
SMTP_HOST = "mail.gandi.net"
SMTP_PASSWORD = ""
SMTP_LOGIN = ""
FROM_EMAIL = "contact@egapro.org"
SITE_DESCRIPTION = "Egapro"
EMAIL_SIGNATURE = "Egapro"
DBNAME = "egapro"
DBHOST = "localhost"
DBUSER = "postgres"
DBPASS = "postgres"
DBMAXSIZE = 10
# Used for initial import from Kinto. Delete me once this is done.
LEGACY_PSQL = "postgresql://postgres@localhost/legacy_egapro"


def init():
    for key, value in globals().items():
        if key.isupper():
            env_key = "EGAPRO_" + key
            typ = type(value)
            if typ == list:
                typ = lambda x: x.split()
            if env_key in os.environ:
                globals()[key] = typ(os.environ[env_key])


init()
