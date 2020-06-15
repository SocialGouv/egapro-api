from datetime import timedelta
from functools import wraps

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
    @wraps(view)
    def wrapper(request, response, *args, **kwargs):
        if config.REQUIRE_TOKEN:
            token = request.headers.get("API-KEY")
            if not token:
                raise HttpError(401, "No authentication token was provided.")
            try:
                email = read(token)
            except ValueError:
                raise HttpError(401, "Invalid token")
        else:
            email = (
                request.json.get("data", {})
                .get("informationsDeclarant", {})
                .get("email")
            )
            if not email:
                raise HttpError(422, "Missing declarant email")
        request["email"] = email
        return view(request, response, *args, **kwargs)

    return wrapper
