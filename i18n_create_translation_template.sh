#!/bin/sh

if [ ! $1 ]; then 
  echo "Usage: $0 <language_code>"
  exit 1
fi

pybabel init -i messages.pot -d translations -l $1

