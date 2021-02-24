from datetime import datetime
from pathlib import Path

from fpdf import fpdf

from egapro import constants


# Disabled, waiting for new release so we can control the cache path.
fpdf.FPDF_CACHE_MODE = 1


def as_date(s):
    return datetime.fromisoformat(s).date().strftime("%d/%m/%Y")


class PDF(fpdf.FPDF):
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
        self.cell(0, 10, "Page " + str(self.page_no()) + "/{nb}", 0, 0, "C")

    def write_pair(self, key, value):
        line_height = self.font_size * 2.1
        self.set_font("Marianne", "B", 11)
        # self.multi_cell(0, h=5, txt=f"{key} ")
        cell_width = self.epw / 2
        self.multi_cell(cell_width, line_height, f"{key} ", border=0, ln=3, max_line_height=self.font_size)
        self.set_font("Marianne", "", 11)
        if value is None:
            value = " - "
        # self.multi_cell(0, h=5, txt=str(value), align="R", ln=3)
        self.multi_cell(cell_width, line_height, str(value), border=0, ln=3, max_line_height=self.font_size, align="R")
        self.ln(line_height)

    def write_headline(self, value):
        self.ln(8)
        self.set_font("Marianne", "B", 14)
        self.write(6, str(value))
        self.ln(6)
        self.line(self.l_margin, self.y, self.w - self.r_margin, self.y)
        self.ln(2)


