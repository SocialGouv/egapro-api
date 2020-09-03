import logging

logger = logging.getLogger("egapro")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())
