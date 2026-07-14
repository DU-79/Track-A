"""
Protocol detector - logic-based, not name-based.
Detects AXI4, AXI4-Stream, SRAM-like, handshake patterns.
Marks anything unrecognized as 'custom'.
"""
import re


def _has_valid_ready(signals):
    names = [s["name"].lower() for s in signals]
    return any("valid" in n for n in names) and any("ready" in n for n in names)


def _has_signal_containing(signals, *keywords):
    names = [s["name"].lower() for s in signals]
    return any(any(kw in n for kw in keywords) for n in names)


def _segment_match(name, prefixes, suffixes):
    """Check if any underscore-separated segment matches prefix+suffix.
    E.g., 's_axi_awvalid' with prefix='aw', suffix='valid' -> True."""
    for seg in name.lower().split("_"):
        for pf in prefixes:
            if seg.startswith(pf) and seg != pf:
                tail = seg[len(pf):]
                if tail in suffixes:
                    return True
                for sf in suffixes:
                    if sf in tail:
                        return True
    return False


def _detect_axi4(inputs, outputs):
    """Score-based AXI4 detection on a group of signals."""
    all_signals = inputs + outputs
    all_names = [s["name"] for s in all_signals]
    score = 0
    details = {"channels": []}

    # AW channel: _aw + (addr|valid|ready|id|len|size|burst|lock|cache|prot|qos|region|user)
    aw_suffixes = ["addr", "valid", "ready", "id", "len", "size", "burst", "lock",
                   "cache", "prot", "qos", "region", "user"]
    aw_signals = [s for s in all_signals if _segment_match(s["name"], ["aw"], aw_suffixes)]
    if len(aw_signals) >= 3 and _has_valid_ready(aw_signals):
        score += 2
        details["channels"].append("AW")

    # W channel: _w + (data|strb|last|valid|ready)
    w_suffixes = ["data", "strb", "last", "valid", "ready"]
    w_signals = [s for s in all_signals if _segment_match(s["name"], ["w"], w_suffixes)]
    if _has_valid_ready(w_signals) and _has_signal_containing(w_signals, "wdata"):
        score += 2
        details["channels"].append("W")

    # B channel: _b + (resp|id|valid|ready)
    b_suffixes = ["resp", "id", "valid", "ready"]
    b_signals = [s for s in all_signals if _segment_match(s["name"], ["b"], b_suffixes)]
    if _has_valid_ready(b_signals):
        score += 1
        details["channels"].append("B")

    # AR channel: _ar + (addr|valid|ready|id|len|size|burst|lock|cache|prot|qos|region|user)
    ar_suffixes = ["addr", "valid", "ready", "id", "len", "size", "burst", "lock",
                   "cache", "prot", "qos", "region", "user"]
    ar_signals = [s for s in all_signals if _segment_match(s["name"], ["ar"], ar_suffixes)]
    if len(ar_signals) >= 3 and _has_valid_ready(ar_signals):
        score += 2
        details["channels"].append("AR")

    # R channel: _r + (data|resp|last|id|user|valid|ready)
    r_suffixes = ["data", "resp", "last", "id", "user", "valid", "ready"]
    r_signals = [s for s in all_signals if _segment_match(s["name"], ["r"], r_suffixes)]
    if _has_valid_ready(r_signals) and _has_signal_containing(r_signals, "rdata"):
        score += 2
        details["channels"].append("R")

    output_names = [s["name"].lower() for s in outputs]
    input_names = [s["name"].lower() for s in inputs]
    is_master = any(
        "awaddr" in n or "araddr" in n for n in output_names
    )
    is_slave = any(
        "awaddr" in n or "araddr" in n for n in input_names
    )
    details["role"] = "master" if is_master else ("slave" if is_slave else "unknown")

    return score, details


def _detect_axis(inputs, outputs):
    """Detect AXI4-Stream: requires tvalid+tready+tdata as minimum."""
    all_signals = inputs + outputs
    stream_suffixes = ["data", "keep", "strb", "last", "id", "dest", "user", "valid", "ready"]
    stream_signals = [s for s in all_signals if _segment_match(s["name"], ["t"], stream_suffixes)]

    if not stream_signals:
        return 0, {}

    has_tvalid = _has_signal_containing(stream_signals, "tvalid")
    has_tready = _has_signal_containing(stream_signals, "tready")
    has_tdata = _has_signal_containing(stream_signals, "tdata")

    if not (has_tvalid and has_tready and has_tdata):
        return 0, {}

    score = 5
    for bonus in ["tlast", "tkeep", "tstrb", "tid", "tdest", "tuser"]:
        if _has_signal_containing(stream_signals, bonus):
            score += 1

    return score, {"signal_count": len(stream_signals)}


