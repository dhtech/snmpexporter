#!/bin/sh
# Tries the package build.sh left in dist/, as a server would have it.
# Runs INSIDE a NEW debian:13 container - one with no compiler and
# nothing of the build in it:
#
#   docker run --rm -v "$PWD:/src:ro" -v "<MIB files>:/mibs:ro" \
#       -e TRY_MIBS=/mibs -w /src debian:13 sh .github/try.sh
#
# TRY_MIBS is a directory of standard MIB files (SNMPv2-SMI, SNMPv2-TC,
# SNMPv2-CONF, SNMPv2-MIB, IANAifType-MIB, IF-MIB at the least; the
# package holds none, and Debian ships none).
#
# The package installs with apt, which fetches what it depends on. The
# compiled modules load and resolve names from the MIB files. Then the
# real thing: Debian's snmpd runs here as the device, snmpexporterd is
# started as the unit starts it, and a probe over HTTP - SNMPv3 and
# SNMPv2c - comes back as metrics with names from the MIBs and the
# interface's name joined on. snmpexport does the same by hand. And the
# package can be removed again.
set -eu

: "${TRY_MIBS:?TRY_MIBS must name a directory of standard MIB files}"
ls "$TRY_MIBS" | grep -q '^IF-MIB' || {
    echo "$TRY_MIBS holds no IF-MIB"; exit 1; }

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q --no-install-recommends \
    ./dist/snmpexporter_*_"$(dpkg --print-architecture)".deb snmpd
dpkg -s snmpexporter | grep -E '^(Status|Version|Depends):'
if command -v gcc >/dev/null 2>&1; then
    echo "there is a compiler here: this is not a machine with only the package"
    exit 1
fi
id snmpexporter
test "$(stat -c '%U:%G %a' /etc/snmpexporter)" = 'root:snmpexporter 750'

# this machine's settings, as a server's configuration would write them
cat > /etc/default/snmpexporter <<EOF
MIBDIRS=$TRY_MIBS
MIBS=ALL
SNMPEXPORTERD_OPTS="--address 127.0.0.1 --poller-pool=4"
EOF
install -m 640 -g snmpexporter tests/e2e/auth.yaml /etc/snmpexporter/auth.yaml
# the package's collection file plus one collection for a Linux agent
cat /etc/snmpexporter/snmpexporter.yaml tests/e2e/collection.yaml \
    > /etc/snmpexporter/try.yaml

# 1. the compiled modules load, away from the source tree, and the
#    resolver names an object and its values from the MIB files
(cd / && MIBDIRS=$TRY_MIBS MIBS=ALL python3 -B - <<'EOF'
import sys
sys.path.insert(0, '/usr/lib/snmpexporter')
import mibresolver
import netsnmp
import snmpexporter
print('mibresolver:', mibresolver.__file__)
print('netsnmp:', netsnmp.__file__)
name, enum = mibresolver.resolve('.1.3.6.1.2.1.2.2.1.8.1')
print(name, enum)
assert name == 'IF-MIB::ifOperStatus.1', name
assert enum.get('1') == 'up' and enum.get('2') == 'down', enum
assert mibresolver.resolve('not an oid') is None
EOF
)

# 2. the device: Debian's snmpd
snmpd -f -Lo -C -c tests/e2e/snmpd.conf -p /run/try-snmpd.pid \
    > /tmp/snmpd.log 2>&1 &
agent=$!
daemons=""
stop() {
    # shellcheck disable=SC2086
    kill $daemons "$agent" 2>/dev/null || true
}
fail() { stop; for f in /tmp/snmpd.log /tmp/9190.log /tmp/9191.log; do
    [ -f "$f" ] && { echo "--- $f"; tail -40 "$f"; }; done; exit 1; }

# 3. snmpexporterd, as the unit starts it: the account, the state
#    directory, the command
grep -xF 'ExecStart=/usr/sbin/snmpexporterd --port %i' \
    /usr/lib/systemd/system/snmpexporterd@.service
grep -xF 'User=snmpexporter' /usr/lib/systemd/system/snmpexporterd@.service
start() {  # port [VAR=value ...]
    port=$1; shift
    install -d -o snmpexporter -g snmpexporter "/var/lib/snmpexporter/$port"
    setpriv --reuid snmpexporter --regid snmpexporter --init-groups env \
        "SNMP_PERSISTENT_DIR=/var/lib/snmpexporter/$port" "$@" \
        /usr/sbin/snmpexporterd --port "$port" > "/tmp/$port.log" 2>&1 &
    daemons="$daemons $!"
}
check() { python3 -B tests/e2e/check.py "$@" || fail; }

