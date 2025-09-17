BIN ?= asciidoctor
MAN_OPTS ?= --backend manpage
REVNUMBER := $(shell python3 -c "import tomllib; content = tomllib.load(open('../pyproject.toml', 'rb')); print(content['project']['version'])")
all: man

man: man/firehpc.1

man/%.1: man/%.adoc
	$(BIN) $(MAN_OPTS) --attribute mansource="FireHPC v$(REVNUMBER)" $<
