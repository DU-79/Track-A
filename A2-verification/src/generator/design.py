import os
import re
from utils.helpers import is_clock, is_reset
from protocol.detector import classify_interface


def _signal_info(port):
    return {
        "name": port.name,
        "direction": port.direction,
        "type": getattr(port, "port_type", "wire"),
        "width": port.width if port.width else "1",
    }


def _group_by_axi_channel(ports, prefix):
    """
    Split AXI signals into channel groups:
    s_axi_aw*, s_axi_w*, s_axi_b*, s_axi_ar*, s_axi_r*
    Returns list of {name, role, protocol_channel, signals}
    """
    channels = {"AW": [], "W": [], "B": [], "AR": [], "R": []}
    channel_labels = {
        "AW": "AXI write address",
        "W": "AXI write data",
        "B": "AXI write response",
        "AR": "AXI read address",
        "R": "AXI read data",
    }

    for p in ports:
        name = p.name.lower()
        for ch in ["aw", "w", "b", "ar", "r"]:
            pattern = f"_{ch}"
            idx = name.find(pattern)
            if idx >= 0:
                after = name[idx + len(pattern):]
                if not after or after[0] == "_" or after[0].isdigit() or after[0].isalpha():
                    channels[ch.upper()].append(p)
                    break

    result = []
    for ch, sigs in channels.items():
        if not sigs:
            continue
        inputs = [s for s in sigs if s.direction == "input"]
        outputs = [s for s in sigs if s.direction == "output"]
        if inputs:
            result.append({
                "name": f"{prefix}_{ch.lower()}",
                "role": "input_driver",
                "protocol_channel": channel_labels[ch],
                "signals": [_signal_info(s) for s in sorted(inputs, key=lambda x: x.name)],
            })
        if outputs:
            result.append({
                "name": f"{prefix}_{ch.lower()}",
                "role": "output_monitor",
                "protocol_channel": channel_labels[ch],
                "signals": [_signal_info(s) for s in sorted(outputs, key=lambda x: x.name)],
            })

    return result


def _group_non_axi(ports, prefix, proto):
    """For non-AXI interfaces, split into input_driver and output_monitor."""
    result = []
    inputs = [s for s in ports if s.direction == "input"]
    outputs = [s for s in ports if s.direction == "output"]
    if inputs:
        result.append({
            "name": prefix,
            "role": "input_driver",
            "protocol_channel": proto,
            "signals": [_signal_info(s) for s in sorted(inputs, key=lambda x: x.name)],
        })
    if outputs:
        result.append({
            "name": prefix,
            "role": "output_monitor",
            "protocol_channel": proto,
            "signals": [_signal_info(s) for s in sorted(outputs, key=lambda x: x.name)],
        })
    return result


def _detect_top_protocol(interfaces):
    """Determine the top-level protocol description."""
    protos = set()
    for iface in interfaces:
        ch = iface.get("protocol_channel", "")
        if "AXI" in ch and "Stream" not in ch:
            protos.add("AXI4")
        elif "AXI-Stream" in ch or ch == "AXI4-Stream":
            protos.add("AXI4-Stream")
        elif "SRAM" in ch:
            protos.add("SRAM-like")
    if "AXI4" in protos:
        return "AXI4" + (" memory-mapped" if len(protos) == 1 else "")
    if "AXI4-Stream" in protos:
        return "AXI4-Stream"
    if "SRAM-like" in protos:
        return "SRAM-like"
    return "custom"


def _derive_params(params):
    """Compute derived parameters (e.g., STRB_WIDTH from DATA_WIDTH/8)."""
    derived = {}
    for name, val in params.items():
        if isinstance(val, str):
            m = re.match(r"\((\w+)\s*/\s*8\)", val)
            if m:
                derived[f"{name}_computed"] = f"{m.group(1)} // 8"
            m = re.match(r"\(\((\w+)\s*\+\s*7\)\s*/\s*8\)", val)
            if m:
                derived[f"{name}_computed"] = f"({m.group(1)} + 7) // 8"
    return derived if derived else None


def _guess_function(top_module):
    """Heuristically describe what the module does."""
    name = top_module.name.lower()
    if "adapter" in name:
        return "Data-width adapter / protocol converter"
    if "fifo" in name:
        return "AXI4-Stream FIFO with width conversion"
    if "ram" in name or "sram" in name:
        return "AXI4 memory-mapped RAM"
    if "crossbar" in name:
        return "AXI crossbar / address decoder"
    if "cnn" in name or "conv" in name or "pooling" in name or "relu" in name:
        return "CNN accelerator"
    if "uart" in name:
        return "UART communication controller"
    if "spi" in name:
        return "SPI master controller"
    return "Custom hardware module"


def generate_design(top_module, all_modules, rtl_dir):
    clocks = [p for p in top_module.ports if is_clock(p.name) and p.direction == "input"]
    resets = [p for p in top_module.ports if is_reset(p.name) and p.direction == "input"]

    # Group ports by prefix
    prefix_groups = {}
    for p in top_module.ports:
        if is_clock(p.name) or is_reset(p.name):
            continue
        prefix = p.name.split("_")[0] if "_" in p.name else "general"
        prefix_groups.setdefault(prefix, []).append(p)

    # Build interfaces in official format
    interfaces = []
    for prefix, ports in prefix_groups.items():
        inputs = [p for p in ports if p.direction == "input"]
        outputs = [p for p in ports if p.direction == "output"]
        proto, _, _ = classify_interface(
            [_signal_info(p) for p in inputs],
            [_signal_info(p) for p in outputs],
        )

        if proto == "AXI4":
            interfaces.extend(_group_by_axi_channel(ports, prefix))
        else:
            interfaces.extend(_group_non_axi(ports, prefix, proto))

    # Resolve RTL paths
    rtl_files = []
    for m in all_modules:
        rtl_files.append(m.file_path)

    # Put .vh files first
    rtl_files.sort(key=lambda f: (not f.endswith(".vh"), f))

    top_proto = _detect_top_protocol(interfaces)

    params_dict = {}
    for p in top_module.params:
        params_dict[p.name] = p.value if p.value else "<unknown>"

    design = {
        "design": {
            "name": top_module.name,
            "language": "verilog-2001",
            "top_module": top_module.name,
            "rtl": rtl_files,
            "function": _guess_function(top_module),
            "protocol": top_proto,
            "clock": {
                "name": clocks[0].name if clocks else None,
                "period_ns": 10,
            } if clocks else None,
            "reset": {
                "name": resets[0].name if resets else None,
                "active_level": 0 if getattr(top_module, "reset_active", "high") == "low" else 1,
                "style": "synchronous",
                "minimum_cycles": 2,
            } if resets else None,
            "all_clocks": [_signal_info(c) for c in clocks],
            "all_resets": [_signal_info(r) for r in resets],
            "parameters": params_dict,
            "derived_parameters": _derive_params(params_dict),
            "interfaces": interfaces,
        }
    }
    return design
