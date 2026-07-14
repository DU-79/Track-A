# A2: Verification Environment Auto-Generator

Automatically generates a verification environment from RTL design files.

## Requirements

```bash
pip install -r requirements.txt
```

## Usage

```bash
python3 configure.py --rtl <rtl_dir> --top <module> --out <output_dir> --seed 42 --num-seq 5000
```

### Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--rtl` | Path to RTL source directory | required |
| `--top` | Top module name (auto-detect if omitted) | auto |
| `--out` | Output directory | required |
| `--seed` | Random seed for reproducibility | 42 |
| `--num-seq` | Number of test sequences | 5000 |
| `--clock-period` | Clock period in ns | 10.0 |

### Example

```bash
python3 configure.py --rtl testcases/case1/rtl --top dut --out output/case1 --seed 42 --num-seq 5000
```

## Output Structure

```
<out>/
├── design.json
├── verification_skeleton.json
├── constraints.json
├── coverage_bins.json
├── functional_coverage.json
├── coverage_result.json
├── report.json
└── generated/
    └── tb/
        ├── tb_top.sv
        ├── generated_driver.sv
        └── generated_monitor.sv
```
