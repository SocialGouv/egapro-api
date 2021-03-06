# API Egapro

## Schéma

- jsonschema : [https://index-egapro.travail.gouv.fr/api/jsonschema.json](https://index-egapro.travail.gouv.fr/api/jsonschema.json)
- Une version un peu plus "human readable" du schéma: [https://github.com/SocialGouv/egapro-api/blob/schema/egapro/schema/raw.yml](https://github.com/SocialGouv/egapro-api/blob/schema/egapro/schema/raw.yml)

À noter:

- pour les appels API, la source **doit** être `api`

## Racine de l'API

- Dev: `https://dev.egapro.fabrique.social.gouv.fr/api`
- Prod: `https://index-egapro.travail.gouv.fr/api`

## Endpoints

### /token
Pour demander un token.

Body attendu: `{"email": "foo@bar.org"}`

### /declaration/{siren}/{year}
Pour ajouter ou modifier une déclaration.

Où `siren` est le numéro de siren de l'entreprise ou UES déclarant, et `year` l'année de validité des indicateurs déclarés.

Pour aller voir les mails en dev:

https://mailtrap.dev.egapro.fabrique.social.gouv.fr/

(Demander un accès.)

## Process

1. Faire une demande de token sur /token, en passant un email dans un body json:

    `{"email": "foo@bar.org"}`

1. Récupérer le token envoyé par mail (via l'interface mailtrap)

1. Tester une déclaration sur `/declaration`, en passant le token via le header `API-KEY`
