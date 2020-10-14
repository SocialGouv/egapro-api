"""DGT specific utils"""

import time
from collections import defaultdict

from openpyxl import Workbook, load_workbook
from progressist import ProgressBar

from egapro import db
from egapro.solen import ExcelData, RowProcessor
from egapro.utils import flatten
from egapro.schema.legacy import from_legacy


AGES = {
    ":29": "30",
    "30:39": "30-39",
    "40:49": "40-49",
    "50:": "50",
}
EFFECTIF = {"50:250": "50 à 250", "251:999": "251 à 999", "1000:": "1000 et plus"}


async def get_ues_cols():
    """Return a list of `nom` and `siren` cols for the max number of UES columns."""
    try:
        max_num_ues = await db.declaration.fetchval(
            "SELECT "
            "jsonb_array_length(data->'informationsEntreprise'->'entreprisesUES') AS length "
            "FROM declaration WHERE data->'informationsEntreprise' ? 'entreprisesUES' "
            "ORDER BY length DESC LIMIT 1;"
        )
    except db.NoData:
        max_num_ues = 0
    # # The entreprise that made the declaration is counted in the number of UES,
    # # but its nom/siren is given elsewhere.
    # max_num_ues -= 1
    # This is a list of size max_num_ues of pairs of nom/siren cols.
    ues_cols_name_and_siren = [
        [
            (
                f"UES_{index_ues}_Nom_Entreprise",
                f"/entreprise/ues/entreprises/{index_ues}/raison_sociale",
            ),
            (
                f"UES_{index_ues}_Siren",
                f"/entreprise/ues/entreprises/{index_ues}/siren",
            ),
        ]
        for index_ues in range(max_num_ues)
    ]
    # This is a list of 2*max_num_ues of cols (ues 0 > nom, ues 0 > siren, ues 1 > nom, ues 1 > siren...)
    flattened_cols = [col for ues_cols in ues_cols_name_and_siren for col in ues_cols]
    return flattened_cols


