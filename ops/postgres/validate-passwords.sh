#!/bin/sh
# Refuse credentials that would change the structure of Compose's application URLs.
set -eu
for value in "$MENDEL_DB_PASSWORD" "$WIENER_DB_PASSWORD"; do
  case "$value" in
    ''|*[!A-Za-z0-9_-]*)
      echo 'Application database passwords must use only letters, digits, _ and -.' >&2
      exit 1
      ;;
  esac
done
