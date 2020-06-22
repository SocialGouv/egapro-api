class Data(dict):
    @property
    def id(self):
        return self.get("id")

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

    def path(self, path):
        data = self
        for sub in path.split("."):
            data = data.get(sub, {})
        return data if data or data in [False, 0] else None
