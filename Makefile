
TAG = $(shell git name-rev --tags --name-only $(shell git rev-parse HEAD))
VERSION = $(shell echo $(TAG) | grep -o 'v[0-9\.]*' \
            | sed -E 's/^v([0-9\.]+)/-N \1-1/')
BRANCH = $(shell git rev-parse --abbrev-ref HEAD)
TREE = $(shell test $(TAG) = undefined && echo $(BRANCH) || echo $(TAG))
COVERAGE ?= 'python3-coverage'

all: test

install:
	make -C $(CURDIR)/mibresolver $@
	make -C $(CURDIR)/snmpexporter $@
	mkdir -p $(DESTDIR)/etc/default $(DESTDIR)/etc/init.d
	install -D -m600 etc/snmpexporter.yaml $(DESTDIR)/etc/

clean:
	rm -f .coverage
	make -C $(CURDIR)/mibresolver $@
	make -C $(CURDIR)/snmpexporter $@

distclean: clean

test:
	$(COVERAGE) erase
	PYTHONPATH=$(CURDIR) echo $(wildcard */*_test.py) | \
	  xargs -n 1 $(COVERAGE) run -p
	echo $(wildcard *_test.py) | xargs -n 1 $(COVERAGE) run -p
	$(COVERAGE) combine
	$(COVERAGE) report -m

deb:
	echo Using $(TREE)
	git checkout $(TREE)
	cp debian/changelog debian/changelog.old
	rm -f ../snmpexporter_*.orig.tar.gz
	gbp dch --snapshot --auto --ignore-branch $(VERSION)
	gbp buildpackage --git-upstream-tree=$(TREE) --git-submodules \
		--git-ignore-new --git-ignore-branch --git-builder='debuild -i -I -us -uc'
	mv debian/changelog.old debian/changelog

.PHONY: deb test clean install all distclean
