FROM python:3-alpine

RUN apk add --update gcc net-snmp-tools net-snmp-dev musl-dev make findutils \
  wget && \
  pip3 install python3-netsnmp --pre && \
  pip3 install coverage pyyaml twisted && \
  ln -sf /usr/local/bin/coverage3 /usr/local/bin/python3-coverage

RUN (mkdir -p /var/lib/mibs/std /tmp/librenms; cd /tmp/librenms; \
  wget https://github.com/librenms/librenms/archive/master.zip 2>&1 && \
  unzip master.zip && mv librenms-master/mibs/* /var/lib/mibs/std/) && \
  rm -r /tmp/librenms

ADD . /tmp/snmpexporter

RUN (cd /tmp/snmpexporter/mibresolver; python3 setup.py build install)

RUN make test -C /tmp/snmpexporter 2> /dev/null && \
  mkdir -p /opt/snmpexporter/ && \
  find /tmp/snmpexporter/ -name \*.py -not -name \*_test\* -not -name setup.py \
  -printf '%P\n' | \
  xargs -I{} install -m0644 -D /tmp/snmpexporter/{} /opt/snmpexporter/{} && \
  rm -fr /tmp/snmpexporter/ && \
  chmod +x /opt/snmpexporter/snmpexport.py /opt/snmpexporter/snmpexporterd.py && \
  ls -laR /opt

add etc/snmp.conf /etc/snmp/
ADD etc/snmpexporter.yaml /etc/snmpexporter/

EXPOSE 9190
CMD ["/opt/snmpexporter/snmpexporterd.py", \
  "--config", "/etc/snmpexporter/snmpexporter.yaml"]
