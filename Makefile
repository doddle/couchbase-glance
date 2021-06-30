# SHELL:=/bin/bash
.DEFAULT_GOAL:=help

export ROOTDIR:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

# activate the virtualenv
export VIRTUAL_ENV := $(ROOTDIR)/venv
export PATH        :=$(ROOTDIR)/venv/bin:$(PATH)

## Print this help
help:
	@awk -v skip=1 \
		'/^##/ { sub(/^[#[:blank:]]*/, "", $$0); doc_h=$$0; doc=""; skip=0; next } \
		 skip  { next } \
		 /^#/  { doc=doc "\n" substr($$0, 2); next } \
		 /:/   { sub(/:.*/, "", $$0); printf "\033[1m%-30s\033[0m\033[1m%s\033[0m %s\n\n", $$0, doc_h, doc; skip=1 }' \
		$(MAKEFILE_LIST)


## Install all dependencies
# Usage:
#  make deps
deps: deps-python

#/ activates virenv and installs deps
deps-python:
	@cd "$(ROOTDIR)"
	@if [ ! -d $(VIRTUAL_ENV)/bin ] ; \
	then \
		python3 -m venv "$(VIRTUAL_ENV)" ;\
	fi
	. $(VIRTUAL_ENV)/bin/activate ; \
	$(VIRTUAL_ENV)/bin/pip3 install --upgrade pip ; \
 	$(VIRTUAL_ENV)/bin/pip3 install -r $(ROOTDIR)/requirements.txt


## Run the script
# Usage:
#  make run    (don't forget to have run `make deps` beforehand)
run: 
	./main.py

#? clean up venv
clean:
	rm -rf $(VIRTUAL_ENV)

## Freeze current deps into the requirements.txt
# Usage:
#  make freeze
freeze:
	@pip freeze --path venv/lib/python3.*/site-packages > requirements.txt
