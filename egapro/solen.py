import csv
import dpath.util
import io
import math
import pandas
import sys

import minicli
import ujson as json
from collections import OrderedDict
from datetime import date, datetime, timedelta
from itertools import islice
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError
from progressist import ProgressBar
from xlrd.biffh import XLRDError

from . import db, models
from .schema.legacy import from_legacy
from . import schema

# Configuration de l'import CSV

CELL_SKIPPABLE_VALUES = [
    "",
    "-",
    "NC",
    "non applicable",
    "non calculable",
]  # équivalents cellules vides
DATE_FORMAT_INPUT = "%Y-%m-%d %H:%M:%S"  # format de date en entrée
DATE_FORMAT_OUTPUT = "%d/%m/%Y"  # format de date en sortie
DATE_FORMAT_OUTPUT_HEURE = "%d/%m/%Y %H:%M"  # format de date avec heure en sortie
EXCEL_NOM_FEUILLE_REPONDANTS = "BDD REPONDANTS"  # nom de feuille excel repondants
EXCEL_NOM_FEUILLE_UES = "BDD UES"  # nom de feuille excel UES
NON_RENSEIGNE = "<non renseigné>"  # valeur si champ requis absent
SOLEN_URL_PREFIX = "https://solen1.enquetes.social.gouv.fr/cgi-bin/HE/P?P="  # racine URL déclarations Solen
TRANCHE_50_250 = "De 50 à 250 inclus"  # valeur champ structure 50<250
TRANCHE_PLUS_DE_250 = "Plus de 250"  # valeur champ structure +250
# Les deux champs suivants ne sont présents que dans le nouvel export de solen pour l'année 2020 (année indicateur 2019)
TRANCHE_251_999 = "De 251 à 999 inclus"  # valeur champ structure 251<999
TRANCHE_PLUS_DE_1000 = "De 1000 ou plus"  # valeur champ structure +1000
UES_KEY = "__uesdata__"  # nom clé données UES (interne)
BLACKLIST = [
    "1162z18z2z43892z-1z6A87466E48",
    "1162z18z2z43896z-1z8C5A42A73E",
    "1162z18z2z53017z-1zC61ABCEC04",
    "1162z18z2z27263z-1zE73A11646D",
    "1162z18z2z30378z-1zD1D7636D6F",
    "1162z18z2z30018z-1zA4794A1867",
    "1162z18z2z28845z-1zBE03BDA89E",
    "1162z18z2z27431z-1z4F0B4CD997",
    "1162z18z2z50067z-1z104C6B8CFD",
    "1162z18z2z52337z-1z6DF5E5AF91",
    "1162z18z2z40476z-1z16AFC1301E",
    "1162z18z2z5403z-1z9D31F1423D",
    "1162z18z2z30138z-1z9652AE3AE8",
    "1162z18z2z54430z-1z00E5CEA9EF",
    "1162z18z2z4732z-1z33CBCD0807",
    "1162z18z2z51471z-1z0867DF90C4",
    "1162z18z2z2209z-1z56667B0CC3",
    "1162z18z2z55927z-1zEE48136274",
    "1162z18z2z54649z-1z219D57AE7C",
    "1162z18z2z7969z-1zECEE4FCAC8",
    "1162z18z2z49409z-1z94B5BC338C",
    "1162z18z2z4073z-1zD033056C10",
    "1162z18z2z4457z-1zA374FCCA17",
    "1162z18z2z43875z-1z869749F6A1",
    "1162z18z2z52778z-1z2D22200096",
    "1162z18z2z51291z-1zD087B0813A",
    "1162z18z2z28418z-1z20F31D7846",
    "1162z18z2z51984z-1zF2FCEE90B1",
    "1162z18z2z53610z-1z1347668B17",
    "1162z18z2z52903z-1z1D0503A580",
    "1162z18z2z49938z-1z3C8861FDDD",
    "1162z18z2z55406z-1zE96ED4B7ED",
    "1162z18z2z4646z-1zF01D5AB1E9",
    "1162z18z2z4650z-1zCE39A3ED7B",
    "1162z18z2z47746z-1zF9A6A3784B",
    "1162z18z2z50895z-1z2CA38C3D33",
    "1162z18z2z53787z-1zE6ED5618F6",
    "1162z18z2z8339z-1z519C65A0D3",
    "1162z18z2z427z-1z9B85189C25",
    "1162z18z2z49012z-1zDEF239F5BA",
    "1162z18z2z56333z-1z10C0B90FF7",
    "1162z18z2z49715z-1zC86F6E8DF7",
    "1162z18z2z49064z-1z4B2AC58346",
    "1162z18z2z4240z-1zC47CE4B6AE",
    "1162z18z2z3876z-1zCB1D8E903A",
    "1162z18z2z45052z-1zD6796813DF",
    "1162z18z2z30748z-1z293BA9EE00",
    "1162z18z2z49066z-1z2F2AD85ECD",
    "1162z18z2z6476z-1zC212FCB720",
    "1162z18z2z7164z-1z9E0B63098B",
    "1162z18z2z52985z-1zF227F99248",
    "1162z18z2z54718z-1zA36FC92CC5",
    "1162z18z2z52898z-1z8BE900E9D9",
    "1162z18z2z49801z-1z6C5C2E4567",
    "1162z18z2z382z-1zDFDB12936C",
    "1162z18z2z12807z-1zCB511B3BC9",
    "1162z18z2z386z-1zB6616D76EC",
    "1162z18z2z50541z-1z6DAF6DCDE7",
    "1162z18z2z52240z-1zD81F510481",
    "1162z18z2z53882z-1z319086B637",
    "1162z18z2z55141z-1z2C59D58F54",
]


