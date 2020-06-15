"""Export data from DB."""

from pathlib import Path

import minicli
import ujson as json

from egapro import db


@minicli.cli
async def dump(path: Path, all=False):
    """Export des données Egapro.

    :path:          chemin vers le fichier d'export
    :all:           inclure les déclarations non validées
    """

    records = await db.declaration.all()
    print("Number of records", len(records))
    with path.open("w") as f:
        json.dump([r["data"] for r in records], f, ensure_ascii=False)
