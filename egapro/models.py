class Data(dict):

    # Emulate **kwargs.
    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            return super().__getitem__(key)

    def keys(self):
        keys = set(super().keys())
        # Extend with custom properties.
        return keys | (set(dir(self)) - set(dir(dict)))

    def __iter__(self):
        yield from self.keys()
        # End emulate **kwargs.

    @property
    def id(self):
        return self.get("id")

    @property
    def validated(self):
        return self.path("declaration.formValidated") == "Valid"

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
        return self.path("informationsEntreprise.siren")

    @property
    def email(self):
        return self.path("informationsDeclarant.email")

    @property
    def company(self):
        return self.path("informationsEntreprise.nomEntreprise")

    @property
    def region(self):
        return self.path("informationsEntreprise.region")

    @property
    def departement(self):
        return self.path("informationsEntreprise.departement")

    @property
    def structure(self):
        return self.path("informationsEntreprise.structure")

    @property
    def ues(self):
        return self.path("informationsEntreprise.nomUES")

    @property
    def grade(self):
        return self.path("declaration.noteIndex")

    def path(self, path):
        data = self
        for sub in path.split("."):
            data = data.get(sub, {})
        return data if data or data in [False, 0] else None
