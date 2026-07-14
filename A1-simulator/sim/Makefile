FILELIST ?= filelist.txt
TOP ?= tb
THREADS ?= 4
SIM_EXE ?= sim.out

SUBMISSION_DIR ?= $(abspath $(dir $(firstword $(MAKEFILE_LIST))))
SRC_DIR ?= $(SUBMISSION_DIR)/src

SIMULATOR ?= $(SUBMISSION_DIR)/simulator

CXX ?= g++
CXXFLAGS ?= -std=c++11 -O2 -Wall -I$(SRC_DIR)
LDFLAGS ?= -lm

.PHONY: build compile_sim run parallel_run clean

build:
	$(CXX) $(CXXFLAGS) \
		$(SRC_DIR)/Lexer.cpp \
		$(SRC_DIR)/Parser.cpp \
		$(SRC_DIR)/Compiler.cpp \
		$(SRC_DIR)/CodeGen.cpp \
		$(SRC_DIR)/main.cpp \
		-o $(SIMULATOR) $(LDFLAGS)

compile_sim: build
	$(SIMULATOR) --compile -f "$(FILELIST)" --top "$(TOP)" -o "$(abspath $(SIM_EXE))"

run:
	@rm -f tb/output.mem
	"$(abspath $(SIM_EXE))"

parallel_run:
	$(MAKE) run

clean:
	rm -f $(SIMULATOR) $(SIM_EXE) $(SIM_EXE).cpp tb/output.mem