class BaseLogger(object):
    """Classe de base pour logger les messages applicatifs, définissant les
    différents niveaux de messages à traiter.
    """

    def std(self, str):
        raise TypeError("La méthode 'std' doit être implémentée.")

    def error(self, str):
        raise TypeError("La méthode 'error' doit être implémentée.")

    def info(self, str):
        raise TypeError("La méthode 'info' doit être implémentée.")

    def success(self, str):
        raise TypeError("La méthode 'success' doit être implémentée.")

    def warn(self, str):
        raise TypeError("La méthode 'warn' doit être implémentée.")


class ConsoleLogger(BaseLogger):
    HEADER = "\033[95m"
    INFO = "\033[94m"
    SUCCESS = "\033[92m"
    WARNING = "\033[93m"
    ERROR = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

    def std(self, str):
        sys.stdout.write(str + "\n")
        sys.stdout.flush()

    def error(self, str):
        sys.stderr.write(f"{ConsoleLogger.ERROR}✖  {str}{ConsoleLogger.ENDC}\n")
        sys.stderr.flush()

    def info(self, str):
        sys.stdout.write(f"{ConsoleLogger.INFO}🛈  {str}{ConsoleLogger.ENDC}\n")
        sys.stdout.flush()

    def success(self, str):
        sys.stdout.write(f"{ConsoleLogger.SUCCESS}✓  {str}{ConsoleLogger.ENDC}\n")
        sys.stdout.flush()

    def warn(self, str):
        sys.stdout.write(f"{ConsoleLogger.WARNING}⚠️  {str}{ConsoleLogger.ENDC}\n")
        sys.stdout.flush()


class NoLogger(BaseLogger):
    def std(self, str):
        pass

    def error(self, str):
        pass

    def info(self, str):
        pass

    def success(self, str):
        pass

    def warn(self, str):
        pass


class AppError(RuntimeError):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors if errors is not None else []


class ExcelDataError(RuntimeError):
    pass


class ImporterError(RuntimeError):
    pass


class RowProcessorError(RuntimeError):
    pass


