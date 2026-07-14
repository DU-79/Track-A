from protocol.protocols import get_coverpoints


def generate_coverage_bins(top_module, design_info):
    interfaces = design_info["design"].get("interfaces", [])
    proto = design_info["design"].get("protocol", "custom")

    # Determine conditions
    has_axi = any("AXI" in iface.get("protocol_channel", "") for iface in interfaces)
    has_axis = any("Stream" in iface.get("protocol_channel", "") for iface in interfaces)
    has_sram = any("SRAM" in iface.get("protocol_channel", "") for iface in interfaces)
    has_hs = any("handshake" in iface.get("protocol_channel", "").lower() for iface in interfaces)

    # Map interface detection to protocol name (fallback chain)
    if has_axi and "Stream" not in proto:
        proto_name = "AXI4"
    elif has_axis:
        proto_name = "AXI4-Stream"
    elif has_sram:
        proto_name = "SRAM-like"
    elif has_hs:
        proto_name = "handshake"
    else:
        proto_name = "custom"

    conditions = {
        "has_write": any(iface.get("role") == "input_driver" and "write" in iface.get("protocol_channel", "").lower() for iface in interfaces),
        "has_read": any(iface.get("role") == "input_driver" and "read" in iface.get("protocol_channel", "").lower() for iface in interfaces),
    }

    cp = get_coverpoints(proto_name, **conditions)

    bins = []
    for name, values in cp.items():
        bins.append({
            "name": name,
            "description": "Coverpoint for " + name,
            "values": [{"name": v, "scenario": "Exercise " + name + ":" + v} for v in values],
        })

    result = {
        "coverage_bins": {
            "name": f"{top_module.name}_functional_bins",
            "design": top_module.name,
            "description": "Functional coverage bins with protocol scenarios and corner cases",
            "bins": bins,
            "uncovered_feedback": [],
        }
    }
    return result
