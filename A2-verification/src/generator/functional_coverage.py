def generate_functional_coverage(top_module, coverage_bins):
    bin_list = coverage_bins["coverage_bins"]["bins"]

    coverpoints = []
    total_bins = 0
    for bin_def in bin_list:
        bin_entries = [
            {"name": v, "hits": 0, "covered": False}
            for v in bin_def["values"]
        ]
        coverpoints.append({
            "name": bin_def["name"],
            "covered_bins": 0,
            "total_bins": len(bin_entries),
            "bins": bin_entries,
        })
        total_bins += len(bin_entries)

    result = {
        "functional_coverage": {
            "design": top_module.name,
            "status": "pending",
            "source": "testbench simulation sampling",
            "covered_bins": 0,
            "total_bins": total_bins,
            "percent": 0.0,
            "coverpoints": coverpoints,
        }
    }
    return result
