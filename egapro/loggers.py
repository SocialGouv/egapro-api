import logging
from importlib import metadata

import sentry_sdk

from . import config, schema


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
        extra = {}
        try:
            data = request.data
        except:
            pass
        else:
            for key in schema.SCHEMA.sub_keys:
                extra[key] = str(data.path(key))
        context = {"path": request.path, **extra}
        sentry_sdk.set_context("request", context)
        logger.info(context)

    def message(self, request, message):
        self._set_context(request)
        sentry_sdk.capture_message(message)
        logger.info(message)

    def error(self, request, error=None):
        self._set_context(request)
        sentry_sdk.capture_exception(error)