async def get_headers_columns():
    """Return a tuple of lists of (header_names, column_names) that we want in the export."""
    num_coefficient = await db.declaration.fetchval(
        "SELECT coalesce(MAX((data->'indicateurUn'->>'nombreCoefficients')::int),0) AS max_val "
        "FROM declaration WHERE data->'indicateurUn' ? 'nombreCoefficients'"
    )
    interesting_cols = (
        [
            ("source", "/source"),
            ("URL_declaration", "URL_declaration"),  # Built from /data/id, see below
            ("Date_reponse", "/déclaration/date"),
            ("Email_declarant", "/déclarant/email"),
            ("Nom", "/déclarant/nom"),
            ("Prenom", "/déclarant/prénom"),
            ("Telephone", "/déclarant/téléphone"),
            ("Region", "/entreprise/région"),
            ("Departement", "/entreprise/département"),
            ("Adresse", "/entreprise/adresse"),
            ("CP", "/entreprise/code_postal"),
            ("Commune", "/entreprise/commune"),
            ("Annee_indicateurs", "/déclaration/année_indicateurs"),
            ("Structure", "Structure"),
            ("Tranche_effectif", "/entreprise/effectif/tranche"),
            ("Date_debut_periode", "/déclaration/période_référence/0"),
            ("Date_fin_periode", "/déclaration/période_référence/1"),
            ("Nb_salaries", "/entreprise/effectif/total"),
            ("Nom_Entreprise", "/entreprise/raison_sociale"),
            ("SIREN", "/entreprise/siren"),
            ("Code_NAF", "/entreprise/code_naf"),
            ("Nom_UES", "/entreprise/ues/raison_sociale"),
            # Inclure entreprise déclarante
            ("Nb_ets_UES", "nombre_ues"),
        ]
        + await get_ues_cols()
        + [
            ("Date_publication", "/déclaration/publication/date"),
            ("Site_internet_publication", "/déclaration/publication/url"),
            ("Modalités_publication", "/déclaration/publication/modalités"),
            ("Indic1_non_calculable", "Indic1_non_calculable"),
            (
                "Indic1_motif_non_calculable",
                "/indicateurs/rémunérations/non_calculable",
            ),
            (
                "Indic1_precision_autre_motif",
                "/indicateurs/rémunérations/motif_non_calculable",
            ),
            ("Indic1_modalite_calc_csp", "Indic1_modalite_calc_csp"),
            # Virer les booléens
            ("Indic1_modalite_calc_coef_branche", "Indic1_modalite_calc_coef_branche"),
            ("Indic1_modalite_calc_coef_autre", "Indic1_modalite_calc_coef_autre"),
            ("Indic1_date_consult_CSE", "/déclaration/date_consultation_cse"),
            ("Indic1_nb_coef_niv", "Indic1_nb_coef_niv"),
        ]
        + [
            (
                f"Indic1_Niv{index_coef}",
                f"/indicateurs/rémunérations/catégories/{index_coef}",
            )
            for index_coef in range(num_coefficient)
        ]
        + [
            ("Indic1_resultat", "/indicateurs/rémunérations/résultat"),
            (
                "Indic1_population_favorable",
                "/indicateurs/rémunérations/population_favorable",
            ),
            ("Indic2_non_calculable", "Indic2_non_calculable"),
            (
                "Indic2_motif_non_calculable",
                "/indicateurs/augmentations_hors_promotions/non_calculable",
            ),
        ]
        + [
            (
                f"Indic2_{CSP}",
                f"/indicateurs/augmentations_hors_promotions/catégories/{index_csp}",
            )
            for (index_csp, CSP) in enumerate(["Ouv", "Emp", "TAM", "IC"])
        ]
        + [
            ("Indic2_resultat", "/indicateurs/augmentations_hors_promotions/résultat"),
            (
                "Indic2_population_favorable",
                "/indicateurs/augmentations_hors_promotions/population_favorable",
            ),
            ("Indic3_non_calculable", "Indic3_non_calculable"),
            ("Indic3_motif_non_calculable", "/indicateurs/promotions/non_calculable"),
        ]
        + [
            (
                f"Indic3_{CSP}",
                f"/indicateurs/promotions/catégories/{index_csp}",
            )
            for (index_csp, CSP) in enumerate(["Ouv", "Emp", "TAM", "IC"])
        ]
        + [
            ("Indic3_resultat", "/indicateurs/promotions/résultat"),
            (
                "Indic3_population_favorable",
                "/indicateurs/promotions/population_favorable",
            ),
            ("Indic2et3_non_calculable", "Indic2et3_non_calculable"),
            (
                "Indic2et3_motif_non_calculable",
                "/indicateurs/augmentations/non_calculable",
            ),
            (
                "Indic2et3_resultat_pourcent",
                "/indicateurs/augmentations/résultat",
            ),
            (
                "Indic2et3_resultat_nb_sal",
                "/indicateurs/augmentations/résultat_nombre_salariés",
            ),
            (
                "Indic2et3_population_favorable",
                "/indicateurs/augmentations/population_favorable",
            ),
            ("Indic4_non_calculable", "Indic4_non_calculable"),
            (
                "Indic4_motif_non_calculable",
                "/indicateurs/congés_maternité/non_calculable",
            ),
            (
                "Indic4_precision_autre_motif",
                "/indicateurs/congés_maternité/motif_non_calculable",
            ),
            ("Indic4_resultat", "/indicateurs/congés_maternité/résultat"),
            ("Indic5_resultat", "/indicateurs/hautes_rémunérations/résultat"),
            (
                "Indic5_sexe_sur_represente",
                "/indicateurs/hautes_rémunérations/population_favorable",
            ),
            ("Indicateur_1", "/indicateurs/rémunérations/note"),
            ("Indicateur_2", "/indicateurs/augmentations_hors_promotions/note"),
            ("Indicateur_2et3", "/indicateurs/augmentations/note"),
            (
                "Indicateur_2et3_PourCent",
                "/indicateurs/augmentations/points_en_pourcentage",
            ),
            (
                "Indicateur_2et3_ParSal",
                "/indicateurs/augmentations/points_nombre_salariés",
            ),
            ("Indicateur_3", "/indicateurs/promotions/note"),
            ("Indicateur_4", "/indicateurs/congés_maternité/note"),
            ("Indicateur_5", "/indicateurs/hautes_rémunérations/note"),
            ("Nombre_total_points obtenus", "/déclaration/total_points"),
            (
                "Nombre_total_points_pouvant_etre_obtenus",
                "/déclaration/total_points_calculables",
            ),
            ("Resultat_final_sur_100_points", "/déclaration/index"),
            ("Mesures_correction", "/déclaration/mesures_correctives"),
        ]
    )
    headers = [header for header, _column in interesting_cols]
    columns = [column for _header, column in interesting_cols]
    return (headers, columns)


async def as_xlsx(max_rows=None, debug=False):
    """Export des données au format souhaité par la DGT.

    :max_rows:          Max number of rows to process.
    :debug:             Turn on debug to be able to read the generated Workbook
    """
    print("Reading from DB")
    records = await db.declaration.all()
    print("Flattening JSON")
    if max_rows:
        records = records[:max_rows]
    wb = Workbook(write_only=not debug)
    ws = wb.create_sheet()
    wb.active = ws
    headers, columns = await get_headers_columns()
    ws.append(headers)
    bar = ProgressBar(prefix="Computing", total=len(records))
    for record in bar.iter(records):
        data = prepare_record(record["data"])
        ws.append([data.get(c) for c in columns])
    return wb


