import logging
from importlib import metadata

import sentry_sdk

from . import config
from .utils import json_dumps


logger = logging.getLogger("egapro")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

sentry = None


def init():
    global sentry
    sentry = Sentry()


class Sentry:
    def __init__(self):
        sentry_sdk.init(
            config.SENTRY_DSN,
            release=metadata.version("egapro"),
            environment=config.FLAVOUR,
        )

    def _set_context(self, request):
        try:
            data = request.data
        except:
            data = {}
        sentry_sdk.set_context(
            "request",
            {
                "path": request.path,
                "source": data.get("source"),
                "data": json_dumps(data),
            },
        )

    def message(self, request, message):
        self._set_context(request)
        sentry_sdk.capture_message(message)

    def error(self, request, error=None):
        self._set_context(request)
        sentry_sdk.capture_exception(error)
