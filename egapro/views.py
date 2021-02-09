import sys

from functools import wraps
from traceback import print_exc

from naf import DB as NAF
from roll import Roll, HttpError
from roll import Request as BaseRequest
from asyncpg.exceptions import DataError
from roll.extensions import cors, options
from stdnum.fr.siren import is_valid as siren_is_valid

from . import config, constants, db, emails, helpers, models, tokens, schema
from .schema.legacy import from_legacy
from . import loggers


class Request(BaseRequest):
    def __init__(self, *args, **kwargs):
        self._data = None
        super().__init__(*args, **kwargs)

    @property
    def json(self):
        data = super().json
        if not isinstance(data, dict):
            raise HttpError(400, "`data` doit être de type objet JSON")
        id_ = data.get("id")
        if "data" in data:
            data = data["data"]
        # Legacy identifier, be defensive and try hard to find it.
        if "id" not in data and id_:
            data["id"] = id_
        return data

    @property
    def data(self):
        if self._data is None:
            data = self.json
            if data and "déclaration" not in data:
                data = from_legacy(data)
            self._data = models.Data(data)
        return self._data

    @property
    def domain(self):
        domain = self.origin or f"https://{self.host}"
        if not domain.endswith("/"):
            domain += "/"
        return domain

    @property
    def ip(self):
        return self.headers.get("X-REAL-IP")


class App(Roll):
    Request = Request


app = App()
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
        elif isinstance(error.__context__, db.NoData):
            response.status = 404
            error.message = f"Resource not found: {error.__context__}"
        elif isinstance(error.__context__, ValueError):
            response.status = 422
            loggers.log_request(request)
            loggers.logger.error(str(error.__context__))
        else:
            loggers.log_request(request)
            print_exc()
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
                loggers.logger.debug(
                    "Non owner (%s instead of %s) accessing resource %s %s",
                    declarant,
                    owner,
                    siren,
                    year,
                )
                if declarant not in config.STAFF:
                    if request.method == "PUT":
                        msg = "Cette déclaration a déjà été créée par un autre utilisateur"
                    else:
                        msg = "Cette déclaration a été créée par un autre utilisateur"
                    raise HttpError(403, msg)
        if request._body:  # This is a PUT.
            request.data.setdefault("déclarant", {})
            # Use token email as default for declarant email.
            if not request.data["déclarant"].get("email"):
                request.data["déclarant"]["email"] = declarant
        return await view(request, response, siren, year, *args, **kwargs)

    return wrapper


@app.route("/declaration/{siren}/{year}", methods=["PUT"])
@tokens.require
@ensure_owner
async def declare(request, response, siren, year):
    try:
        year = int(year)
    except ValueError:
        raise HttpError(f"Ce n'est pas une année valide: `{year}`")
    if not siren_is_valid(siren):
        raise HttpError(422, f"Numéro SIREN invalide: {siren}")
    if year not in constants.YEARS:
        years = ", ".join([str(y) for y in constants.YEARS])
        raise HttpError(
            422, f"Il est possible de déclarer seulement pour les années {years}"
        )
    data = request.data
    schema.validate(data.raw)
    helpers.compute_notes(data)
    schema.cross_validate(data.raw)
    declarant = request["email"]
    try:
        current = await db.declaration.get(siren, year)
    except db.NoData:
        current = None
    else:
        # Do not force new declarant, in case this is a staff person editing
        declarant = current["owner"]
    await db.declaration.put(siren, year, declarant, data)
    response.status = 204
    if data.validated:
        await db.archive.put(siren, year, data, by=declarant, ip=request.ip)
        # Do not send the success email on update for now (we send too much emails that
        # are unwanted, mainly because when someone loads the frontend app a PUT is
        # automatically sent, without any action from the user.)
        loggers.logger.info(f"{siren}/{year} BY {declarant} FROM {request.ip}")
        if not current or not current.data.validated:
            url = request.domain + data.uri
            emails.success.send(declarant, url=url, **data)


@app.route("/declaration/{siren}/{year}", methods=["GET"])
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


@app.route("/me", methods=["GET"])
@tokens.require
async def me(request, response):
    response.json = {"email": request["email"]}


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
        data = request.json
        if not isinstance(data, dict):
            raise HttpError(400, "JSON invalide")
        await db.simulation.put(uuid, data)
        response.json = db.simulation.as_resource(await db.simulation.get(uuid))
        response.status = 200
        draft = data.get("declaration", {}).get("formValidated") != "Valid"
        email = data.get("informationsDeclarant", {}).get("email")
        if email and not draft:
            token = tokens.create(email)
            response.cookies.set(name="api-key", value=token)

    async def on_get(self, request, response, uuid):
        record = await db.simulation.get(uuid)
        try:
            response.json = db.simulation.as_resource(record)
        except db.NoData:
            raise HttpError(404, f"No simulation found with uuid {uuid}")
        response.status = 200


@app.route("/token", methods=["POST"])
async def send_token(request, response):
    # TODO mailbomb management in nginx
    email = request.json.get("email")
    if not email:
        raise HttpError(400, "Missing email key")
    token = tokens.create(email)
    link = f"{request.domain}declaration/?token={token}"
    if "localhost" in link or "127.0.0.1" in link:
        print(link)
    loggers.logger.info(f"Token request FOR {email} FROM {request.ip}")
    if request.ip in config.ALLOWED_IPS:
        response.json = {"token": token}
    else:
        body = emails.ACCESS_GRANTED.format(link=link)
        emails.send(email, "Déclarer sur Egapro", body)
        response.status = 204


@app.route("/search")
async def search(request, response):
    q = request.query.get("q", "").strip()
    limit = request.query.int("limit", 10)
    offset = request.query.int("offset", 0)
    code_naf = request.query.get("code_naf", None)
    departement = request.query.get("departement", None)
    region = request.query.get("region", None)
    results = await db.search.run(
        query=q,
        limit=limit,
        offset=offset,
        code_naf=code_naf,
        departement=departement,
        region=region,
    )
    stats = await db.search.stats(
        query=q,
        code_naf=code_naf,
        departement=departement,
        region=region,
    )
    response.json = {"data": results, **stats}


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
    response.json = schema.SCHEMA.raw


@app.route("/validate-siren")
async def validate_siren(request, response):
    siren = request.query.get("siren")
    if not siren_is_valid(siren):
        raise HttpError(422, f"Numéro SIREN invalide: {siren}")
    response.status = 204


@app.listen("startup")
async def on_startup():
    await init()


@app.listen("shutdown")
async def on_shutdown():
    await db.terminate()


async def init():
    config.init()
    loggers.init()
    try:
        await db.init()
    except RuntimeError as err:
        sys.exit(err)
