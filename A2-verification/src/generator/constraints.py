def _feedback_notes(top_module, design_info):
    """Generate parameter-aware coverage feedback notes."""
    params = design_info["design"].get("parameters", {})
    notes = []
    for k, v in params.items():
        if v in ("0", "0.0", "false", "False"):
            notes.append(f"Parameter {k}={v} may gate off related logic branches. If coverage is low for this circuit, check whether {k} enables additional functionality.")
    if not notes:
        notes.append("No zero-valued parameters detected. All declared bins should be reachable with sufficient stimulus diversity.")
    return {"timestamp": "auto-generated", "notes": notes}


def generate_constraints(top_module, design_info, seed, num_seq):
    interfaces = design_info["design"].get("interfaces", [])
    variables = {}
    hard_constraints = ["all transactions must respect protocol handshaking"]
    coverage_guidance = ["include edge cases and boundary values for all variables"]

    has_axi = any("AXI" in iface.get("protocol_channel", "") for iface in interfaces)
    has_axis = any("Stream" in iface.get("protocol_channel", "") for iface in interfaces)
    has_sram = any("SRAM" in iface.get("protocol_channel", "") for iface in interfaces)

    if has_axi:
        variables.update({
            "transaction_type": {"type": "enum", "values": ["read", "write", "read_after_write"]},
            "address": {"type": "integer", "range": [0, 65535]},
            "burst_length": {"type": "integer", "range": [1, 256]},
            "transfer_size": {"type": "enum", "values": [1, 2, 4]},
            "address_alignment": {"type": "enum", "values": ["aligned", "unaligned", "4k_boundary"]},
            "backpressure_mode": {"type": "enum", "values": ["none", "addr_ready_pause", "data_ready_pause", "random"]},
            "data_seed": {"type": "integer", "value": seed},
        })
        hard_constraints.extend([
            "address + burst_length <= 65536 (no 64K crossing)",
            "burst_length must respect 4K boundary",
            "transfer_size must be <= data bus width",
        ])
        coverage_guidance.extend([
            "include addresses near 0, 4K boundary, and 64K boundary",
            "include all burst lengths from 1 to 256",
            "exercise all backpressure modes",
        ])

    if has_axis:
        variables.update({
            "frame_length": {"type": "integer", "range": [1, 256]},
            "payload_pattern": {"type": "enum", "values": ["increment", "constant", "random"]},
            "source_valid_pattern": {"type": "enum", "values": ["always", "random_gap", "burst"]},
            "sink_ready_pattern": {"type": "enum", "values": ["always", "random_gap", "burst"]},
            "tlast_position": {"type": "integer", "range": [1, 256]},
        })
        hard_constraints.extend([
            "frame_length bytes must match tlast position",
            "tkeep must reflect valid bytes on last beat",
        ])
        coverage_guidance.extend([
            "include frame lengths that are multiples of beat width and non-multiples",
            "exercise sink backpressure on at least 20% of transactions",
        ])

    if has_sram:
        variables.update({
            "operation": {"type": "enum", "values": ["write", "read", "read_after_write"]},
            "address": {"type": "integer", "range": [0, 65535]},
            "write_data": {"type": "integer", "range": [0, 2**32 - 1]},
            "address_pattern": {"type": "enum", "values": ["sequential", "random", "reverse", "fixed"]},
            "data_pattern": {"type": "enum", "values": ["zero", "ones", "walking_one", "increment", "random"]},
        })

    if not (has_axi or has_axis or has_sram):
        variables.update({
            "input_values": {"type": "integer", "range": [0, 2**16 - 1], "description": "Random input stimulus"},
            "toggle_rate": {"type": "enum", "values": ["slow", "medium", "fast"], "description": "Input change frequency"},
        })
        coverage_guidance.append("exercise all input signals across full range")

    constraints = {
        "constraint_random_test": {
            "name": f"{top_module.name}_constraints",
            "design": top_module.name,
            "seed": seed,
            "sequence_count": num_seq,
            "reproducible": True,
            "transaction_variables": variables,
            "hard_constraints": hard_constraints,
            "coverage_guidance": coverage_guidance,
            "coverage_feedback_log": [_feedback_notes(top_module, design_info)],
            "objective": {
                "primary": f"achieve >=85% composite coverage on {top_module.name}",
                "secondary": "exercise all protocol states and corner cases",
                "reported_metric": [
                    "line_coverage_percent",
                    "branch_coverage_percent",
                    "functional_coverage_percent",
                    "composite_coverage_percent",
                ],
            },
        }
    }
    return constraints
