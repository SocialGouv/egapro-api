from functools import wraps

from roll import Roll, HttpError
from roll import Request as BaseRequest
from roll.extensions import cors, options, simple_server, traceback

from . import config, db, emails, models, tokens


class Request(BaseRequest):
    @property
    def data(self):
        data = self.json
        if "data" in data:
            data = data["data"]
        return models.Data(data)


class App(Roll):
    Request = Request


app = App()
traceback(app)
cors(app, methods=["GET", "PUT"], headers="*")
options(app)


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
                # TODO should we obfuscate the existence of the resource?
                raise HttpError(403, "Sorry, no")
        return await view(request, response, siren, year, *args, **kwargs)

    return wrapper


@app.route("/declaration/{siren}/{year}", methods=["PUT"])
@tokens.require
@ensure_owner
async def declare(request, response, siren, year):
    data = request.data
    declarant = request["email"]
    await db.declaration.put(siren, year, declarant, data)
    response.status = 204
    if data.get("confirm") is True:
        emails.send(declarant, "Votre déclaration est confirmée", emails.SUCCESS)


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


@app.route("/simulation", methods=["POST"])
async def start_simulation(request, response):
    data = request.data
    email = data.email
    uid = await db.simulation.create(data)
    response.json = {"id": uid}
    if email:
        body = emails.SIMULATION.format(
            link=f"{request.headers.get('REFERER', 'http://127.0.0.1:2626')}"
        )
        emails.send(email, "Votre simulation", body)
    response.status = 200


# KILL THIS ENDPOINT
@app.route("/simulation/{uuid}/send-code", methods=["POST"])
async def send_simulation_code(request, response, uuid):
    email = request.json.get("email", {})
    if email:
        body = emails.SIMULATION.format(
            link=f"{request.headers.get('REFERER', 'http://127.0.0.1:2626')}"
        )
        emails.send(email, "Votre simulation", body)
    response.status = 204


@app.route("/simulation/{uuid}", methods=["PUT"])
async def simulate(request, response, uuid):
    data = request.data
    if data.validated:
        # This is a declaration, for now let's redirect.
        # https://tools.ietf.org/html/rfc7231#section-6.4.7
        response.redirect = f"/declaration/{data.siren}/{data.year}", 307
        return
    await db.simulation.put(uuid, data)
    response.json = db.simulation.as_resource(await db.simulation.get(uuid))
    response.status = 200


@app.route("/simulation/{uuid}", methods=["GET"])
async def get_simulation(request, response, uuid):
    record = await db.simulation.get(uuid)
    data = models.Data(record["data"])
    if data.validated:
        response.redirect = f"/declaration/{data.siren}/{data.year}", 302
        return
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
    link = f"https://{request.host}/sésame/{token.decode()}"
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
    results = await db.declaration.search(q)
    response.json = {"data": results, "total": len(results)}


@app.listen("startup")
async def on_startup():
    await init()


@app.listen("shutdown")
async def on_shutdown():
    await db.terminate()


async def init():
    config.init()
    await db.init()


def serve(reload=False):
    """Run a web server (for development only)."""
    if reload:
        import hupper

        hupper.start_reloader("egapro.serve")
    simple_server(app, port=2626)
