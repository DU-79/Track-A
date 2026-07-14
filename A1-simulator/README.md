# A1: Lightweight RTL Simulator

Event-driven Verilog RTL simulator supporting Verilog-2001 core syntax subset.

## Build

```bash
make build
```

## Usage

```bash
make compile_sim FILELIST=filelist.txt TOP=tb
make run
make parallel_run THREADS=4
```

### Makefile Targets

| Target | Description |
|--------|-------------|
| `build` | Compile the simulator from source |
| `compile_sim` | Parse RTL filelist and generate simulation executable |
| `run` | Run single-threaded simulation, outputs `tb/output.mem` |
| `parallel_run` | Run multi-threaded simulation with `$(THREADS)` threads |
| `clean` | Remove build artifacts |

### Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FILELIST` | `filelist.txt` | Path to Verilog source file list |
| `TOP` | `tb` | Top-level testbench module |
| `THREADS` | `4` | Number of parallel simulation threads |
| `SIM_EXE` | `sim.out` | Simulation executable name |
