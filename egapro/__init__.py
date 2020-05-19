from roll import Roll, HttpError
from roll.extensions import simple_server, traceback

from . import config, db, emails, tokens

app = Roll()
traceback(app)


def ensure_owner(view):
    def wrapper(request, response, siren, year, *args, **kwargs):
        declarant = request["email"]
        try:
            owner = db.declaration.owner(siren, year)
        except db.NoData:
            pass
        else:
            if owner != declarant:
                # TODO should we obfuscate the existance of the resource?
                raise HttpError(403, "Sorry, no")
        return view(request, response, siren, year, *args, **kwargs)

    return wrapper


@app.route("/declaration/{siren}/{year}", methods=["PUT"])
@tokens.require
@ensure_owner
async def declare(request, response, siren, year):
    data = request.json
    declarant = request["email"]
    db.declaration.put(siren, year, declarant, data)
    response.status = 200
    if data.get("confirm") is True:
        emails.send(declarant, "Votre déclaration est confirmée", emails.SUCCESS)


@app.route("/declaration/{siren}/{year}", methods=["GET"])
@tokens.require
@ensure_owner
async def get_declaration(request, response, siren, year):
    try:
        response.body = db.declaration.get(siren, year)
    except db.NoData:
        raise HttpError(404, "No declaration with siren {siren} and year {year}")
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


@app.listen("startup")
async def on_startup():
    init()


def init():
    config.init()
    db.init()


def serve(reload=False):
    """Run a web server (for development only)."""
    if reload:
        import hupper

        hupper.start_reloader("egapro.serve")
    simple_server(app, port=2626)
