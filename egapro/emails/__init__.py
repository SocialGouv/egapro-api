import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Template

from .. import config
from ..loggers import logger


ACCESS_GRANTED = """Bonjour,

Voici le lien vous permettant de déclarer sur Egapro:

{link}

L'équipe Egapro
"""


def send(to, subject, txt, html=None):
    msg = EmailMessage()
    msg["From"] = config.FROM_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(txt)
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
        else:
            logger.debug(f"Email sent to {to}: {subject}")


class Email:
    def __init__(self, subject, txt, html):
        self.subject = subject
        self.txt = Template(txt)
        self.html = Template(html)

    def send(self, to, **vars):
        txt = self.txt.render(**vars)
        html = (self.html or "").render(**vars)
        send(to, self.subject, txt, html)


def load():
    """Load templates, in order to do `emails.success.send()` for a template named
    `success`."""
    for path in Path(__file__).parent.iterdir():
        if path.is_dir() and not path.name.startswith("_"):
            # Don't include carriage return in subject.
            subject = (path / "subject.txt").read_text()[:-1]
            txt = (path / "body.txt").read_text()
            html = path / "body.html"
            if html.exists():
                html = html.read_text()
            else:
                html = ""
            globals()[path.name] = Email(subject, txt, html)


load()
