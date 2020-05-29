import smtplib
from email.message import EmailMessage

from . import config


ACCESS_GRANTED = """Bonjour,

Voici le lien vous permettant de déclarer sur Egapro:

{link}

L'équipe Egapro
"""

SUCCESS = """Bonjour,

Votre déclaration est maintenant confirmée.

Merci poulet.

L'équipe Egapro
"""

SIMULATION = """Bonjour,

Le lien pour retrouver votre simulation:

{link}

Merci poulet.

L'équipe Egapro
"""


def send(to, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = config.FROM_EMAIL
    msg["To"] = to
    if not config.SEND_EMAILS:
        print("Sending email", str(msg))
        print("email body:", body)
        return
    try:
        server = smtplib.SMTP_SSL(config.SMTP_HOST)
        server.login(config.FROM_EMAIL, config.SMTP_PASSWORD)
        server.send_message(msg)
    except smtplib.SMTPException:
        raise RuntimeError
    finally:
        server.quit()
