# Egapro backend POC

## Dependencies

- python >= 3.6
- psql >= 9.4
- make >= 3.82 (with ONESHELL support)

## Install

Create a PSQL database named `egapro`:

    createdb egapro

Create a virtualenv, then

    make develop
    make init

## Run server for development

    make serve


## Run tests

    make test
