import smtplib, ssl
from email.message import EmailMessage
from pathlib import Path

from .. import config


ACCESS_GRANTED = """Bonjour,

Voici le lien vous permettant de déclarer sur Egapro:

{link}

L'équipe Egapro
"""


def send(to, subject, txt, html=None):
    msg = EmailMessage()
    msg.set_content(txt)
    msg["Subject"] = subject
    msg["From"] = config.FROM_EMAIL
    msg["To"] = to
    if html:
        msg.add_alternative(html, subtype="html")
    if not config.SEND_EMAILS:
        print("Sending email", str(msg))
        print("email txt:", txt)
        return
    context = ssl.create_default_context()
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        if config.SMTP_SSL:
            server.starttls(context=context)
        try:
            if config.SMTP_LOGIN:
                server.login(config.SMTP_LOGIN, config.SMTP_PASSWORD)
            server.send_message(msg)
        except smtplib.SMTPException as err:
            raise RuntimeError from err


class Email:
    def __init__(self, subject, txt, html):
        self.subject = subject
        self.txt = txt
        self.html = html

    def send(self, to, **vars):
        txt = self.txt.format(**vars)
        html = (self.html or "").format(**vars)
        send(to, self.subject, txt, html)


def load():
    """Load templates, in order to do `emails.success.send()` for a template named
    `success`."""
    for path in Path(__file__).parent.iterdir():
        if path.is_dir() and not path.name.startswith("_"):
            subject = (path / "subject.txt").read_text()
            txt = (path / "body.txt").read_text()
            html = path / "body.html"
            if html.exists():
                html = html.read_text()
            else:
                html = None
            globals()[path.name] = Email(subject, txt, html)


load()
