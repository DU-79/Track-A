#!/usr/bin/env python3
"""
A3 Lightweight RTL Logic Synthesis Tool
Wraps Yosys + Berkeley ABC with configurable multi-point optimization.
"""
import os, sys, json, argparse, subprocess, time

ABC_FALLBACK = "strash; balance; rewrite; refactor; map"

def load_point(config_path, circuit, point_idx):
    """Load ABC sequence for (circuit, point) from config.json."""
    with open(config_path) as f:
        cfg = json.load(f)
    points = cfg.get(circuit) or cfg.get("$default", [])
    if not points or point_idx > len(points):
        print(f"[synth] ERROR: point {point_idx} out of range for {circuit}", file=sys.stderr)
        sys.exit(1)
    pt = points[point_idx - 1]
    seq = pt.get("abc_sequence", ABC_FALLBACK) if isinstance(pt, dict) else ABC_FALLBACK
    return seq

def write_abc_script(path, abc_seq):
    """Write ABC command script, one command per line."""
    cmds = [c.strip() for c in abc_seq.split(";") if c.strip()]
    if not any("map" in c for c in cmds):
        cmds.append("map")
    with open(path, "w") as f:
        f.write("\n".join(cmds) + "\n")
    return cmds

def run_yosys(rtl, top, sdc, liberty, out_dir, abc_script):
    """Execute Yosys synthesis flow."""
    netlist = os.path.join(out_dir, "netlist.v")
    ys = os.path.join(out_dir, "run_synth.ys")
    
    cmds = [
        f"read_verilog -sv {rtl}",
        f"hierarchy -check -top {top}",
        "proc",
        f"read_sdc {sdc}",
        f"synth -top {top}",
        f"dfflibmap -liberty {liberty}",
        f"abc -liberty {liberty} -script {abc_script}",
        "clean",
        f"write_verilog -noattr {netlist}",
    ]
    with open(ys, "w") as f:
        f.write("\n".join(cmds) + "\n")

    env = os.environ.copy()
    env["OPENMP_NUM_THREADS"] = "1"
    env["OMP_NUM_THREADS"] = "1"

    t0 = time.time()
    res = subprocess.run(["yosys", "-s", ys], env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    elapsed = time.time() - t0
    
    if res.returncode != 0 or not os.path.exists(netlist):
        print(f"[synth] FAILED after {elapsed:.1f}s", file=sys.stderr)
        return None
    print(f"[synth] OK {elapsed:.1f}s → {netlist}")
    return netlist

def main():
    parser = argparse.ArgumentParser(description="A3 Synthesis Tool")
    parser.add_argument("--rtl", required=True)
    parser.add_argument("--top", required=True)
    parser.add_argument("--sdc", required=True)
    parser.add_argument("--liberty", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--circuit", required=True)
    parser.add_argument("--point", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    out_dir = os.path.dirname(args.output) or "."

    # Primary strategy
    abc_seq = load_point(args.config, args.circuit, args.point)
    print(f"[synth] {args.circuit} p{args.point}: {abc_seq}")
    
    abc_script = os.path.join(out_dir, "abc.script")
    write_abc_script(abc_script, abc_seq)
    
    result = run_yosys(args.rtl, args.top, args.sdc, args.liberty, out_dir, abc_script)
    
    # If primary strategy fails, try fallback
    if result is None and abc_seq != ABC_FALLBACK:
        print(f"[synth] Retry with fallback: {ABC_FALLBACK}")
        write_abc_script(abc_script, ABC_FALLBACK)
        result = run_yosys(args.rtl, args.top, args.sdc, args.liberty, out_dir, abc_script)
    
    if result is None:
        sys.exit(1)

    # Ensure output is at the requested path
    src = os.path.normpath(result) if result else ""
    dst = os.path.normpath(args.output)
    if src and src != dst:
        import shutil
        shutil.copy(result, args.output)
    
    sys.exit(0)

if __name__ == "__main__":
    main()