def attachment(data):
    pdf = PDF()
    root = Path(__file__).parent
    pdf.add_font("Marianne", "", root / "font/Marianne-Regular.ttf", uni=True)
    pdf.add_font("Marianne", "I", root / "font/Marianne-RegularItalic.ttf", uni=True)
    pdf.add_font("Marianne", "B", root / "font/Marianne-Bold.ttf", uni=True)
    pdf.add_font("Marianne", "BI", root / "font/Marianne-BoldItalic.ttf", uni=True)
    pdf.set_title(f"Index Egapro {data.siren}/{data.year}")
    pdf.add_page()
    tranche_effectif = data.path("entreprise.effectif.tranche")

    pdf.write_headline("Informations déclarant")
    name = "{nom} {prénom}".format(**data["déclarant"])
    pdf.write_pair("Nom Prénom", name)
    pdf.write_pair("Adresse mail", data.path("déclarant.email"))

    pdf.write_headline(
        "Périmètre retenu pour le calcul et la publication des indicateurs"
    )
    pdf.write_pair("Structure", data.structure)
    pdf.write_pair("Tranche effectifs", constants.EFFECTIFS.get(tranche_effectif))
    pdf.write_pair("Raison sociale", data.company)
    pdf.write_pair("Siren", data.siren)
    pdf.write_pair("Code NAF", data.naf)
    adresse = "{adresse} {code_postal} {commune}".format(**data["entreprise"])
    pdf.write_pair("Année de calcul", data.year)
    pdf.write_pair("Adresse", adresse)
    if data.path("entreprise.ues.entreprises"):
        pdf.write_pair("Nom UES", data.path("entreprise.ues.nom"))
        pdf.write_pair(
            "Nombre d'entreprises composant l'UES",
            len(data.path("entreprise.ues.entreprises")),
        )
    pdf.write_headline("Informations calcul et période de référence")
    pdf.write_pair(
        "Année au titre de laquelle les indicateurs sont calculés", data.year
    )
    pdf.write_pair(
        "Date de fin de la période de référence",
        as_date(data.path("déclaration.fin_période_référence")),
    )
    pdf.write_pair(
        "Nombre de salariés pris en compte pour le calcul des indicateurs",
        data.path("entreprise.effectif.total"),
    )

    if tranche_effectif == "50:250":
        pdf.write_headline(
            "Indicateur relatif à l'écart de taux d'augmentations individuelles "
            "entre les femmes et les hommes"
        )
        non_calculable = data.path(
            "indicateurs.augmentations_et_promotions.non_calculable"
        )
        if non_calculable:
            pdf.write_pair("Motif de non calculabilité", non_calculable)
        else:
            pdf.write_pair(
                "Résultat final en %",
                data.path("indicateurs.augmentations_et_promotions.résultat"),
            )
            pdf.write_pair(
                "Résultat final en nombre équivalent de salariés",
                data.path(
                    "indicateurs.augmentations_et_promotions.résultat_nombre_salariés"
                ),
            )
            pdf.write_pair(
                "Population envers qui l'écart est favorable",
                data.path(
                    "indicateurs.augmentations_et_promotions.population_favorable"
                ),
            )
            pdf.write_pair(
                "Nombre de points obtenus sur le résultat final en pourcentage",
                data.path(
                    "indicateurs.augmentations_et_promotions.note_en_pourcentage"
                ),
            )
            pdf.write_pair(
                "Nombre de points obtenus sur le résultat final en nombre de salariés",
                data.path(
                    "indicateurs.augmentations_et_promotions.note_nombre_salariés"
                ),
            )
            pdf.write_pair(
                "Nombre de points obtenus",
                data.path("indicateurs.augmentations_et_promotions.note"),
            )
        pdf.ln(20)  # Force page break
    else:
        pdf.write_headline("Indicateur relatif à l'écart de rémunération")
        non_calculable = data.path("indicateurs.rémunérations.non_calculable")
        if non_calculable:
            pdf.write_pair("Motif de non calculabilité", non_calculable)
        else:
            pdf.write_pair(
                "Modalité de calcul", data.path("indicateurs.rémunérations.mode")
            )
            pdf.write_pair(
                "Date de consultation du CSE",
                data.path("indicateurs.rémunérations.date_consultation_cse"),
            )
            pdf.write_pair(
                "Nombre de niveaux ou coefficients",
                len(data.path("indicateurs.rémunérations.catégories")),
            )
            pdf.write_pair(
                "Résultat final en %", data.path("indicateurs.rémunérations.résultat")
            )
            pdf.write_pair(
                "Population envers qui l'écart est favorable",
                data.path("indicateurs.rémunérations.population_favorable"),
            )
            pdf.write_pair(
                "Nombre de points obtenus", data.path("indicateurs.rémunérations.note")
            )

        pdf.write_headline(
            "Indicateur relatif à l'écart de taux d'augmentations individuelles"
        )
        non_calculable = data.path("indicateurs.augmentations.non_calculable")
        if non_calculable:
            pdf.write_pair("Motif de non calculabilité", non_calculable)
        else:
            pdf.write_pair(
                "Résultat final en %", data.path("indicateurs.augmentations.résultat")
            )
            pdf.write_pair(
                "Population envers qui l'écart est favorable",
                data.path("indicateurs.augmentations.population_favorable"),
            )
            pdf.write_pair(
                "Nombre de points obtenus", data.path("indicateurs.augmentations.note")
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
                "Population envers qui l'écart est favorable",
                data.path("indicateurs.promotions.population_favorable"),
            )
            pdf.write_pair(
                "Nombre de points obtenus", data.path("indicateurs.promotions.note")
            )

    pdf.write_headline(
        "Indicateur relatif au % de salariées ayant bénéficié d'une augmentation dans "
        "l'année suivant leur retour de congé maternité"
    )
    non_calculable = data.path("indicateurs.congés_maternité.non_calculable")
    if non_calculable:
        pdf.write_pair("Motif de non calculabilité", non_calculable)
    else:
        pdf.write_pair(
            "Résultat final en %", data.path("indicateurs.congés_maternité.résultat")
        )
        pdf.write_pair(
            "Population envers qui l'écart est favorable",
            data.path("indicateurs.congés_maternité.population_favorable"),
        )
        pdf.write_pair(
            "Nombre de points obtenus", data.path("indicateurs.congés_maternité.note")
        )
    pdf.write_headline(
        "Indicateur relatif au nombre de salariés du sexe sous-représenté parmi les "
        "10 salariés ayant perçu les plus hautes rémunératons"
    )
    pdf.write_pair(
        "Résultat final en %", data.path("indicateurs.hautes_rémunérations.résultat")
    )
    pdf.write_pair(
        "Sexe des salariés sur-représentés",
        data.path("indicateurs.hautes_rémunérations.population_favorable"),
    )
    pdf.write_pair(
        "Nombre de points obtenus", data.path("indicateurs.hautes_rémunérations.note")
    )

    pdf.write_headline("Niveau de résultat global")
    pdf.write_pair("Total de points obtenus", data.path("déclaration.points"))
    pdf.write_pair(
        "Nombre de points maximum pouvant être obtenus",
        data.path("déclaration.points_calculables"),
    )
    pdf.write_pair("Résultats final sur 100 points", data.grade)
    pdf.write_pair(
        "Mesures de corrections prévues", data.path("déclaration.mesures_correctives")
    )
    pdf.write_pair("Date de déclaration", as_date(data.path("déclaration.date")))

    pdf.write_headline("Publication du niveau de résultat global")
    pdf.write_pair(
        "Date de publication", as_date(data.path("déclaration.publication.date"))
    )
    pdf.write_pair(
        "Site Internet de publication", data.path("déclaration.publication.url")
    )
    pdf.write_pair(
        "Modalités de communication auprès des salariés",
        data.path("déclaration.publication.modalités"),
    )
    return pdf, "declaration.pdf"
