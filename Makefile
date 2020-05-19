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
	from egapro import config, db
	config.init()
	db.init()
.PHONY: init
