# A3: Lightweight RTL Logic Synthesis Tool

RTL logic synthesis tool using Yosys + Berkeley ABC with configurable multi-point optimization.

## Environment

- Docker: `my_siliconcompiler_image:latest`
- Yosys 0.54, OpenSTA 2.7.0, Icarus Verilog 10.3

## Build

```bash
make build
```

Generates `bin/synth_tool`.

## Usage

```bash
make synth \
  RTL=/case/rtl/design.v \
  TOP=top \
  SDC=/case/constraints.sdc \
  LIBERTY=/pdk/NangateOpenCellLibrary_typical.lib \
  CONFIG=/submission/config.json \
  CIRCUIT=LSV01 \
  POINT=1 \
  OUT_DIR=/output
```

Output: `$(OUT_DIR)/netlist.v`

### Makefile Targets

| Target | Description |
|--------|-------------|
| `build` | Generate `bin/synth_tool` from source |
| `synth` | Synthesize one circuit point, outputs `$(OUT_DIR)/netlist.v` |
| `clean` | Remove build artifacts |

### Configuration

`config.json` defines per-circuit optimization points (1-7 points each). Unlisted circuits fall back to `$default`.
