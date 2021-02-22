import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

import yaml
from jinja2 import Template, TemplateError, Undefined

from .. import config
from ..loggers import logger


ACCESS_GRANTED = """Bonjour,

Voici le lien vous permettant de déclarer sur Egapro:

{link}

L'équipe Egapro
"""

REPLY_TO = {}


# Never fail when a deep attribute is missing (eg. indicateurs.rémunérations.note)
class SilentUndefined(Undefined):
    def _fail_with_undefined_error(self, *args, **kwargs):
        return None


def send(to, subject, txt, html=None, reply_to=None):
    msg = EmailMessage()
    msg["From"] = config.FROM_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
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
        self.txt = self.load(txt)
        self.html = self.load(html)

    def send(self, to, **context):
        txt, html = self(**context)
        reply_to = REPLY_TO.get(context.get("departement"))
        send(to, self.subject, txt, html, reply_to=reply_to)

    def __call__(self, **context):
        return self.txt.render(**context), (self.html or "").render(**context)

    def load(self, s):
        try:
            return Template(
                s or "", undefined=SilentUndefined, trim_blocks=True, lstrip_blocks=True
            )
        except TemplateError as err:
            print(s)
            sys.exit(err)


def load():
    """Load templates, in order to do `emails.success.send()` for a template named
    `success`."""
    root = Path(__file__).parent
    for path in root.iterdir():
        if path.is_dir() and not path.name.startswith("_"):
            # Don't include carriage return in subject.
            subject = (path / "subject.txt").read_text()[:-1]
            txt = (path / "body.txt").read_text()
            html = path / "body.html"
            if html.exists():
                html = html.read_text()
            else:
                html = None
            globals()[path.name] = Email(subject, txt, html)

    REPLY_TO.update(yaml.safe_load((root / "reply_to.yml").read_text()))


load()
