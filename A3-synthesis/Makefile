.PHONY: build synth clean

build:
	mkdir -p bin
	cp src/synth_tool.py bin/synth_tool
	chmod +x bin/synth_tool

synth:
	python3 bin/synth_tool \
		--rtl "$(RTL)" \
		--top "$(TOP)" \
		--sdc "$(SDC)" \
		--liberty "$(LIBERTY)" \
		--config "$(CONFIG)" \
		--circuit "$(CIRCUIT)" \
		--point "$(POINT)" \
		--output "$(OUT_DIR)/netlist.v"

clean:
	rm -rf bin/
