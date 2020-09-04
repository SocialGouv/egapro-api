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
	from egapro.bin import migrate_legacy
	asyncio.run(migrate_legacy())
.PHONY: migrate-legacy

test:
	py.test -vvx
.PHONI: test
