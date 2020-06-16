class Data(dict):

    @property
    def validated(self):
        return self.get("declaration", {}).get("formValidated") == "Valid"

    @property
    def year(self):
        try:
            return self["informations"]["anneeDeclaration"]
        except KeyError:
            try:
                # OLD data.
                return int(self["informations"]["finPeriodeReference"][-4:])
            except KeyError:
                return None

    @property
    def siren(self):
        return self.get("informationsEntreprise", {}).get("siren")

    @property
    def email(self):
        return self.get("informationsDeclarant", {}).get("email")

    @property
    def company(self):
        return self.get("informationsEntreprise", {}).get("nomEntreprise")
