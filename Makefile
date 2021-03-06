.ONESHELL:

develop:
	pip install -e .[dev,test,solen]

init: SHELL := python3
init:
	import asyncio
	from egapro import init
	asyncio.run(init())
.PHONY: init

migrate-legacy: SHELL := python3
migrate-legacy:
	import asyncio
	from egapro.bin import migrate_from_legacy
	asyncio.run(migrate_from_legacy())
.PHONY: migrate-legacy

test:
	py.test -vv --cov
.PHONY: test

download-data:
	scp egapro.prod:/srv/egapro/data/dgt.xlsx tmp/

download-db:
	ssh egapro.dev "set -o allexport; source /srv/egapro/env; set +o allexport; PGPASSWORD=\$$EGAPRO_DBPASS pg_dump  --host \$$EGAPRO_DBHOST --user \$$EGAPRO_DBUSER \$$EGAPRO_DBNAME --file /tmp/dump.sql"

restore-db:
	pg_restore -d egapro -S postgres --clean --table declaration --table simulation tmp/dump.psql

deploy-docs:
	mkdocs gh-deploy
