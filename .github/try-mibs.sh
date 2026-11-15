#!/bin/sh
# Fetches the few standard MIB files .github/try.sh needs into the
# directory named as the argument. Runs on the workflow's runner, not
# in the containers. The package holds no MIB files and Debian ships
# none; these come from LibreNMS' collection, at one release of it:
#
#   sh .github/try-mibs.sh mibs
set -eu
LIBRENMS=26.10.2
dir=${1:?the directory to fill}
mkdir -p "$dir"
for mib in SNMPv2-SMI SNMPv2-TC SNMPv2-CONF SNMPv2-MIB IANAifType-MIB IF-MIB; do
    curl --fail --silent --show-error --location --retry 3 \
        -o "$dir/$mib" \
        "https://raw.githubusercontent.com/librenms/librenms/$LIBRENMS/mibs/$mib"
    grep -Eq "^[[:space:]]*$mib DEFINITIONS" "$dir/$mib" || {
        echo "$mib: not the MIB module of that name"; exit 1; }
done
ls -l "$dir"
