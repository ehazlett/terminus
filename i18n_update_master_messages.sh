#!/bin/sh

pybabel extract -F babel.cfg -o messages.pot .
pybabel extract -F babel.cfg -k lazy_gettext -o messages.pot .
