import os


def generate_report(case_name, output_dir, stages, seed=None, num_seq=None, top_module=None, rtl_dir=None):
    artifacts = []
    expected_files = [
        "design.json",
        "verification_skeleton.json",
        "constraints.json",
        "coverage_bins.json",
        "functional_coverage.json",
        "coverage_result.json",
    ]
    for f in expected_files:
        path = os.path.join(output_dir, f)
        if os.path.isfile(path):
            artifacts.append(f)

    tb_dir = os.path.join(output_dir, "generated_tb")
    if os.path.isdir(tb_dir):
        for f in os.listdir(tb_dir):
            artifacts.append(f"generated_tb/{f}")

    repro_cmd = "A2 tool generation completed. To reproduce simulation:"
    if rtl_dir and top_module:
        repro_cmd = (
            f"cd generated_tb && "
            f"iverilog -o sim.vvp -f filelist.txt && "
            f"vvp sim.vvp"
        )

    report = {
        "report": {
            "name": case_name,
            "status": "complete" if all(s["status"] == "passed" for s in stages) else "partial",
            "stages": stages,
            "artifacts": artifacts,
            "summary": f"Verification environment generated for {case_name}",
            "reproducible_command": repro_cmd,
            "coverage_summary": {
                "formula": "0.4 * line_coverage + 0.3 * branch_coverage + 0.3 * functional_coverage",
                "scoring": {
                    ">=85%": 7.0,
                    "65-85%": 4.9,
                    "45-65%": 2.8,
                    "<45%": 0,
                },
            },
        }
    }
    return report
