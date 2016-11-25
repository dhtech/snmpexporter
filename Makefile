COVERAGE ?= 'python3-coverage'
export PYTHONPATH=$(CURDIR)

all: test

install:
	make -C $(CURDIR)/mibresolver $@
	mkdir -p $(DESTDIR)/opt/snmpexporter/
	find . -name \*.py -not -name \*_test\* -not -name setup.py \
	  -printf '%P\n' | \
	  xargs -I{} install -m0644 -D {} $(DESTDIR)/opt/snmpexporter/{}
	chmod +x $(DESTDIR)/opt/snmpexporter/snmpexport.py \
	  $(DESTDIR)/opt/snmpexporter/snmpexporterd.py
	install -m600 etc/snmpexporter.yaml $(DESTDIR)/etc/

clean:
	rm -f .coverage
	make -C $(CURDIR)/mibresolver $@

distclean: clean

test:
	$(COVERAGE) erase
	echo $(wildcard */*_test.py) | xargs -n 1 $(COVERAGE) run -p
	echo $(wildcard *_test.py) | xargs -n 1 $(COVERAGE) run -p
	$(COVERAGE) combine
	$(COVERAGE) report -m

.PHONY: test clean install all distclean
