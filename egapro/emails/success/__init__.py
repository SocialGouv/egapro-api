from datetime import datetime
from pathlib import Path

from fpdf import fpdf

from egapro import constants


# Disabled, waiting for new release so we can control the cache path.
fpdf.FPDF_CACHE_MODE = 1


LABELS = {
    "niveau_branche": "Par niveau ou coefficient hiérarchique en application de la classification de branche",
    "niveau_autre": "Par niveau ou coefficient hiérarchique en application d'une autre méthode de cotation des postes",
    "csp": "Par catégorie socio-professionnelle",
    "egvi40pcet": "Effectif des groupes valides inférieur à 40% de l'effectif",
    "absaugi": "Absence d'augmentations individuelles",
    "absprom": "Absence de promotions",
    "etsno5f5h": "L'entreprise ne comporte pas au moins 5 femmes et 5 hommes",
    "absrcm": "Absence de retours de congé maternité",
    "absaugpdtcm": "Absence d'augmentations pendant ce congé",
}


def as_date(s):
    if not s:
        return None
    return datetime.fromisoformat(s).date().strftime("%d/%m/%Y")


class PDF(fpdf.FPDF):
    def __init__(self, data, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = data
        root = Path(__file__).parent
        self.add_font("Marianne", "", root / "font/Marianne-Regular.ttf", uni=True)
        self.add_font(
            "Marianne", "I", root / "font/Marianne-RegularItalic.ttf", uni=True
        )
        self.add_font("Marianne", "B", root / "font/Marianne-Bold.ttf", uni=True)
        self.add_font("Marianne", "BI", root / "font/Marianne-BoldItalic.ttf", uni=True)
        self.set_title(f"Index Egapro {data.siren}/{data.year}")

    def header(self):
        self.image(Path(__file__).parent / "logo.png", 10, 8, 33)
        self.set_font("Marianne", "B", 16)
        # Move to the right
        self.cell(35)
        self.cell(
            0,
            txt="Récapitulatif de la déclaration de votre index de l'égalité",
            h=14,
            ln=2,
        )
        self.cell(0, txt="professionnelle entre les femmes et les hommes")
        self.ln(10)

    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        # Marianne italic 8
        self.set_font("Marianne", "I", 8)
        # Page number
        page_number = self.page_no()
        at = as_date(self.data.path("déclaration.date"))
        txt = (
            f"Page {page_number}/{{nb}} • Déclaration du {at} pour le Siren "
            f"{self.data.siren} et l'année {self.data.year}"
        )
        self.cell(0, 10, txt, 0, 0, "C")

    def write_pair(self, key, value):
        self.set_font("Marianne", "B", 11)
        key = f"{key} "
        if value is None:
            value = " - "
        if isinstance(value, float):
            value = f"{value:.2f}"
        value = str(LABELS.get(value, value))
        # Compute each cell width, and total height
        key_len = len(key)
        value_len = len(value)
        key_part = key_len / (value_len + key_len)
        # epw is the effetive page width.
        # Make sure we always let at least 50 mm for each cell.
        key_width = min(max(50, self.epw * key_part), self.epw - 50)
        value_width = self.epw - key_width
        max_len = max(key_len, value_len)
        # A char is more or less 2 mm width.
        letters_per_row = max(key_width, value_width) / 2
        height = (int(max_len / letters_per_row) + 1) * 5
        # print(key, value, key_width, value_width, max_len, letters_per_row, height)
        self.multi_cell(key_width, height, key, ln=3, align="L", max_line_height=5)
        self.set_font("Marianne", "", 11)
        self.multi_cell(value_width, height, value, ln=3, align="R", max_line_height=5)
        self.ln(height)

    def write_headline(self, value):
        self.ln(8)
        self.set_font("Marianne", "B", 14)
        self.write(6, str(value))
        self.ln(6)
        self.line(self.l_margin, self.y, self.w - self.r_margin, self.y)
        self.ln(2)

    def write_table(self, title, cells):
        with self.unbreakable() as pdf:
            pdf.write_headline(title)
            for key, value in cells:
                pdf.write_pair(key, value)


def attachment(data):
    pdf = PDF(data)
    pdf.add_page()
    tranche_effectif = data.path("entreprise.effectif.tranche")

    cells = (
        ("Nom Prénom", "{nom} {prénom}".format(**data["déclarant"])),
        ("Adresse mail", data.path("déclarant.email")),
    )
    pdf.write_table("Informations déclarant", cells)

    adresse = "{adresse} {code_postal} {commune}".format(**data["entreprise"])
    cells = [
        ("Structure", data.structure),
        ("Tranche effectifs", constants.EFFECTIFS.get(tranche_effectif)),
        ("Raison sociale", data.company),
        ("Siren", data.siren),
        ("Code NAF", data.naf),
        ("Adresse", adresse),
    ]
    if data.path("entreprise.ues.entreprises"):
        cells.append(("Nom UES", data.path("entreprise.ues.nom")))
        cells.append(
            (
                "Nombre d'entreprises composant l'UES",
                len(data.path("entreprise.ues.entreprises")) + 1,
            ),
        )
    pdf.write_table(
        "Périmètre retenu pour le calcul et la publication des indicateurs", cells
    )

    cells = (
        ("Année au titre de laquelle les indicateurs sont calculés", data.year),
        (
            "Date de fin de la période de référence",
            as_date(data.path("déclaration.fin_période_référence")),
        ),
        (
            "Nombre de salariés pris en compte pour le calcul des indicateurs",
            int(data.path("entreprise.effectif.total")),
        ),
    )
    pdf.write_table("Informations calcul et période de référence", cells)

    non_calculable = data.path("indicateurs.rémunérations.non_calculable")
    if non_calculable:
        cells = [("Motif de non calculabilité", non_calculable)]
    else:
        mode = data.path("indicateurs.rémunérations.mode")
        nb_niveaux = len(data.path("indicateurs.rémunérations.catégories"))
        cells = (
            ("Modalité de calcul", mode),
            (
                "Date de consultation du CSE",
                as_date(data.path("indicateurs.rémunérations.date_consultation_cse")),
            ),
            (
                "Nombre de niveaux ou coefficients",
                nb_niveaux if mode != "csp" else None,
            ),
            (
                "Résultat final en %",
                data.path("indicateurs.rémunérations.résultat"),
            ),
            (
                "Population envers laquelle l'écart est favorable",
                data.path("indicateurs.rémunérations.population_favorable"),
            ),
            (
                "Nombre de points obtenus",
                data.path("indicateurs.rémunérations.note"),
            ),
        )
    pdf.write_table("Indicateur relatif à l'écart de rémunération", cells)

    if tranche_effectif == "50:250":
        non_calculable = data.path(
            "indicateurs.augmentations_et_promotions.non_calculable"
        )
        if non_calculable:
            cells = [("Motif de non calculabilité", non_calculable)]
        else:
            cells = (
                (
                    "Résultat final en %",
                    data.path("indicateurs.augmentations_et_promotions.résultat"),
                ),
                (
                    "Résultat final en nombre équivalent de salariés",
                    data.path(
                        "indicateurs.augmentations_et_promotions.résultat_nombre_salariés"
                    ),
                ),
                (
                    "Population envers laquelle l'écart est favorable",
                    data.path(
                        "indicateurs.augmentations_et_promotions.population_favorable"
                    ),
                ),
                (
                    "Nombre de points obtenus sur le résultat final en pourcentage",
                    data.path(
                        "indicateurs.augmentations_et_promotions.note_en_pourcentage"
                    ),
                ),
                (
                    "Nombre de points obtenus sur le résultat final en nombre de salariés",
                    data.path(
                        "indicateurs.augmentations_et_promotions.note_nombre_salariés"
                    ),
                ),
                (
                    "Nombre de points obtenus",
                    data.path("indicateurs.augmentations_et_promotions.note"),
                ),
            )
        pdf.write_table(
            "Indicateur relatif à l'écart de taux d'augmentations individuelles",
            cells,
        )
    else:
        non_calculable = data.path("indicateurs.augmentations.non_calculable")
        if non_calculable:
            cells = [("Motif de non calculabilité", non_calculable)]
        else:
            cells = (
                (
                    "Résultat final en %",
                    data.path("indicateurs.augmentations.résultat"),
                ),
                (
                    "Population envers laquelle l'écart est favorable",
                    data.path("indicateurs.augmentations.population_favorable"),
                ),
                (
                    "Nombre de points obtenus",
                    data.path("indicateurs.augmentations.note"),
                ),
            )
        pdf.write_table(
            "Indicateur relatif à l'écart de taux d'augmentations individuelles "
            "(hors promotions)",
            cells,
        )

        pdf.write_headline("Indicateur relatif à l'écart de taux de promotions")
        non_calculable = data.path("indicateurs.promotions.non_calculable")
        if non_calculable:
            pdf.write_pair("Motif de non calculabilité", non_calculable)
        else:
            pdf.write_pair(
                "Résultat final en %", data.path("indicateurs.promotions.résultat")
            )
            pdf.write_pair(
                "Population envers laquelle l'écart est favorable",
                data.path("indicateurs.promotions.population_favorable"),
            )
            pdf.write_pair(
                "Nombre de points obtenus", data.path("indicateurs.promotions.note")
            )

    non_calculable = data.path("indicateurs.congés_maternité.non_calculable")
    if non_calculable:
        cells = [("Motif de non calculabilité", non_calculable)]
    else:
        cells = (
            ("Résultat final en %", data.path("indicateurs.congés_maternité.résultat")),
            (
                "Nombre de points obtenus",
                data.path("indicateurs.congés_maternité.note"),
            ),
        )
    pdf.write_table(
        "Indicateur relatif au % de salariées ayant bénéficié d'une augmentation dans "
        "l'année suivant leur retour de congé maternité",
        cells,
    )

    cells = (
        (
            "Résultat en nombre de salariés du sexe sous-représenté",
            data.path("indicateurs.hautes_rémunérations.résultat"),
        ),
        (
            "Sexe des salariés sur-représentés",
            data.path("indicateurs.hautes_rémunérations.population_favorable"),
        ),
        (
            "Nombre de points obtenus",
            data.path("indicateurs.hautes_rémunérations.note"),
        ),
    )
    pdf.write_table(
        "Indicateur relatif au nombre de salariés du sexe sous-représenté parmi les "
        "10 salariés ayant perçu les plus hautes rémunératons",
        cells,
    )

    cells = (
        ("Total de points obtenus", data.path("déclaration.points")),
        (
            "Nombre de points maximum pouvant être obtenus",
            data.path("déclaration.points_calculables"),
        ),
        ("Résultats final sur 100 points", data.grade),
        (
            "Mesures de corrections prévues",
            data.path("déclaration.mesures_correctives"),
        ),
    )
    pdf.write_table("Niveau de résultat global", cells)

    cells = (
        ("Date de publication", as_date(data.path("déclaration.publication.date"))),
        ("Site Internet de publication", data.path("déclaration.publication.url")),
        (
            "Modalités de communication auprès des salariés",
            data.path("déclaration.publication.modalités"),
        ),
    )
    pdf.write_table("Publication du niveau de résultat global", cells)
    return pdf, "declaration.pdf"
