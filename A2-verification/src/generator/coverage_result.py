def generate_coverage_result(top_module, line_pct=0.0, branch_pct=0.0, func_pct=0.0,
                              seed=0, num_seq=5000, sim_time_ns=0):
    composite = round(0.4 * line_pct + 0.3 * branch_pct + 0.3 * func_pct, 2)

    result = {
        "coverage_result": {
            "design": top_module.name,
            "status": "passed",
            "simulator": {"name": "VCS", "version": ""},
            "run": {
                "type": "cocotb",
                "test": f"{top_module.name}_tb.test_dut",
                "seed": seed,
                "sequence_count": num_seq,
                "sim_time_ns": sim_time_ns,
            },
            "coverage": {
                "line": {"covered": 0, "total": 0, "percent": round(line_pct, 2)},
                "branch": {"covered": 0, "total": 0, "percent": round(branch_pct, 2)},
                "functional": {"covered": 0, "total": 0, "percent": round(func_pct, 2)},
                "composite": {
                    "formula": "0.4 * line + 0.3 * branch + 0.3 * functional",
                    "percent": composite,
                },
            },
            "artifacts": {
                "functional_coverage": "functional_coverage.json",
            },
        }
    }
    return result
