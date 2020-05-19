from datetime import timedelta

import jwt
from roll import HttpError

from . import config, utils


def create(email):
    return jwt.encode(
        {"sub": str(email), "exp": utils.utcnow() + timedelta(hours=1)},
        config.SECRET,
        config.JWT_ALGORITHM,
    )


def read(token):
    try:
        decoded = jwt.decode(token, config.SECRET, algorithms=[config.JWT_ALGORITHM])
    except (jwt.DecodeError, jwt.ExpiredSignatureError):
        raise ValueError
    return decoded["sub"]


def require(view):
    def wrapper(request, response, *args, **kwargs):
        token = request.headers.get("API-KEY")
        if not token:
            raise HttpError(401, "No authentication token was provided.")
        try:
            request["email"] = read(token)
        except ValueError:
            raise HttpError(401, "Invalid token")
        return view(request, response, *args, **kwargs)

    return wrapper