class RowProcessor:
    READ_FIELDS = set({})

    def __init__(self, logger, row, validator=None, debug=False):
        self.logger = logger
        if row is None:
            raise RowProcessorError("Échec d'import d'une ligne vide.")
        self.debug = debug
        self.row = row
        self.validator = validator
        self.record = {}

    def log(self, msg):
        if self.debug:
            self.logger.std(msg)

    def importField(self, csvFieldName, path, type=str):
        value = self.get(csvFieldName)
        if not value:
            return
        elif type != str:
            try:
                value = type(value)
            except ValueError:
                raise RowProcessorError(
                    f"Impossible de typer la valeur du champ '{csvFieldName}' ('{value}') en {type}"
                )

        return self.set(path, value)

    def importSexeSurRepresente(self, csvFieldName, path):
        # Note: si la valeur du champ n'est ni "Femmes" ni "Hommes" ni "Egalite", nous n'importons pas la donnée
        value = self.get(csvFieldName)
        if value in ["Femmes", "Hommes", "Egalite"]:
            return self.set(path, value.lower())

    def importBooleanField(self, csvFieldName, path, negate=False):
        # Note: si la valeur du champ n'est ni "Oui" ni "Non", nous n'importons pas la donnée
        if self.get(csvFieldName) == "Oui":
            return self.set(path, True if not negate else False)
        elif self.get(csvFieldName) == "Non":
            return self.set(path, False if not negate else True)

    def importDateField(self, csvFieldName, path, format=DATE_FORMAT_OUTPUT):
        date = self.get(csvFieldName)
        if date is None:
            return
        if not isinstance(date, datetime):
            try:
                date = datetime.strptime(date, DATE_FORMAT_INPUT)
            except (ValueError, TypeError) as err:
                raise RowProcessorError(
                    f"Impossible de traiter la valeur date '{date}': {err}"
                )
        return self.set(path, date.strftime(format))

    def importFloatField(self, csvFieldName, path):
        return self.importField(csvFieldName, path, type=float)

    def importIntField(self, csvFieldName, path, fromFloat=False):
        if fromFloat:
            type_ = lambda x: math.ceil(float(x))
        else:
            type_ = int
        return self.importField(csvFieldName, path, type=type_)

    def get(self, csvFieldName):
        if csvFieldName not in self.row:
            raise RowProcessorError(
                f"La ligne ne possède pas de champ '{csvFieldName}'."
            )
        if self.row[csvFieldName] in CELL_SKIPPABLE_VALUES:
            return None
        self.READ_FIELDS.add(csvFieldName)
        return self.row[csvFieldName]

    def set(self, path, value):
        self.log(f"set '{path}' to '{value}'")
        if value not in CELL_SKIPPABLE_VALUES:
            try:
                dpath.util.get(self.record, path)
                result = dpath.util.set(self.record, path, value)
            except KeyError:
                result = dpath.util.new(self.record, path, value)
            if result == 0:
                raise RowProcessorError(
                    f"Impossible de créer le chemin '{path}' à la valeur '{value}'."
                )
            return value

    def as_record(self):
        record = {"id": self.get("id"), "data": models.Data(from_legacy(self.record))}
        if self.validator:
            try:
                self.validator.validate(record)
            except ValidationError as err:
                raise RowProcessorError(
                    "\n   ".join(
                        [
                            f"Validation JSON échouée pour la directive '{err.validator}' :",
                            f"Message: {err.message}",
                            f"Chemin: {'.'.join(list(err.path))}",
                        ]
                    )
                )
        return record

    def importPeriodeDeReference(self):
        # Année et périmètre retenus pour le calcul et la publication des indicateurs
        # Selon le format (2019 ou 2020) la colonne s'appelle
        # "annee_indicateurs" ou "annee_indicateurs > Valeur numérique"
        if "annee_indicateurs" in self.row:
            annee_indicateur = self.importIntField(
                "annee_indicateurs", "informations/anneeDeclaration"
            )
        else:
            annee_indicateur = self.importIntField(
                "annee_indicateurs > Valeur numérique", "informations/anneeDeclaration"
            )

        # Compatibilité egapro de la valeur de tranche d'effectifs
        tranche = self.get("tranche_effectif")
        trancheEgapro = TRANCHE_PLUS_DE_250
        if tranche == TRANCHE_50_250:
            trancheEgapro = "50 à 250"
        elif tranche == TRANCHE_251_999:
            trancheEgapro = "251 à 999"
        elif tranche == TRANCHE_PLUS_DE_1000:
            trancheEgapro = "1000 et plus"
        elif tranche != TRANCHE_PLUS_DE_250:
            raise RowProcessorError(
                f"Tranche invalide: '{tranche}'; les valeurs supportées sont '{TRANCHE_50_250}', '{TRANCHE_PLUS_DE_250}', '{TRANCHE_251_999}' et '{TRANCHE_PLUS_DE_1000}'."
            )
        self.set("informations/trancheEffectifs", trancheEgapro)

        # Période de référence
        debut_pr = self.get("date_debut_pr > Valeur date")
        if self.get("periode_ref") == "ac":
            # année civile: 31 décembre de l'année précédent "annee_indicateurs"
            debutPeriodeReference = "01/01/" + str(annee_indicateur)
            finPeriodeReference = "31/12/" + str(annee_indicateur)
        elif debut_pr != "-":
            # autre période: rajouter un an à "date_debut_pr"
            date_debut_pr = datetime.strptime(debut_pr, DATE_FORMAT_INPUT)
            one_day = timedelta(days=1)
            debutPeriodeReference = date_debut_pr.strftime(DATE_FORMAT_OUTPUT)
            try:
                # One year later, but one day before: 01-01-2019 -> 31-12-2019
                finPeriodeReference = (
                    date_debut_pr.replace(year=date_debut_pr.year + 1) - one_day
                ).strftime(DATE_FORMAT_OUTPUT)
            except ValueError:
                # Special case for the month of february which doesn't always have the same number of days
                finPeriodeReference = date_debut_pr + (
                    date(date_debut_pr.year + 1, 3, 1) - date(date_debut_pr.year, 3, 1)
                )
        else:
            # autre période de référence sans début spécifié: erreur
            raise RowProcessorError(
                "\n   ".join(
                    [
                        "Données de période de référence incohérentes :",
                        f"Date début: {date_debut_pr}",
                        f"Année indicateur: {annee_indicateur}",
                    ]
                )
            )
        self.set("informations/debutPeriodeReference", debutPeriodeReference)
        self.set("informations/finPeriodeReference", finPeriodeReference)

        # Note: utilisation d'un nombre à virgule pour prendre en compte les temps partiels
        self.importFloatField(
            "nb_salaries > Valeur numérique", "effectif/nombreSalariesTotal"
        )

    def importInformationsDeclarant(self):
        # Identification du déclarant pour tout contact ultérieur
        self.importField("Nom", "informationsDeclarant/nom")
        self.importField("Prénom", "informationsDeclarant/prenom")
        self.importField("e-mail_declarant", "informationsDeclarant/email")
        self.importField("telephone", "informationsDeclarant/tel")

    def importInformationsEntrepriseOuUES(self):
        structure = self.importField("structure", "informationsEntreprise/structure")
        self.importField("nom_UES", "informationsEntreprise/nomUES")
        # Certaines déclarations ont mal renseigné la structure, donc on essaie
        # d'importer le plus de données possible
        if structure == "Entreprise":
            nom_entreprise = self.get("RS_ets") or self.get("nom_ets_UES")
            code_naf = self.get("Code NAF") or self.get("Code NAF de cette entreprise")
            siren = self.get("SIREN_ets") or self.get("SIREN_UES")
        else:
            nom_entreprise = self.get("nom_ets_UES") or self.get("RS_ets")
            code_naf = self.get("Code NAF de cette entreprise") or self.get("Code NAF")
            siren = self.get("SIREN_UES") or self.get("SIREN_ets")
        nom_entreprise and self.set(
            "informationsEntreprise/nomEntreprise", nom_entreprise
        )
        code_naf and self.set("informationsEntreprise/codeNaf", code_naf)
        siren and self.set("informationsEntreprise/siren", siren)

        # Import des données de l'UES
        self.importEntreprisesUES()

        # Champs communs Entreprise/UES
        self.importField("Reg", "informationsEntreprise/region")
        self.importField("dpt", "informationsEntreprise/departement")
        self.importField("Adr ets", "informationsEntreprise/adresse")
        self.importField("CP", "informationsEntreprise/codePostal")
        self.importField("Commune", "informationsEntreprise/commune")

    def importEntreprisesUES(self):
        sirenUES = self.get("SIREN_UES")
        uesData = self.row.get(UES_KEY)
        if not uesData:
            return
        # Note: toutes les cellules pour UES001 sont vides, nous commençons à UES002
        columns2_99 = ["UES{:02d}".format(x) for x in range(2, 100)]
        columns100_500 = ["UES{:03d}".format(x) for x in range(100, 501)]
        columns = columns2_99 + columns100_500
        entreprises = []
        for column in columns:
            value = uesData[column]
            if value == "":
                break
            split = value.strip().split("\n")
            if len(split) == 2:
                [raisonSociale, siren] = split
            elif len(split) == 1 and split[0].isdigit():
                (raisonSociale, siren) = (NON_RENSEIGNE, split[0])
            elif len(split) == 1:
                (raisonSociale, siren) = (split[0], NON_RENSEIGNE)
            else:
                raise RowProcessorError(
                    " ".join(
                        [
                            f"Impossible d'extraire les valeurs de la colonne '{column}' dans",
                            f"la feuille '{EXCEL_NOM_FEUILLE_UES}' pour l'entreprise dont le",
                            f"SIREN est '{sirenUES}'.",
                        ]
                    )
                )
            entreprises.append({"nom": raisonSociale, "siren": siren})
        # Ajouter l'entreprise déclarante pour l'UES au nombre d'entreprises de l'UES
        self.set("informationsEntreprise/nombreEntreprises", len(entreprises) + 1)
        self.set("informationsEntreprise/entreprisesUES", entreprises)

    def importPublicationResultat(self):
        # Publication de résultat de l'entreprise ou de l'UES
        self.importDateField(
            "date_publ_niv > Valeur date", "declaration/datePublication"
        )
        self.importField("site_internet_publ", "declaration/lienPublication")

    def setValeursTranche(self, niveau, path, index, fieldName, custom=False):
        niveaux = [
            niveau + " > -30",
            niveau + " > 30-39",
            niveau + " > 40-49",
            niveau + " > 50+",
        ]
        values = [self.get(col) for col in niveaux]
        tranches = [None, None, None, None]
        for trancheIndex, value in enumerate(values):
            tranches[trancheIndex] = {"trancheAge": trancheIndex}
            if value is not None:
                tranches[trancheIndex][fieldName] = float(value)
            payload = {"tranchesAges": tranches}
            if custom:
                payload["name"] = "niveau " + str(index + 1)
            else:
                payload["categorieSocioPro"] = index
        self.set(f"{path}/{index}", payload)

    def setValeursTranches(self, niveaux, path, fieldName, custom=False):
        self.set(path, [])
        for index, niveau in enumerate(niveaux):
            self.setValeursTranche(niveau, path, index, fieldName, custom)

    def importTranchesCsp(self):
        self.setValeursTranches(
            ["Ou", "Em", "TAM", "IC"],
            "indicateurUn/remunerationAnnuelle",
            "ecartTauxRemuneration",
        )

    def importTranchesCoefficients(self):
        nb_coef_raw = self.get("nb_coef_niv")
        try:
            nb_coef = int(nb_coef_raw)
        except TypeError:
            raise RowProcessorError(
                f"Impossible de prendre en charge une valeur 'nb_coef_niv' non-entière, ici '{nb_coef_raw}'."
            )
        except (KeyError, ValueError):
            raise RowProcessorError(
                "Valeur 'nb_coef_niv' manquante ou invalide, indispensable pour une déclaration par niveaux de coefficients"
            )
        niveaux = ["niv{:02d}".format(niv) for niv in range(1, nb_coef + 1)]
        self.setValeursTranches(
            niveaux, "indicateurUn/coefficient", "ecartTauxRemuneration", custom=True
        )

    def importIndicateurUn(self):
        # Indicateur 1 relatif à l'écart de rémunération entre les femmes et les hommes
        # Quatre items possibles :
        # - coef_niv: Par niveau ou coefficient hiérarchique en application de la classification de branche
        # - amc: Par niveau ou coefficient hiérarchique en application d'une autre méthode de cotation des postes
        # - csp: Par catégorie socio-professionnelle
        # - nc: L'indicateur n'est pas calculable
        # Mapping:
        # csp       -> indicateurUn/csp
        # coef_nif  -> indicateurUn/coefficients
        # nc et amc -> indicateurUn/autre
        modalite = self.get("modalite_calc_tab1")
        self.set("indicateurUn/csp", False)
        self.set("indicateurUn/coef", False)
        self.set("indicateurUn/autre", False)
        self.set("indicateurUn/nonCalculable", False)
        if modalite == "csp":
            self.set("indicateurUn/csp", True)
        elif modalite == "coef_niv":
            self.set("indicateurUn/coef", True)
        elif modalite == "amc":
            self.set("indicateurUn/autre", True)
        elif modalite == "nc":
            self.set("indicateurUn/nonCalculable", True)
        self.importIntField("nb_coef_niv", "indicateurUn/nombreCoefficients")
        self.importField("motif_non_calc_tab1", "indicateurUn/motifNonCalculable")
        self.importField(
            "precision_am_tab1", "indicateurUn/motifNonCalculablePrecision"
        )
        if modalite == "csp":
            self.importTranchesCsp()
        elif modalite != "nc":
            # Que ce soit par coefficients ou "autre" (amc) le résultat est le même
            self.importTranchesCoefficients()
        # Résultat
        self.importFloatField("resultat_tab1", "indicateurUn/resultatFinal")
        self.importSexeSurRepresente(
            "population_favorable_tab1", "indicateurUn/sexeSurRepresente"
        )
        self.importIntField("Indicateur 1", "indicateurUn/noteFinale")
        self.importDateField(
            "date_consult_CSE > Valeur date", "declaration/dateConsultationCSE"
        )

    def setValeursEcart(self, niveau, path, index, fieldName):
        categorie = {"categorieSocioPro": index}
        value = self.get(niveau)
        if value is not None:
            categorie[fieldName] = float(value)
        self.set(f"{path}/{index}", categorie)

    def setValeursEcarts(self, niveaux, path, fieldName):
        self.set(path, [])
        for index, niveau in enumerate(niveaux):
            self.setValeursEcart(niveau, path, index, fieldName)

    def importIndicateurDeux(self):
        # Indicateur 2 relatif à l'écart de taux d'augmentations individuelles (hors promotion) entre
        # les femmes et les hommes pour les entreprises ou UES de plus de 250 salariés
        # Calculabilité
        nonCalculable = self.importBooleanField(
            "calculabilite_indic_tab2_sup250",
            "indicateurDeux/nonCalculable",
            negate=True,
        )
        self.set("indicateurDeux/presenceAugmentation", not nonCalculable)
        self.importField(
            "motif_non_calc_tab2_sup250", "indicateurDeux/motifNonCalculable"
        )
        self.importField(
            "precision_am_tab2_sup250", "indicateurDeux/motifNonCalculablePrecision"
        )
        # Taux d'augmentation individuelle par CSP
        self.setValeursEcarts(
            ["Ou_tab2_sup250", "Em_tab2_sup250", "TAM_tab2_sup250", "IC_tab2_sup250"],
            "indicateurDeux/tauxAugmentation",
            "ecartTauxAugmentation",
        )
        # Résultats
        self.importFloatField("resultat_tab2_sup250", "indicateurDeux/resultatFinal")
        self.importSexeSurRepresente(
            "population_favorable_tab2_sup250", "indicateurDeux/sexeSurRepresente"
        )
        self.importIntField("Indicateur 2", "indicateurDeux/noteFinale")

    def importIndicateurTrois(self):
        # Indicateur 3 relatif à l'écart de taux de promotions entre les femmes et les hommes pour
        # les entreprises ou UES de plus de 250 salariés
        # Calculabilité
        nonCalculable = self.importBooleanField(
            "calculabilite_indic_tab3_sup250",
            "indicateurTrois/nonCalculable",
            negate=True,
        )
        self.set("indicateurTrois/presencePromotion", not nonCalculable)
        self.importField(
            "motif_non_calc_tab3_sup250", "indicateurTrois/motifNonCalculable"
        )
        self.importField(
            "precision_am_tab3_sup250", "indicateurTrois/motifNonCalculablePrecision"
        )
        # Ecarts de taux de promotions par CSP
        self.setValeursEcarts(
            ["Ou_tab3_sup250", "Em_tab3_sup250", "TAM_tab3_sup250", "IC_tab3_sup250"],
            "indicateurTrois/tauxPromotion",
            "ecartTauxPromotion",
        )
        # Résultats
        self.importFloatField("resultat_tab3_sup250", "indicateurTrois/resultatFinal")
        self.importSexeSurRepresente(
            "population_favorable_tab3_sup250", "indicateurTrois/sexeSurRepresente"
        )
        self.importIntField("Indicateur 3", "indicateurTrois/noteFinale")

    def importIndicateurDeuxTrois(self):
        # Indicateur 2 relatif à l'écart de taux d'augmentations individuelles (hors promotion)
        # entre les femmes et les hommes pour les entreprises ou UES de 50 à 250 salariés
        nonCalculable = self.importBooleanField(
            "calculabilite_indic_tab2_50-250",
            "indicateurDeuxTrois/nonCalculable",
            negate=True,
        )
        self.set("indicateurDeuxTrois/presenceAugmentationPromotion", not nonCalculable)
        self.importField(
            "motif_non_calc_tab2_50-250", "indicateurDeuxTrois/motifNonCalculable"
        )
        self.importField(
            "precision_am_tab2_50-250",
            "indicateurDeuxTrois/motifNonCalculablePrecision",
        )
        # Résultats
        self.importFloatField(
            "resultat_pourcent_tab2_50-250", "indicateurDeuxTrois/resultatFinalEcart"
        )
        self.importFloatField(
            "resultat_nb_sal_tab2_50-250",
            "indicateurDeuxTrois/resultatFinalNombreSalaries",
        )
        self.importSexeSurRepresente(
            "population_favorable_tab2_50-250", "indicateurDeuxTrois/sexeSurRepresente"
        )
        self.importIntField("Indicateur 2", "indicateurDeuxTrois/noteFinale")
        self.importIntField("Indicateur 2 PourCent", "indicateurDeuxTrois/noteEcart")
        self.importIntField(
            "Indicateur 2 ParSal", "indicateurDeuxTrois/noteNombreSalaries"
        )

    def importIndicateurQuatre(self):
        # Indicateur 4 relatif au pourcentage de salariées ayant bénéficié d'une
        # augmentation dans l'année suivant leur retour de congé de maternité
        #
        # Note: le fichier d'export Solen renseigne des jeux de colonnes distincts
        # pour les entreprises de 50 à 250 salariés et les entreprises de plus de
        # 250 salariés, mais nous les fusionnons ici.
        #
        if self.get("tranche_effectif") == TRANCHE_50_250:
            # Import des données pour les entreprises 50-250
            nonCalculable = self.importBooleanField(
                "calculabilite_indic_tab4_50-250",
                "indicateurQuatre/nonCalculable",
                negate=True,
            )
            self.importField(
                "motif_non_calc_tab4_50-250", "indicateurQuatre/motifNonCalculable"
            )
            self.importField(
                "precision_am_tab4_50-250",
                "indicateurQuatre/motifNonCalculablePrecision",
            )
            self.importFloatField(
                "resultat_tab4_50-250", "indicateurQuatre/resultatFinal"
            )
        else:
            # Import des données pour les entreprises 250+
            nonCalculable = self.importBooleanField(
                "calculabilite_indic_tab4_sup250",
                "indicateurQuatre/nonCalculable",
                negate=True,
            )
            self.importField(
                "motif_non_calc_tab4_sup250", "indicateurQuatre/motifNonCalculable"
            )
            self.importField(
                "precision_am_tab4_sup250",
                "indicateurQuatre/motifNonCalculablePrecision",
            )
            self.importFloatField(
                "resultat_tab4_sup250", "indicateurQuatre/resultatFinal"
            )
        self.importIntField("Indicateur 4", "indicateurQuatre/noteFinale")
        self.set("indicateurQuatre/presenceCongeMat", not nonCalculable)

    def importIndicateurCinq(self):
        self.importIntField(
            "resultat_tab5", "indicateurCinq/resultatFinal", fromFloat=True
        )
        self.importSexeSurRepresente(
            "sexe_sur_represente_tab5", "indicateurCinq/sexeSurRepresente"
        )
        self.importIntField("Indicateur 5", "indicateurCinq/noteFinale")

    def importNiveauDeResultatGlobal(self):
        self.importIntField("Nombre total de points obtenus", "declaration/totalPoint")
        self.importIntField(
            "Nombre total de points pouvant être obtenus",
            "declaration/totalPointCalculable",
        )
        self.importIntField("Résultat final sur 100 points", "declaration/noteIndex")
        self.importField("mesures_correction", "declaration/mesuresCorrection")

    def run(self):
        self.set("source", "solen")
        self.importDateField(
            "Date réponse > Valeur date",
            "declaration/dateDeclaration",
            format=DATE_FORMAT_OUTPUT_HEURE,
        )
        self.importInformationsDeclarant()
        self.importPeriodeDeReference()
        self.importInformationsEntrepriseOuUES()
        self.importPublicationResultat()
        self.importIndicateurUn()
        if self.get("tranche_effectif") == TRANCHE_50_250:
            self.importIndicateurDeuxTrois()
        else:
            self.importIndicateurDeux()
            self.importIndicateurTrois()
        self.importIndicateurQuatre()
        self.importIndicateurCinq()
        self.importNiveauDeResultatGlobal()

        return self.as_record()


