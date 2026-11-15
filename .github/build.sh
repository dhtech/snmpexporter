#!/bin/sh
# Builds the Debian package. Runs INSIDE a debian:13 container, in the
# source tree, as the workflows start it:
#
#   docker run --rm -v "$PWD:/src" -w /src debian:13 sh .github/build.sh
#
# It runs the unit tests, compiles the MIB resolver with Debian 13's
# own compiler for Debian 13's own Python and Net-SNMP, takes the
# Net-SNMP Python module from our fork's release (below), and leaves in
# dist/:
#
#   snmpexporter_<version>_amd64.deb
#       /usr/sbin/snmpexporterd, /usr/bin/snmpexport   the two programs
#       /usr/lib/snmpexporter/                         their code, the
#           compiled mibresolver and the netsnmp module
#       /usr/lib/systemd/system/snmpexporterd@.service one per port
#       /etc/snmpexporter/snmpexporter.yaml            what is collected
#       /usr/share/doc/snmpexporter/                   licences, examples
#   SHA256SUMS
#
# A server that installs it needs no compiler and nothing from the
# internet but Debian's own packages. Whether it works is tried apart
# from here, on a machine that has only the package: .github/try.sh.
set -eu

# The Net-SNMP Python module ("netsnmp") is in no Debian package and on
# PyPI as source only. It comes from a release of our fork,
# github.com/dhtech/python3-netsnmp: a wheel built for Debian 13. The
# release and what its archive must hash to:
NETSNMP_TAG=v1.1a2-dh1
NETSNMP_ASSET=python3-netsnmp_1.1a2-dh1_debian13_amd64.tar.gz
NETSNMP_SHA256=3c93677960e36794e58d86ff492758563d88803eeb5866e4ad62eb2ded6902fa
# NETSNMP_WHEEL=<file> in the environment takes that wheel instead and
# downloads nothing - for a trial build only: such a package is marked
# and must not be released.

version=$(cat VERSION)
test -n "$version"

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q --no-install-recommends \
    gcc libc6-dev python3-dev python3-setuptools libsnmp-dev \
    python3-yaml ca-certificates

# the unit tests, as the Makefile runs them
for t in snmpexporter/*_test.py; do
    PYTHONPATH=$PWD python3 -B "$t"
done

# the MIB resolver, built away from the tree
rm -rf dist /tmp/build
mkdir -p /tmp/build/lib /tmp/build/tmp
(cd mibresolver && python3 setup.py -q build_ext \
    --build-lib /tmp/build/lib --build-temp /tmp/build/tmp)
resolver=$(ls /tmp/build/lib/mibresolver.*.so)
strip --strip-unneeded "$resolver"
echo "built: $resolver"

# the netsnmp module
if [ -n "${NETSNMP_WHEEL:-}" ]; then
    wheel=$NETSNMP_WHEEL
    netsnmp="a trial wheel, NOT the release $NETSNMP_TAG"
    echo "NETSNMP_WHEEL is set: $wheel - a trial build, not to be released"
else
    url="https://github.com/dhtech/python3-netsnmp/releases/download/$NETSNMP_TAG/$NETSNMP_ASSET"
    python3 - "$url" "/tmp/build/$NETSNMP_ASSET" <<'EOF'
import sys
import urllib.request
with urllib.request.urlopen(sys.argv[1], timeout=120) as f:
    data = f.read()
with open(sys.argv[2], 'wb') as out:
    out.write(data)
print('fetched %s (%d bytes)' % (sys.argv[1], len(data)))
EOF
    echo "$NETSNMP_SHA256  /tmp/build/$NETSNMP_ASSET" | sha256sum -c -
    mkdir /tmp/build/asset
    tar xzf "/tmp/build/$NETSNMP_ASSET" -C /tmp/build/asset
    wheel=$(ls /tmp/build/asset/python3_netsnmp-*.whl)
    netsnmp="python3-netsnmp $NETSNMP_TAG"
fi
mkdir /tmp/build/wheel
python3 -m zipfile -e "$wheel" /tmp/build/wheel/
binding=$(ls /tmp/build/wheel/netsnmp/client_intf.*.so)
ls /tmp/build/wheel/python3_netsnmp-*.dist-info/licenses/LICENSE

# what the package says it needs: this Python (the compiled modules are
# tied to it), Debian's Net-SNMP library, and the C library version the
# modules' symbols ask for
arch=$(dpkg --print-architecture)
python=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
python_next=$(python3 -c \
    'import sys; print("%d.%d" % (sys.version_info[0], sys.version_info[1] + 1))')
glibc=$(objdump -T "$resolver" "$binding" \
    | sed -n 's/.*(GLIBC_\([0-9.]*\)).*/\1/p' | sort -V | tail -1)
