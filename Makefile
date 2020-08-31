.ONESHELL:

develop:
	pip install -e .[dev,test]

serve: SHELL := python3
serve:
	from egapro import serve
	serve(reload=True)
.PHONY: serve

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
	py.test -vvx
.PHONY: test
