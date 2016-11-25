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

ADD etc/snmp.conf /etc/snmp/

ADD . /tmp/snmpexporter
RUN make all install -C /tmp/snmpexporter && ls -laR /opt

EXPOSE 9190
CMD ["/opt/snmpexporter/snmpexporterd.py", \
  "--config", "/etc/snmpexporter/snmpexporter.yaml"]
