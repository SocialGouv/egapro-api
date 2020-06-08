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

test:
	py.test -vvx
.PHONI: test
