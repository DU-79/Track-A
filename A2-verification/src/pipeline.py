#!/usr/bin/env python3

import argparse
import os
import sys

from parser.rtl_parser import parse_rtl_directory
from protocol.detector import detect_all_interfaces
from generator.design import generate_design
from generator.verification import generate_verification_skeleton
from generator.constraints import generate_constraints
from generator.coverage_bins import generate_coverage_bins
from generator.functional_coverage import generate_functional_coverage
from generator.coverage_result import generate_coverage_result
from generator.report import generate_report
from generator.tb_generator import generate_cocotb_top, generate_cocotb_tb
from utils.helpers import save_json, find_verilog_files, find_top_module


def main():
    parser = argparse.ArgumentParser(description="A2: Auto Verification Environment Generator")
    parser.add_argument("--rtl", required=True, help="Path to RTL directory")
    parser.add_argument("--top", default=None, help="Top module name (auto-detect if not given)")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--num-seq", type=int, default=5000, help="Number of test sequences")
    parser.add_argument("--clock-period", type=float, default=10.0, help="Clock period in ns")
    parser.add_argument("--simulator", default="cocotb", help="Target simulator")
    args = parser.parse_args()

    rtl_dir = os.path.abspath(args.rtl)
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    stages = []
    errors = []

    # Stage 1: Parse RTL
    try:
        all_modules = parse_rtl_directory(rtl_dir)
        if not all_modules:
            raise ValueError(f"No Verilog modules found in {rtl_dir}")

        # Find top module
        top_module = None
        if args.top:
            for m in all_modules:
                if m.name == args.top:
                    top_module = m
                    break
            if not top_module:
                raise ValueError(f"Top module '{args.top}' not found in RTL")
        else:
            top_module = find_top_module(all_modules)
            if not top_module:
                raise ValueError("Cannot determine top module. Use --top to specify.")

        stages.append({"stage": "rtl_parse", "status": "passed", "detail": f"Parsed {len(all_modules)} modules"})
    except Exception as e:
        stages.append({"stage": "rtl_parse", "status": "failed", "detail": str(e)})
        errors.append(f"Parse error: {e}")
        save_json(generate_report(os.path.basename(out_dir), out_dir, stages,
            seed=args.seed, num_seq=args.num_seq, top_module="unknown", rtl_dir=rtl_dir),
            os.path.join(out_dir, "report.json"))
        sys.exit(1)

    # Stage 2: Generate design.json (includes protocol detection)
    try:
        design_info = generate_design(top_module, all_modules, rtl_dir)
        save_json(design_info, os.path.join(out_dir, "design.json"))
        protocols = [f"{i['name']}({i.get('protocol_channel','')})" for i in design_info["design"]["interfaces"]]
        stages.append({"stage": "design_json", "status": "passed", "detail": f"Protocols: {protocols}"})
    except Exception as e:
        stages.append({"stage": "design_json", "status": "failed", "detail": str(e)})
        errors.append(f"design.json: {e}")

    # Stage 3: Generate verification_skeleton.json
    try:
        verif_info = generate_verification_skeleton(top_module, design_info)
        save_json(verif_info, os.path.join(out_dir, "verification_skeleton.json"))
        stages.append({"stage": "verification_skeleton_json", "status": "passed"})
    except Exception as e:
        stages.append({"stage": "verification_skeleton_json", "status": "failed", "detail": str(e)})
        errors.append(f"verification_skeleton.json: {e}")

    # Stage 5: Generate constraints.json
    try:
        constraints_info = generate_constraints(top_module, design_info, args.seed, args.num_seq)
        save_json(constraints_info, os.path.join(out_dir, "constraints.json"))
        stages.append({"stage": "constraints_json", "status": "passed"})
    except Exception as e:
        stages.append({"stage": "constraints_json", "status": "failed", "detail": str(e)})
        errors.append(f"constraints.json: {e}")

    # Stage 6: Generate coverage_bins.json
    try:
        bins_info = generate_coverage_bins(top_module, design_info)
        save_json(bins_info, os.path.join(out_dir, "coverage_bins.json"))
        stages.append({"stage": "coverage_bins_json", "status": "passed"})
    except Exception as e:
        stages.append({"stage": "coverage_bins_json", "status": "failed", "detail": str(e)})
        errors.append(f"coverage_bins.json: {e}")

    # Stage 7: Generate functional_coverage.json (initial empty)
    try:
        func_cov = generate_functional_coverage(top_module, bins_info)
        save_json(func_cov, os.path.join(out_dir, "functional_coverage.json"))
        stages.append({"stage": "functional_coverage_json", "status": "passed"})
    except Exception as e:
        stages.append({"stage": "functional_coverage_json", "status": "failed", "detail": str(e)})
        errors.append(f"functional_coverage.json: {e}")

    # Stage 8: Generate coverage_result.json (initial empty)
    try:
        cov_result = generate_coverage_result(top_module, seed=args.seed, num_seq=args.num_seq)
        save_json(cov_result, os.path.join(out_dir, "coverage_result.json"))
        stages.append({"stage": "coverage_result_json", "status": "passed"})
    except Exception as e:
        stages.append({"stage": "coverage_result_json", "status": "failed", "detail": str(e)})
        errors.append(f"coverage_result.json: {e}")

    # Stage 9: Generate testbench
    try:
        tb_dir = os.path.join(out_dir, "generated_tb")
        os.makedirs(tb_dir, exist_ok=True)

        # generated_tests directory with reproducible test description
        tests_dir = os.path.join(out_dir, "generated_tests")
        os.makedirs(tests_dir, exist_ok=True)
        params_list = ", ".join("{}={}".format(k, v) for k, v in list(design_info["design"].get("parameters", {}).items())[:5])
        test_desc = "Test for {}\nProtocol: {}\nSeed: {}\nSequences: {}\nParams: {}".format(
            top_module.name, design_info["design"].get("protocol", "?"), args.seed, args.num_seq, params_list)
        with open(os.path.join(tests_dir, "test_info.txt"), "w") as f:
            f.write(test_desc)

        # Verilog cocotb wrapper
        top_v = generate_cocotb_top(top_module, all_modules)
        top_v_path = os.path.join(tb_dir, f"{top_module.name}_cocotb_top.v")
        with open(top_v_path, "w") as f:
            f.write(top_v)

        # Python cocotb testbench (protocol-aware)
        tb_py = generate_cocotb_tb(top_module, design_info, args.seed, args.num_seq, args.clock_period)
        tb_py_path = os.path.join(tb_dir, f"{top_module.name}_tb.py")
        with open(tb_py_path, "w") as f:
            f.write(tb_py)

        # Makefile (standard cocotb, supports Icarus/VCS/Verilator)
        verilog_files = find_verilog_files(rtl_dir)
        sources_parts = []
        for vf in verilog_files:
            try:
                sources_parts.append(os.path.relpath(vf, tb_dir).replace("\\", "/"))
            except ValueError:
                sources_parts.append(vf.replace("\\", "/"))
        try:
            sources_parts.append(os.path.relpath(top_v_path, tb_dir).replace("\\", "/"))
        except ValueError:
            sources_parts.append(top_v_path.replace("\\", "/"))
        sources = " ".join(sources_parts)
        test_module = f"{top_module.name}_tb"
        makefile = f"""SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = {sources}
TOPLEVEL = {top_module.name}_cocotb_top
COCOTB_TEST_MODULES = {test_module}

ifeq ($(SIM),verilator)
EXTRA_ARGS += --coverage -Wno-WIDTHTRUNC -Wno-WIDTHEXPAND -Wno-fatal
endif

include $(shell cocotb-config --makefiles)/Makefile.sim
"""
        with open(os.path.join(tb_dir, "Makefile"), "w") as f:
            f.write(makefile)

        stages.append({"stage": "testbench_generation", "status": "passed"})
    except Exception as e:
        stages.append({"stage": "testbench_generation", "status": "failed", "detail": str(e)})
        errors.append(f"testbench: {e}")

    # Stage 10: Generate report.json
    try:
        report = generate_report(os.path.basename(out_dir), out_dir, stages,
            seed=args.seed, num_seq=args.num_seq, top_module=top_module.name, rtl_dir=rtl_dir)
        if errors:
            report["report"]["errors"] = errors
        save_json(report, os.path.join(out_dir, "report.json"))
        stages.append({"stage": "report_json", "status": "passed"})
    except Exception as e:
        print(f"Warning: Could not generate report.json: {e}")

    print(f"A2 generation complete: {out_dir}")
    if errors:
        print(f"  Warnings/Errors: {len(errors)}")
        for e in errors:
            print(f"    - {e}")


if __name__ == "__main__":
    main()