def initValidator(jsonschema_path):
    with open(jsonschema_path, "r") as schema_file:
        return Draft7Validator(json.load(schema_file))


class ExcelData:
    def __init__(self, pathToExcelFile, logger=None):
        self.logger = logger
        try:
            excel = pandas.read_excel(
                pathToExcelFile,
                sheet_name=[EXCEL_NOM_FEUILLE_REPONDANTS, EXCEL_NOM_FEUILLE_UES],
                dtype={"CP": str, "telephone": str, "SIREN_ets": str, "SIREN_UES": str},
            )
        except XLRDError as err:
            raise ExcelDataError(
                f"Le format du fichier '{pathToExcelFile}' n'a pu être interprété: {err}"
            )
        self.fields = {
            EXCEL_NOM_FEUILLE_REPONDANTS: set([]),
            EXCEL_NOM_FEUILLE_UES: set([]),
        }
        self.repondants = self.importSheet(excel, EXCEL_NOM_FEUILLE_REPONDANTS)
        self.ues = self.importSheet(excel, EXCEL_NOM_FEUILLE_UES)
        self.linkUes()

    def importSheet(self, excel, sheetName):
        sheet = excel.get(sheetName)
        if sheet.empty:
            raise ExcelDataError(f"Feuille de calcul '{sheetName}' absente ou vide.")
        try:
            csvString = sheet.to_csv(float_format="%g")
            reader = csv.DictReader(io.StringIO(csvString))
            for field in reader.fieldnames:
                self.fields[sheetName].add(field)
            return self.createDict([row for row in reader])
        except (AttributeError, KeyError, IndexError, TypeError, ValueError) as err:
            raise ExcelDataError(
                f"Impossible de traiter la feuille de calcul '{sheetName}': {err}"
            )

    def createDict(self, source):
        dict = OrderedDict()
        for row in source:
            solenId = row["URL d'impression du répondant"].replace(SOLEN_URL_PREFIX, "")
            dict[solenId] = row
            dict[solenId]["id"] = solenId
        return dict

    def findUesById(self, id):
        found = self.ues.get(id)
        if not found and self.logger:
            self.logger.warn(
                f"Données UES non trouvées pour l'id {id}. Vérifiez la feuille {EXCEL_NOM_FEUILLE_UES}."
            )
        return found

    def linkUes(self):
        for id, row in self.repondants.items():
            if (
                row["structure"] == "Unité Economique et Sociale (UES)"
                or row["nom_UES"] != ""
            ):
                row[UES_KEY] = self.findUesById(id)
                self.repondants[id] = row

    def getNbRepondants(self):
        return len(self.repondants)