def _detect_sram(inputs, outputs):
    """Detect SRAM-like: needs address bus + data bus + control signals."""
    all_signals = inputs + outputs
    names = [s["name"].lower() for s in all_signals]

    has_addr = any(
        re.search(r"\baddr\b", n) or n.endswith("_addr") or n.endswith("_a")
        for n in names
    )
    has_data_in = any(
        re.search(r"\b(data_in|wdata|wr_data|din|d_i)\b", n) for n in names
    )
    has_data_out = any(
        re.search(r"\b(data_out|rdata|rd_data|dout|d_o|q)\b", n) for n in names
    )
    has_wen = any(
        re.search(r"\b(wen|wr_en|we|write_en|wren|w_en)\b", n) for n in names
    )
    has_ren = any(
        re.search(r"\b(ren|rd_en|re|read_en|rden|r_en)\b", n) for n in names
    )
    has_cs = any(
        re.search(r"\b(cs|ce|chip_sel|chip_en)\b", n) for n in names
    )

    score = 0
    if has_addr:
        score += 2
    if has_data_in or has_data_out:
        score += 2
    if has_wen:
        score += 2
    if has_ren:
        score += 1
    if has_cs:
        score += 1

    details = {"features": []}
    for feat, flag in [("address", has_addr), ("write_enable", has_wen),
                       ("read_enable", has_ren), ("chip_select", has_cs)]:
        if flag:
            details["features"].append(feat)

    return score, details


def _detect_handshake(inputs, outputs):
    """Detect generic valid/ready or req/ack handshake (not full protocol)."""
    all_signals = inputs + outputs
    names = [s["name"].lower() for s in all_signals]

    has_valid = any("valid" in n for n in names)
    has_ready = any("ready" in n for n in names)
    has_req = any(re.search(r"\b(req|request)\b", n) for n in names)
    has_ack = any(re.search(r"\b(ack|acknowledge)\b", n) for n in names)
    has_done = any(re.search(r"\b(done|complete|finish)\b", n) for n in names)

    score = 0
    if has_valid and has_ready:
        score += 3
    if has_req and has_ack:
        score += 3
    if has_done:
        score += 1

    return score, {"type": "handshake"}


def classify_interface(inputs, outputs):
    """
    Classify a group of signals into a protocol type.

    Returns: (protocol_name, confidence, details)
    protocol_name: 'AXI4' | 'AXI4-Stream' | 'SRAM-like' | 'handshake' | 'custom'
    """
    if not inputs and not outputs:
        return "custom", 0, {"reason": "empty"}

    candidates = []

    axi_score, axi_details = _detect_axi4(inputs, outputs)
    if axi_score >= 3:
        candidates.append(("AXI4", axi_score, axi_details))

    axis_score, axis_details = _detect_axis(inputs, outputs)
    if axis_score >= 5:
        candidates.append(("AXI4-Stream", axis_score, axis_details))

    sram_score, sram_details = _detect_sram(inputs, outputs)
    if sram_score >= 3:
        candidates.append(("SRAM-like", sram_score, sram_details))

    hshake_score, hshake_details = _detect_handshake(inputs, outputs)
    if hshake_score >= 2:
        candidates.append(("handshake", hshake_score, hshake_details))

    if not candidates:
        return "custom", 0, {"reason": "no known protocol pattern"}

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0], candidates[0][1], candidates[0][2]


def detect_all_interfaces(interfaces_dict):
    """
    Analyze all interface groups and assign protocol labels.
    Returns enriched dict with protocol info per group.
    """
    result = {}
    for prefix, iface in interfaces_dict.items():
        inputs = iface.get("inputs", [])
        outputs = iface.get("outputs", [])
        proto, conf, details = classify_interface(inputs, outputs)
        result[prefix] = {
            "protocol": proto,
            "inputs": inputs,
            "outputs": outputs,
        }
    return result
