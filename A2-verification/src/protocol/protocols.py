"""
Unified protocol behavior definitions.
A single source of truth for: signal detection, coverage bins, and testbench generation.
"""

PROTOCOLS = {
    "AXI4": {
        "signal_patterns": ["aw", "w", "b", "ar", "r"],
        "coverpoints": {
            "reset_behavior": ["post_reset"],
            "address_alignment": ["aligned", "unaligned", "near_4k_boundary"],
            "transfer_size": ["1_byte", "2_byte", "4_byte"],
            "burst_length": ["1", "2_to_3", "4_to_7", "8_to_15"],
            "backpressure": ["exercised"],
        },
        "conditional_coverpoints": {
            "operation_type": {
                "requires": "has_write_and_read",
                "bins": ["write", "read", "write_then_read"],
            },
        },
    },

    "AXI4-Stream": {
        "signal_patterns": ["t"],
        "coverpoints": {
            "reset_behavior": ["post_reset"],
            "source_handshake": ["transfer", "backpressure", "idle"],
            "sink_handshake": ["transfer"],
            "frame_boundary": ["single_beat", "multi_beat"],
            "backpressure": ["exercised"],
        },
    },

    "SRAM-like": {
        "signal_patterns": ["addr", "wen", "ren", "data"],
        "coverpoints": {
            "reset_behavior": ["post_reset"],
            "operation_type": ["write", "read", "read_after_write"],
            "backpressure": ["exercised"],
        },
    },

    "handshake": {
        "signal_patterns": ["valid", "ready"],
        "coverpoints": {
            "reset_behavior": ["post_reset"],
            "handshake_send": ["transfer", "backpressure", "idle"],
            "handshake_recv": ["transfer"],
            "backpressure": ["exercised"],
        },
    },

    "custom": {
        "base_coverpoints": {
            "reset_behavior": ["post_reset"],
            "input_toggled": ["yes"],
            "output_observed": ["yes"],
        },
    },
}


def get_coverpoints(proto_name, **conditions):
    """Get coverpoint dict for a protocol, handling conditional bins.

    conditions: has_write, has_read, input_count, output_count
    """
    proto = PROTOCOLS.get(proto_name, PROTOCOLS["custom"])

    # Base coverpoints
    cp = dict(proto.get("coverpoints", {}))

    # Custom protocol uses base_coverpoints
    if "base_coverpoints" in proto:
        cp = dict(proto["base_coverpoints"])

    # Handle conditional coverpoints
    for name, cfg in proto.get("conditional_coverpoints", {}).items():
        required = cfg.get("requires", "")
        if required == "has_write_and_read":
            if conditions.get("has_write") and conditions.get("has_read"):
                cp[name] = cfg["bins"]
        elif required == "has_write_only":
            if conditions.get("has_write"):
                cp[name] = cfg["bins"]
        elif required == "has_read_only":
            if conditions.get("has_read"):
                cp[name] = cfg["bins"]
        else:
            cp[name] = cfg["bins"]

    return cp
