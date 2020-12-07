import sys

from functools import wraps

import ujson as json
from naf import DB as NAF
from roll import Roll, HttpError
from roll import Request as BaseRequest
from asyncpg.exceptions import DataError
from roll.extensions import cors, options, traceback
from stdnum.fr.siren import is_valid as siren_is_valid

from . import config, constants, db, emails, models, tokens, schema, utils
from .schema.legacy import from_legacy
from .loggers import logger


class Request(BaseRequest):
    def __init__(self, *args, **kwargs):
        self._data = None
        super().__init__(*args, **kwargs)

    @property
    def json(self):
        data = super().json
        if "data" in data:
            data = data["data"]
        return data

    @property
    def data(self):
        if self._data is None:
            data = self.json
            # Legacy identifier, be defensive and try hard to find it.
            if "id" not in data:
                id_ = self.json.get("id")
                if id_:
                    data["id"] = id_
            if data and "déclaration" not in data:
                data = from_legacy(data)
            self._data = models.Data(data)
        return self._data


class App(Roll):
    Request = Request


app = App()
traceback(app)
cors(app, methods="*", headers=["*", "Content-Type"], credentials=True, origin="http://localhost:3000")
options(app)


@app.listen("error")
async def json_error_response(request, response, error):
    if error.status == 404:
        error.message = {"error": f"Path not found `{request.path}`"}
    if error.status == 500:  # This error as not yet been caught
        if isinstance(error.__context__, DataError):
            response.status = 400
            error.message = f"Invalid data: {error.__context__}"
        elif isinstance(error.__context__, db.NoData):
            response.status = 404
            error.message = f"Resource not found: {error.__context__}"
        elif isinstance(error.__context__, ValueError):
            response.status = 422
    if isinstance(error.message, (str, bytes)):
        error.message = {"error": error.message}
    response.json = error.message


def ensure_owner(view):
    @wraps(view)
    async def wrapper(request, response, siren, year, *args, **kwargs):
        declarant = request["email"]
        try:
            owner = await db.declaration.owner(siren, year)
        except db.NoData:
            pass
        else:
            if owner != declarant:
                logger.info(
                    "Non owner (%s instead of %s) accessing resource %s %s",
                    declarant,
                    owner,
                    siren,
                    year,
                )
                if declarant not in config.STAFF:
                    raise HttpError(403, "You are not owner of this resource")
        if request._body:  # This is a PUT.
            request.data.setdefault("déclarant", {})
            # Make sure we set the email used for token as owner.
            request.data["déclarant"]["email"] = declarant
        return await view(request, response, siren, year, *args, **kwargs)

    return wrapper


def flatten(view):
    @wraps(view)
    async def wrapper(request, response, *args, **kwargs):
        to_flatten = "application/vnd.egapro.v1.flat" in request.headers.get(
            "ACCEPT", ""
        )
        if to_flatten and request._body:
            request._json = utils.unflatten(request.json)
        ret = await view(request, response, *args, **kwargs)
        if to_flatten and response.body:
            # TODO act before jsonifying the dict.
            body = json.loads(response.body)
            if "data" in body:
                body["data"] = utils.flatten(body["data"])
            response.body = json.dumps(body)
        return ret

    return wrapper


@app.route("/declaration/{siren}/{year}", methods=["PUT"])
@flatten
@tokens.require
@ensure_owner
async def declare(request, response, siren, year):
    data = request.data
    schema.validate(data.raw)
    utils.compute_notes(data)
    schema.cross_validate(data.raw)
    declarant = request["email"]
    try:
        current = await db.declaration.get(siren, year)
    except db.NoData:
        current = None
        # This is a new declaration, let's validate year and siren.
        if not siren_is_valid(siren):
            raise HttpError(422, f"Numéro SIREN invalide: {siren}")
        try:
            year = int(year)
        except ValueError:
            raise HttpError(f"Invalid value for year: {year}")
        if year not in constants.YEARS:
            years = ", ".join([str(y) for y in constants.YEARS])
            raise HttpError(
                422, f"Il est possible de déclarer seulement pour les années {years}"
            )
    await db.declaration.put(siren, year, declarant, data)
    response.status = 204
    if data.validated:
        # Do not send the success email on update for now (we send too much emails that
        # are unwanted, mainly because when someone loads the frontend app a PUT is
        # automatically sent, without any action from the user.)
        if not current or not models.Data(current["data"]).validated:
            if data.id:  # Coming from simulation URL
                url = f"{config.BASE_URL}/simulateur/{data.id}"
            else:
                url = f"{config.BASE_URL}/declaration/{data.siren}/{data.year}"
            emails.success.send(declarant, url=url, **data)


