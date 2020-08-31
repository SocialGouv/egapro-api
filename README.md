# Egapro backend POC

## Dependencies

- python >= 3.6
- psql >= 9.4
- make >= 3.82 (with ONESHELL support, beware default macOS `make` is 3.81, brew will install it as `gmake`)

## Install

Create a PSQL database named `egapro`:

    createdb egapro

Create a virtualenv, then

    make develop
    make init

[Optional] Generate the naf CSV file:

    pip install -e .[naf]
    egapro generate_naf_csv


## Run server for development

    make serve


## Run tests

    pip install -e .[solen]
    createdb test_egapro
    make test
