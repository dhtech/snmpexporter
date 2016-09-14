install:
	python setup.py install --root $(DESTDIR) $(COMPILE)
	mkdir -p $(DESTDIR)/usr/share/snmpcollector/
	cp src/*.py $(DESTDIR)/usr/share/snmpcollector/
	rm -f $(DESTDIR)/usr/share/snmpcollector/*_test.py