# with the package's own collection file: it is read, the agent is
# asked and answers (a Linux agent has nothing of what that file
# collects from every device, so no metric is expected)
start 9190
check http://127.0.0.1:9190/healthy --wait 60 --has '^I am healthy'
check 'http://127.0.0.1:9190/probe?target=127.0.0.1&layer=try3' \
    --has '^snmp_export_errors 0$' --has '^snmp_export_timeouts 0$' \
    --has '^snmp_exported_metrics_count [0-9]+$'
# a layer nobody configured, and a request without its parameters
check 'http://127.0.0.1:9190/probe?target=127.0.0.1&layer=nosuch' \
    --status 500
check 'http://127.0.0.1:9190/probe?target=127.0.0.1' --status 400
# it listens where it was told to, and nowhere else
check "http://$(hostname -i | awk '{print $1}'):9190/healthy" --refused

# with the Linux collection: interface tables, the name joined on
start 9191 SNMPEXPORTER_CONFIG=/etc/snmpexporter/try.yaml
check http://127.0.0.1:9191/healthy --wait 60 --has '^I am healthy'
for layer in try3 try2; do
    check "http://127.0.0.1:9191/probe?target=127.0.0.1&layer=$layer" \
        --has '^# TYPE ifHCInOctets counter$' \
        --has '^ifOperStatus\{[^}]*interface="lo"[^}]*\} 1$' \
        --has '^ifOperStatus\{[^}]*enum="up"[^}]*\} 1$' \
        --has '^ifHCInOctets\{[^}]*interface="lo"[^}]*\} [0-9]+$' \
        --has '^snmp_export_errors 0$' --has '^snmp_export_timeouts 0$' \
        --lacks 'DUMMY-MIB'
done
# what it writes. A device that does not answer is ONE line, with the
# device in it and no traceback; an answer writes no line at all
# (nothing listens at 127.0.0.5)
check 'http://127.0.0.1:9191/probe?target=127.0.0.5&layer=try3' --status 500
test "$(grep -c 'Poller failed: ' /tmp/9191.log)" = 1 || {
    echo 'a silent device is not exactly one "Poller failed" line'; fail; }
grep -F 'Poller failed: ' /tmp/9191.log | grep -qF '127.0.0.5' || {
    echo 'the line does not name the device'; fail; }
if grep -F 'Traceback' /tmp/9191.log; then
    echo 'a traceback for a device that does not answer'; fail; fi
if grep -F 'GET /probe' /tmp/9190.log /tmp/9191.log; then
    echo 'a line for a request'; fail; fi
echo "a silent device is one line: $(grep -F 'Poller failed: ' /tmp/9191.log | cut -c1-120)"

# what it runs as
for pid in $daemons; do
    uid=$(awk '/^Uid:/ {print $2}' "/proc/$pid/status")
    test "$uid" = "$(id -u snmpexporter)" || { echo "pid $pid: uid $uid"; fail; }
done
echo "snmpexporterd runs as snmpexporter (uid $(id -u snmpexporter))"

# a poller process that dies takes the pool with it: the daemon says so
# and ends with a failure, for the unit to start it again
victim=${daemons##* }
worker=$(python3 -B - "$victim" <<'EOF2'
import os, sys
for pid in os.listdir('/proc'):
    if pid.isdigit():
        try:
            stat = open('/proc/%s/stat' % pid).read()
        except OSError:
            continue
        if stat.rsplit(')', 1)[1].split()[1] == sys.argv[1]:
            print(pid)
            break
EOF2
)
test -n "$worker" || { echo "the daemon $victim has no poller process"; fail; }
kill -9 "$worker"
check "http://127.0.0.1:9191/probe?target=127.0.0.1&layer=try3" --status 500
code=0; wait "$victim" || code=$?
test "$code" = 1 || { echo "the daemon ended with $code, not 1"; fail; }
grep -F 'The poller pool is broken' /tmp/9191.log || fail
daemons=${daemons% *}

# 4. one poll by hand
SNMPEXPORTER_CONFIG=/etc/snmpexporter/try.yaml \
    snmpexport --annotate 127.0.0.1 try2 > /tmp/by-hand.txt || fail
grep -E '^ifOperStatus\{.*interface="lo".*\} 1$' /tmp/by-hand.txt || fail
stop

# 5. and it goes away again
apt-get remove -y -q snmpexporter
test ! -e /usr/sbin/snmpexporterd
test ! -e /usr/lib/snmpexporter/snmpexporterd.py
test ! -e /usr/lib/systemd/system/snmpexporterd@.service
echo "ok: the package installs, polls and is removed"