def prepare_record(data):
    if "déclaration" not in data:  # Legacy schema
        from_legacy(data)

    # Before flattening.
    indic1_nv_niveaux = len(data["indicateurs"]["rémunérations"]["catégories"]) or None
    nombre_ues = len(data["entreprise"].get("ues", {}).get("entreprises", []))
    for idx, category in enumerate(data["indicateurs"]["rémunérations"]["catégories"]):
        tranches = category.get("tranches", {})
        data[f"indicateurs/rémunérations/catégories/{idx}"] = ";".join(
            [
                str(round(tranches.get(":29") or 0, 1)),
                str(round(tranches.get("30:39") or 0, 1)),
                str(round(tranches.get("40:49") or 0, 1)),
                str(round(tranches.get("50:") or 0, 1)),
            ]
        )

    data = flatten(data)
    source = data.get("/source")
    if source in ("solen-2019", "solen-2020"):
        url = f"'https://solen1.enquetes.social.gouv.fr/cgi-bin/HE/P?P={data['/id']}"
    else:
        data["/source"] = "egapro"
        url = f"'https://index-egapro.travail.gouv.fr/simulateur/{data['/id']}"
    data["URL_declaration"] = url
    data["Structure"] = (
        "Unité Economique et Sociale (UES)" if nombre_ues else "Entreprise"
    )
    data["nombre_ues"] = nombre_ues or None
    data["/entreprise/effectif/tranche"] = EFFECTIF[
        data["/entreprise/effectif/tranche"]
    ]

    # Indicateur 1
    indic1_mode = data.get("/indicateurs/rémunérations/mode")
    data["Indic1_nb_coef_niv"] = indic1_nv_niveaux if indic1_mode != "csp" else None
    data["Indic1_non_calculable"] = (
        "1" if data.get("/indicateurs/rémunérations/non_calculable") else "0"
    )
    data["Indic1_modalite_calc_csp"] = indic1_mode == "csp" and True
    data["Indic1_modalite_calc_coef_branche"] = indic1_mode == "coef" and True
    data["Indic1_modalite_calc_coef_autre"] = indic1_mode == "autre" and True

    # Indicateur 2
    data["Indic2_non_calculable"] = (
        True
        if data.get("/indicateurs/augmentations_hors_promotions/non_calculable")
        else False
    )
    data["Indic3_non_calculable"] = (
        True if data.get("/indicateurs/promotions/non_calculable") else False
    )
    data["Indic2et3_non_calculable"] = (
        True if data.get("/indicateurs/augmentations/non_calculable") else False
    )
    data["Indic4_non_calculable"] = (
        True if data.get("/indicateurs/congés_maternité/non_calculable") else False
    )
    return data


async def duplicates(current_export, legacy, *solen_data):
    before = time.perf_counter()
    headers, columns = await get_headers_columns()
    reversed_headers = dict(zip(headers, columns))
    raw = list(load_workbook(legacy, read_only=True, data_only=True).active.values)
    timer, before = time.perf_counter() - before, time.perf_counter()
    print(f"Done reading old data ({timer})")
    data = defaultdict(list)
    own_headers = raw[0]
    for row in raw[1:]:
        if row[0].startswith("solen"):
            continue
        year = row[12]
        if not year:
            year = row[16][-4:]
        siren = row[19]
        key = f"{year}.{siren}"
        # Align to current headers (which change according to data in DB)
        record = {
            reversed_headers[own_headers[i]]: row[i]
            for i in range(len(row))
            if own_headers[i] in reversed_headers
        }
        data[key].append(record)
    timer, before = time.perf_counter() - before, time.perf_counter()
    print(f"Done filtering old data ({timer})")
    raw = list(
        load_workbook(current_export, read_only=True, data_only=True).active.values
    )
    timer, before = time.perf_counter() - before, time.perf_counter()
    print(f"Done reading current data ({timer})")
    own_headers = raw[0]
    for row in raw[1:]:
        if row[0].startswith("solen"):
            continue
        year = row[12]
        if not year:
            year = row[16][-4:]
        siren = row[19]
        key = f"{year}.{siren}"
        if data[key]:  # We only want to import new records from new database.
            continue
        # Align to current headers (which change according to data in DB)
        record = {
            reversed_headers[own_headers[i]]: row[i]
            for i in range(len(row))
            if own_headers[i] in reversed_headers
        }
        data[key].append(record)
    timer, before = time.perf_counter() - before, time.perf_counter()
    print(f"Done filtering current data ({timer})")
    for path in solen_data:
        _, year = path.stem.split("-")
        raw = ExcelData(path)
        for row in raw.repondants.values():
            record = flatten(
                RowProcessor(
                    year,
                    None,
                    row,
                ).run()["data"]
            )
            url = f"'https://solen1.enquetes.social.gouv.fr/cgi-bin/HE/P?P={record['/id']}"
            record["URL_declaration"] = url
            siren = record["/entreprise/siren"]
            year = record["/informations/anneeDeclaration"]
            key = f"{year}.{siren}"
            data[key].append(record)
    timer, before = time.perf_counter() - before, time.perf_counter()
    print(f"Done reading solen data: ({timer})")
    print(f"Unique entries: {len(data)}")
    duplicates = {k: v for k, v in data.items() if len(v) > 1}
    timer, before = time.perf_counter() - before, time.perf_counter()
    print(f"Done computing duplicates ({timer})")
    wb = Workbook(write_only=True)
    ws = wb.create_sheet()
    wb.active = ws
    ws.append(headers)
    for entry in duplicates.values():
        for record in entry:
            ws.append([record.get(c) for c in columns])
    return wb
