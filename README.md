# Egapro backend POC

## Dependencies

- python >= 3.6
- psql >= 9.4
- make >= 3.82 (with ONESHELL support, beware default macOS `make` is 3.81, brew will install it as `gmake`)
- libxml2-dev >= 2.9.10
- libxslt1-dev >= 1.1.29

## Install

Create a PSQL database named `egapro`:

    createdb egapro

Create a virtualenv, then

    make develop
    make init

## Run server for development

    egapro serve


## Run tests

    pip install -e .[solen]
    createdb test_egapro
    make test