test -n "$glibc"
libfile=$(ldd "$resolver" | awk '/libnetsnmp\.so/ {print $3}')
test -n "$libfile"
libsnmp=$(dpkg-query -S "$(readlink -f "$libfile")" | cut -d: -f1)
test -n "$libsnmp"
# both modules must want the same library
ldd "$binding" | grep -qF "$libfile"

# the package's tree
root=/tmp/build/deb
lib=$root/usr/lib/snmpexporter
install -D -m 755 snmpexporterd.py "$lib/snmpexporterd.py"
install -D -m 755 snmpexport.py "$lib/snmpexport.py"
for f in snmpexporter/*.py; do
    case "$f" in *_test.py) continue ;; esac
    install -D -m 644 "$f" "$lib/$f"
done
install -D -m 644 "$resolver" "$lib/$(basename "$resolver")"
install -D -m 644 /tmp/build/wheel/netsnmp/__init__.py "$lib/netsnmp/__init__.py"
install -D -m 644 /tmp/build/wheel/netsnmp/client.py "$lib/netsnmp/client.py"
install -D -m 644 "$binding" "$lib/netsnmp/$(basename "$binding")"
install -D -m 755 packaging/snmpexporterd "$root/usr/sbin/snmpexporterd"
install -D -m 755 packaging/snmpexport "$root/usr/bin/snmpexport"
install -D -m 644 'packaging/snmpexporterd@.service' \
    "$root/usr/lib/systemd/system/snmpexporterd@.service"
install -D -m 644 etc/snmpexporter.yaml \
    "$root/etc/snmpexporter/snmpexporter.yaml"
doc=$root/usr/share/doc/snmpexporter
install -D -m 644 LICENSE "$doc/copyright"
install -D -m 644 \
    /tmp/build/wheel/python3_netsnmp-*.dist-info/licenses/LICENSE \
    "$doc/copyright.netsnmp"
install -D -m 644 README.md "$doc/README.md"
install -D -m 644 etc/auth.yaml "$doc/examples/auth.yaml"
install -D -m 644 packaging/default.example "$doc/examples/default"

size=$(du -sk "$root" | cut -f1)
mkdir "$root/DEBIAN"
sed -e "s/@VERSION@/$version/" -e "s/@ARCH@/$arch/" -e "s/@SIZE@/$size/" \
    -e "s/@PYTHON@/$python/" -e "s/@PYTHON_NEXT@/$python_next/" \
    -e "s/@GLIBC@/$glibc/" -e "s/@LIBSNMP@/$libsnmp/" \
    -e "s|@NETSNMP@|$netsnmp|" packaging/control.in > "$root/DEBIAN/control"
if grep -q '@[A-Z_]*@' "$root/DEBIAN/control"; then
    echo "packaging/control.in: something was not filled in"
    exit 1
fi
echo /etc/snmpexporter/snmpexporter.yaml > "$root/DEBIAN/conffiles"
install -m 755 packaging/postinst packaging/prerm packaging/postrm \
    "$root/DEBIAN/"

mkdir dist
deb="dist/snmpexporter_${version}_${arch}.deb"
dpkg-deb --root-owner-group --build "$root" "$deb"
dpkg-deb --info "$deb"
dpkg-deb --contents "$deb"

(cd dist && sha256sum ./*.deb > SHA256SUMS && cat SHA256SUMS && ls -l)