class App:
    def __init__(
        self,
        xls_path,
        max=0,
        siren=None,
        debug=False,
        progress=False,
        logger=None,
        json_schema=None,
    ):
        # arguments positionnels requis
        self.xls_path = xls_path
        # options
        self.max = max
        self.siren = siren
        self.debug = debug
        self.progress = progress
        self.logger = logger if logger else NoLogger()
        # initialisation des flags de lecture des champs CSV
        RowProcessor.READ_FIELDS = set({})
        # propriétés calculées de l'instance
        self.validator = None
        if json_schema:
            self.validator = initValidator(json_schema)
        try:
            self.excelData = ExcelData(self.xls_path, self.logger)
        except ExcelDataError as err:
            raise AppError(f"Erreur de traitement du fichier '{xls_path}': {err}")
        self.nb_rows = self.excelData.getNbRepondants()
        self.records = self.__prepareRecords(max=max, siren=siren)

    def __prepareRecords(self, max=None, siren=None):
        errors = []
        records = []
        rows = self.excelData.repondants
        if max:
            rows = OrderedDict(islice(rows.items(), max))
        elif siren is not None:
            rows = OrderedDict(
                filter(
                    lambda r: r[1]["SIREN_ets"] == siren or r[1]["SIREN_UES"] == siren,
                    rows.items(),
                )
            )
        if not bool(
            rows
        ):  # test d'un OrderedDict vide https://stackoverflow.com/a/23177452/330911
            raise AppError(
                f"Aucune déclaration trouvée pour les critères siren={siren} et max={max}."
            )
        if self.progress:
            bar = ProgressBar(
                prefix="Préparation des enregistrements",
                total=max or self.nb_rows,
                throttle=100,
            )
        for lineno, id in enumerate(rows):
            try:
                records.append(
                    RowProcessor(
                        self.logger,
                        rows[id],
                        self.validator,
                        self.debug,
                    ).run()
                )
            except RowProcessorError as err:
                errors.append(f"Erreur ligne {lineno} (id={id}): {err}")
            if self.progress:
                next(bar)
        if self.progress:
            bar.finish()
        if len(errors) > 0:
            raise AppError(
                "Erreur(s) rencontrée(s) lors de la préparation des enregistrements",
                errors=errors,
            )
        return records

    async def run(self, force=False):
        missing_owner = []
        skipped = []
        bar = ProgressBar(prefix="Import…", total=len(self.records), throttle=100)
        for record in bar.iter(self.records):
            id_ = record["id"]
            if id_ in BLACKLIST:
                continue
            record["data"]["id"] = id_
            year = record["data"].year
            siren = record["data"].siren
            owner = record["data"].email
            # fmt: off
            modified_at = datetime.fromisoformat(record["data"].path("déclaration.date"))
            # fmt: on
            if not owner:
                missing_owner.append((siren, year))
                continue
            try:
                schema.validate(record["data"].raw)
                schema.cross_validate(record["data"].raw)
            except ValueError as err:
                print(siren, year, err)
                continue
            try:
                declaration = await db.declaration.get(siren, year)
            except db.NoData:
                current = None
            else:
                current = declaration["modified_at"]
            # Allow to compare aware datetimes.
            if not current or modified_at > current or force:
                await db.declaration.put(
                    siren, year, owner, record["data"], modified_at
                )
            else:
                skipped.append((siren, year))
        print("Missing owner:")
        print(missing_owner)
        print("Skipped:")
        print(skipped)


