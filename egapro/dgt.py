"""DGT specific utils"""

from pathlib import Path
from pprint import pprint

import minicli
import pandas

from egapro import db
from egapro.utils import flatten


def get_num_coefficient(data):
    """Return the max number of custom coefficient in the data."""
    return int(data["/indicateurUn/nombreCoefficients"].max())


def get_ues_cols(data):
    """Return a list of `nom` and `siren` cols for the max number of UES columns."""
    max_num_ues = int(data["/informationsEntreprise/nombreEntreprises"].max())
    # The entreprise that made the declaration is counted in the number of UES,
    # but its nom/siren is given elsewhere.
    max_num_ues -= 1
    # This is a list of size max_num_ues of pairs of nom/siren cols.
    ues_cols_name_and_siren = [
        [
            (
                f"UES_{index_ues}_Nom_Entreprise",
                f"/informationsEntreprise/entreprisesUES/{index_ues}/nom",
            ),
            (
                f"UES_{index_ues}_Siren",
                f"/informationsEntreprise/entreprisesUES/{index_ues}/siren",
            ),
        ]
        for index_ues in range(max_num_ues)
    ]
    # This is a list of 2*max_num_ues of cols (ues 0 > nom, ues 0 > siren, ues 1 > nom, ues 1 > siren...)
    flattened_cols = [col for ues_cols in ues_cols_name_and_siren for col in ues_cols]
    return flattened_cols