@app.route("/declaration/{siren}/{year}", methods=["GET"])
@flatten
@tokens.require
@ensure_owner
async def get_declaration(request, response, siren, year):
    try:
        response.json = db.declaration.as_resource(
            await db.declaration.get(siren, year)
        )
    except db.NoData:
        raise HttpError(404, f"No declaration with siren {siren} and year {year}")
    response.status = 200


@app.route("/simulation", methods=["POST"])
async def start_simulation(request, response):
    data = request.json
    email = data.get("informationsDeclarant", {}).get("email")
    uid = await db.simulation.create(request.json)
    response.json = {"id": uid}
    if email:
        emails.permalink.send(email, id=uid)
    response.status = 200


# KILL THIS ENDPOINT
@app.route("/simulation/{uuid}/send-code", methods=["POST"])
async def send_simulation_code(request, response, uuid):
    # Make sure given simulation exists
    await db.simulation.get(uuid)
    email = request.json.get("email", {})
    response.status = 204
    if not email:
        raise HttpError(400, "Missing `email` key")
    emails.permalink.send(email, id=uuid)


@app.route("/simulation/{uuid}")
class SimulationResource:
    async def on_put(self, request, response, uuid):
        await db.simulation.put(uuid, request.json)
        if self.is_declaration(response, request.data):
            return
        response.json = db.simulation.as_resource(await db.simulation.get(uuid))
        response.status = 200

    async def on_get(self, request, response, uuid):
        record = await db.simulation.get(uuid)
        try:
            response.json = db.simulation.as_resource(record)
        except db.NoData:
            raise HttpError(404, f"No simulation found with uuid {uuid}")
        response.status = 200

    def is_declaration(self, response, data):
        """This is an old fashioned declaration. Let's redirect for now."""
        if not data.validated:
            return
        if not data.email:
            raise HttpError(400, "Anonymous declaration")
        token = tokens.create(data.email)
        response.cookies.set(name="api-key", value=token.decode())
        location = f"{config.BASE_URL}/declaration/{data.siren}/{data.year}"
        # https://tools.ietf.org/html/rfc7231#section-6.4.7
        response.redirect = location, 307
        return True


@app.route("/token", methods=["POST"])
async def send_token(request, response):
    # TODO mailbomb management in nginx
    email = request.json.get("email")
    if not email:
        raise HttpError(400, "Missing email key")
    token = tokens.create(email)
    host = request.origin or f"https://{request.host}"
    if not host.endswith("/"):
        host += "/"
    link = f"{host}declaration/?token={token.decode()}"
    print(link)
    body = emails.ACCESS_GRANTED.format(link=link)
    emails.send(email, "Déclarer sur Egapro", body)
    response.status = 204


@app.route("/stats")
async def stats(request, response):
    async with db.table.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT data->'informations'->>'trancheEffectifs' as tranche, COUNT(*) "
            "FROM declaration GROUP BY tranche;"
        )
    response.json = dict(rows)


@app.route("/search")
async def search(request, response):
    q = request.query.get("q")
    if not q:
        raise HttpError(400, "Empty search")
    limit = request.query.int("limit", 10)
    results = await db.declaration.search(q, limit=limit)
    response.json = {"data": results, "total": len(results)}


@app.route("/config")
async def get_config(request, response):
    keys = request.query.list("key", [])
    data = {
        "YEARS": constants.YEARS,
        "EFFECTIFS": constants.EFFECTIFS,
        "DEPARTEMENTS": constants.DEPARTEMENTS,
        "REGIONS": constants.REGIONS,
        "REGIONS_TO_DEPARTEMENTS": constants.REGIONS_TO_DEPARTEMENTS,
        "NAF": dict(NAF.pairs()),
    }
    response.json = {k: v for k, v in data.items() if not keys or k in keys}


@app.route("/jsonschema.json")
async def get_jsonschema(request, response):
    response.json = schema.SCHEMA


@app.listen("startup")
async def on_startup():
    await init()


@app.listen("shutdown")
async def on_shutdown():
    await db.terminate()


async def init():
    config.init()
    try:
        await db.init()
    except RuntimeError as err:
        sys.exit(err)