@minicli.cli(name="import-solen")
async def main(
    path,
    debug=False,
    indent=None,
    max=0,
    show_json=False,
    info=False,
    output="",
    dry_run=False,
    progress=False,
    siren=None,
    json_schema=None,
    force=False,
):
    """Import des données Solen.

    :path:          chemin vers l'export Excel Solen
    :debug:         afficher les messages de debug
    :indent:        niveau d'indentation JSON
    :max:           nombre maximum de lignes à importer
    :show_json:     afficher la sortie JSON
    :info:          afficher les informations d'utilisation des champs
    :output:        sauvegarder la sortie JSON, CSV ou XLSX dans un fichier
    :dry_run:       ne pas procéder à l'import dans la base de données
    :progress:      afficher une barre de progression
    :siren:         importer le SIREN spécifié uniquement
    :json_schema:   chemin vers le schema json à utiliser pour la validation
    """

    logger = ConsoleLogger()
    try:
        app = App(
            path,
            max=max,
            siren=siren,
            debug=debug,
            progress=progress,
            logger=logger,
            json_schema=json_schema,
        )

        if show_json:
            logger.std(json.dumps(app.records, indent=indent))

        if info:
            logger.info(
                "Informations complémentaires sur l'extraction des données Excel :"
            )
            for message in app.getStats():
                logger.info(message)

        if output:
            if output.endswith(".json"):
                with open(output, "w") as json_file:
                    json_file.write(app.toJSON(indent=indent))
                logger.success(
                    f"Enregistrements JSON exportés dans le fichier '{output}'."
                )
            elif output.endswith(".csv"):
                with open(output, "w") as csv_file:
                    csv_file.write(app.toCSV())
                logger.success(
                    f"Enregistrements CSV exportés dans le fichier '{output}'."
                )
            elif output.endswith(".xlsx"):
                app.toXLSX(output)
                logger.success(
                    f"Enregistrements XLSX exportés dans le fichier '{output}'."
                )
            else:
                raise AppError(
                    "Seuls les formats JSON, CSV et XLSX sont supportés pour la sauvegarde."
                )

        if not dry_run:
            logger.info("Import en base (cela peut prendre plusieurs minutes)...")
            await app.run(force)
            logger.success("Import effectué.")

    except AppError as err:
        logger.error(err)
        for error in err.errors:
            logger.error(error)
        exit(1)

    except KeyboardInterrupt:
        logger.std("")
        logger.warn("Script d'import interrompu.")
        exit(1)
