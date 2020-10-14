import sys

from functools import wraps

import ujson as json
from roll import Roll, HttpError
from roll import Request as BaseRequest
from asyncpg.exceptions import DataError
from roll.extensions import cors, options, traceback
from stdnum.fr.siren import is_valid as siren_is_valid

from . import config, constants, db, emails, models, tokens, schema, utils
from .loggers import logger


class Request(BaseRequest):
    @property
    def data(self):
        data = self.json
        if "data" in data:
            data = data["data"]
        # Legacy identifier, be defensive and try hard to find it.
        if "id" not in data:
            id_ = self.json.get("id")
            if id_:
                data["id"] = id_
        return models.Data(data)


class App(Roll):
    Request = Request


app = App()
traceback(app)
cors(app, methods="*", headers=["*", "Content-Type"], credentials=True)
options(app)


@app.listen("error")
async def json_error_response(request, response, error):
    if error.status == 404:
        error.message = {"error": f"Path not found `{request.path}`"}
    if error.status == 500:  # This error as not yet been caught
        if isinstance(error.__context__, DataError):
            response.status = 400
            error.message = f"Invalid data: {error.__context__}"
        if isinstance(error.__context__, db.NoData):
            response.status = 404
            error.message = f"Resource not found: {error.__context__}"
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
                # TODO should we obfuscate the existence of the resource?
                if request.method not in ("GET", "OPTIONS"):
                    raise HttpError(403, "Sorry, no")
        return await view(request, response, siren, year, *args, **kwargs)

    return wrapper


def flatten(view):
    @wraps(view)
    async def wrapper(request, response, *args, **kwargs):
        to_flatten = "application/vnd.egapro.v1.flat" in request.headers.get(
            "ACCEPT", ""
        )
        print(to_flatten, request.headers)
        if to_flatten and request._body:
            request._json = utils.unflatten(request.json)
            print(request._json)
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
    declarant = request["email"]
    try:
        current = await db.declaration.get(siren, year)
    except db.NoData:
        current = None
        # This is a new declaration, let's validate year and siren.
        if not siren_is_valid(siren):
            raise HttpError(422, f"Numéro SIREN invalide: {siren}")
        years = [str(y) for y in constants.YEARS]  # Compare str with str
        if year not in years:
            years = ", ".join(years)
            raise HttpError(
                422, f"Il est possible de déclarer seulement pour les années {years}"
            )
    await db.declaration.put(siren, year, declarant, data)
    response.status = 204
    if data.validated:
        if not data.id:
            raise HttpError(400, "Missing id")
        # Do not send the success email on update for now (we send too much emails that
        # are unwanted, mainly because when someone loads the frontend app a PUT is
        # automatically sent, without any action from the user.)
        if not current or not models.Data(current["data"]).validated:
            emails.success.send(declarant, **data)


@app.route("/declaration/{siren}/{year}", methods=["PATCH"])
@flatten
@tokens.require
@ensure_owner
async def patch_declaration(request, response, siren, year):
    declarant = request["email"]
    declaration = await db.declaration.get(siren, year)
    current = declaration["data"]
    current.update(request.data.raw)
    data = models.Data(current)
    await db.declaration.put(siren, year, declarant, data)
    response.status = 204
    if data.validated:
        if not data.id:
            raise HttpError(400, "Missing id")
        emails.success.send(declarant, **data)


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
    data = request.data
    email = data.email
    uid = await db.simulation.create(data)
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
        data = request.data
        await db.simulation.put(uuid, data)
        if self.is_declaration(response, data):
            return
        response.json = db.simulation.as_resource(await db.simulation.get(uuid))
        response.status = 200

    async def on_get(self, request, response, uuid):
        record = await db.simulation.get(uuid)
        data = models.Data(record["data"])
        if self.is_declaration(response, data):
            return
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
    host = request.referrer or request.origin or f"https://{request.host}"
    if not host.endswith("/"):
        host += "/"
    link = f"{host}?token={token.decode()}"
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
    response.json = {
        "YEARS": constants.YEARS,
        "EFFECTIFS": constants.EFFECTIFS,
        "DEPARTEMENTS": constants.DEPARTEMENTS,
        "REGIONS": constants.REGIONS,
    }


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