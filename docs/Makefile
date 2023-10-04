BIN ?= asciidoctor
MAN_OPTS ?= --backend manpage
REVNUMBER := $(shell python3 -c "import tomli; content = tomli.load(open('../pyproject.toml', 'rb')); print(content['project']['version'])")
all: man

man: man/firehpc.1 man/fhpc-emulate-slurm-usage.1

man/%.1: man/%.adoc
	$(BIN) $(MAN_OPTS) --attribute mansource="FireHPC v$(REVNUMBER)" $<