def get_headers_columns(data):
    """Return a tuple of lists of (header_names, column_names) that we want in the export."""
    interesting_cols = (
        [
            ("source", "/source"),
            ("URL_declaration", "URL_declaration"),  # Built from /data/id, see below
            ("Date_reponse", "/declaration/dateDeclaration"),
            ("Email_declarant", "/informationsDeclarant/email"),
            ("Nom", "/informationsDeclarant/nom"),
            ("Prenom", "/informationsDeclarant/prenom"),
            ("Telephone", "/informationsDeclarant/tel"),
            ("Region", "/informationsEntreprise/region"),
            ("Departement", "/informationsEntreprise/departement"),
            ("Adresse", "/informationsEntreprise/adresse"),
            ("CP", "/informationsEntreprise/codePostal"),
            ("Commune", "/informationsEntreprise/commune"),
            ("Annee_indicateurs", "/informations/anneeDeclaration"),
            ("Structure", "/informationsEntreprise/structure"),
            ("Tranche_effectif", "/informations/trancheEffectifs"),
            ("Date_debut_periode", "/informations/debutPeriodeReference"),
            ("Date_fin_periode", "/informations/finPeriodeReference"),
            ("Nb_salaries", "/effectif/nombreSalariesTotal"),
            ("Nom_Entreprise", "/informationsEntreprise/nomEntreprise"),
            ("SIREN", "/informationsEntreprise/siren"),
            ("Code_NAF", "/informationsEntreprise/codeNaf"),
            ("Nom_UES", "/informationsEntreprise/nomUES"),
            ("Nb_ets_UES", "/informationsEntreprise/nombreEntreprises"),
        ]
        + get_ues_cols(data)
        + [
            ("Date_publication", "/declaration/datePublication"),
            ("Site_internet_publication", "/declaration/lienPublication"),
            ("Indic1_non_calculable", "/indicateurUn/nonCalculable"),
            ("Indic1_motif_non_calculable", "/indicateurUn/motifNonCalculable"),
            (
                "Indic1_precision_autre_motif",
                "/indicateurUn/motifNonCalculablePrecision",
            ),
            ("Indic1_modalite_calc_csp", "/indicateurUn/csp"),
            ("Indic1_modalite_calc_coef_branche", "/indicateurUn/coef"),
            ("Indic1_modalite_calc_coef_autre", "/indicateurUn/autre"),
            ("Indic1_date_consult_CSE", "/declaration/dateConsultationCSE"),
            ("Indic1_nb_coef_niv", "/indicateurUn/nombreCoefficients"),
        ]
        + [
            (
                f"Indic1_{CSP}_{tranche_age}",
                f"/indicateurUn/remunerationAnnuelle/{index_csp}/tranchesAges/{index_tranche_age}/ecartTauxRemuneration",
            )
            for (index_csp, CSP) in enumerate(["Ouv", "Emp", "TAM", "IC"])
            for (index_tranche_age, tranche_age) in enumerate(
                ["30", "30-39", "40-49", "50"]
            )
        ]
        + [
            (
                f"Indic1_Niv{index_coef}_{tranche_age}",
                f"/indicateurUn/coefficient/{index_coef}/tranchesAges/{index_tranche_age}/ecartTauxRemuneration",
            )
            for index_coef in range(get_num_coefficient(data))
            for (index_tranche_age, tranche_age) in enumerate(
                ["30", "30-39", "40-49", "50"]
            )
        ]
        + [
            ("Indic1_resultat", "/indicateurUn/resultatFinal"),
            ("Indic1_population_favorable", "/indicateurUn/sexeSurRepresente"),
            ("Indic2_non_calculable", "/indicateurDeux/nonCalculable"),
            ("Indic2_motif_non_calculable", "/indicateurDeux/motifNonCalculable"),
            (
                "Indic2_precision_autre_motif",
                "/indicateurDeux/motifNonCalculablePrecision",
            ),
        ]
        + [
            (
                f"Indic2_{CSP}",
                f"/indicateurDeux/tauxAugmentation/{index_csp}/ecartTauxAugmentation",
            )
            for (index_csp, CSP) in enumerate(["Ouv", "Emp", "TAM", "IC"])
        ]
        + [
            ("Indic2_resultat", "/indicateurDeux/resultatFinal"),
            ("Indic2_population_favorable", "/indicateurDeux/sexeSurRepresente"),
            ("Indic3_non_calculable", "/indicateurTrois/nonCalculable"),
            ("Indic3_motif_non_calculable", "/indicateurTrois/motifNonCalculable"),
            (
                "Indic3_precision_autre_motif",
                "/indicateurTrois/motifNonCalculablePrecision",
            ),
        ]
        + [
            (
                f"Indic3_{CSP}",
                f"/indicateurTrois/tauxPromotion/{index_csp}/ecartTauxPromotion",
            )
            for (index_csp, CSP) in enumerate(["Ouv", "Emp", "TAM", "IC"])
        ]
        + [
            ("Indic3_resultat", "/indicateurTrois/resultatFinal"),
            ("Indic3_population_favorable", "/indicateurTrois/sexeSurRepresente"),
            ("Indic2et3_non_calculable", "/indicateurDeuxTrois/nonCalculable"),
            (
                "Indic2et3_motif_non_calculable",
                "/indicateurDeuxTrois/motifNonCalculable",
            ),
            (
                "Indic2et3_precision_autre_motif",
                "/indicateurDeuxTrois/motifNonCalculablePrecision",
            ),
            ("Indic2et3_resultat_pourcent", "/indicateurDeuxTrois/resultatFinalEcart",),
            (
                "Indic2et3_resultat_nb_sal",
                "/indicateurDeuxTrois/resultatFinalNombreSalaries",
            ),
            (
                "Indic2et3_population_favorable",
                "/indicateurDeuxTrois/sexeSurRepresente",
            ),
            ("Indic4_non_calculable", "/indicateurQuatre/nonCalculable"),
            ("Indic4_motif_non_calculable", "/indicateurQuatre/motifNonCalculable",),
            (
                "Indic4_precision_autre_motif",
                "/indicateurQuatre/motifNonCalculablePrecision",
            ),
            ("Indic4_resultat", "/indicateurQuatre/resultatFinal"),
            ("Indic5_resultat", "/indicateurCinq/resultatFinal"),
            ("Indic5_sexe_sur_represente", "/indicateurCinq/sexeSurRepresente"),
            ("Indicateur_1", "/indicateurUn/noteFinale"),
            ("Indicateur_2", "/indicateurDeux/noteFinale"),
            ("Indicateur_2et3", "/indicateurDeuxTrois/noteFinale"),
            ("Indicateur_2et3_PourCent", "/indicateurDeuxTrois/noteEcart"),
            ("Indicateur_2et3_ParSal", "/indicateurDeuxTrois/noteNombreSalaries"),
            ("Indicateur_3", "/indicateurTrois/noteFinale"),
            ("Indicateur_4", "/indicateurQuatre/noteFinale"),
            ("Indicateur_5", "/indicateurCinq/noteFinale"),
            ("Nombre_total_points obtenus", "/declaration/totalPoint"),
            (
                "Nombre_total_points_pouvant_etre_obtenus",
                "/declaration/totalPointCalculable",
            ),
            ("Resultat_final_sur_100_points", "/declaration/noteIndex"),
            ("Mesures_correction", "/declaration/mesuresCorrection"),
        ]
    )
    print("List of interesting columns to export: (alias_name, json_name)")
    pprint(interesting_cols)
    import_cols = [
        (header, column)
        for header, column in interesting_cols
        if column in data.columns
    ]
    if len(import_cols) != len(interesting_cols):
        print(
            "!!!!! those columns are 'interesting' but not found in the input file! !!!!!"
        )
        pprint(
            [
                column
                for _header, column in interesting_cols
                if column not in data.columns
            ]
        )
    headers = [header for header, _column in import_cols]
    columns = [column for _header, column in import_cols]
    return (headers, columns)


@minicli.cli(name="dump-dgt")
async def dump(path, nb_rows: int = 0):
    """Export des données au format souhaité par la DGT."""
    print("Reading from DB")
    records = await db.declaration.all()
    print("Flattening JSON")
    if nb_rows:
        records = records[:nb_rows]
    flattened = [flatten(r["data"]) for r in records]
    print("Loading data in pandas")
    data = pandas.DataFrame(flattened)
    print("Adding a source of 'egapro' for records without a source")
    data["/source"] = data.apply(
        lambda d: (
            "egapro"
            if d.get("/source") not in ("solen-2019", "solen-2020")
            else d["/source"]
        ),
        axis=1,
    )
    print("Adding 'URL de déclaration' column based on the ID and the source")
    # print(data["/id"])
    data["URL_declaration"] = data["/id"]
    data["URL_declaration"] = data.apply(
        lambda d: (
            "'https://index-egapro.travail.gouv.fr/simulateur/" + d["/id"]
            if d["/source"] == "egapro"
            else "'https://solen1.enquetes.social.gouv.fr/cgi-bin/HE/P?P=" + d["/id"]
        ),
        axis=1,
    )
    headers, columns = get_headers_columns(data)
    print("Writing the XLSX to", path)
    data[columns].to_excel(path, index=False, header=headers)
    print("Done")
