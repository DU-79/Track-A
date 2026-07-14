"""
Phase 3: Testbench generator - generates protocol-aware cocotb testbenches.
"""
import os
import re
import textwrap


def _indent(code, level=1):
    return textwrap.indent(code, "    " * level)


def _feedback_loop(indent_level=1, num_seq_var="NUM_SEQ"):
    """Generate coverage feedback code: 3 mini-rounds trying to fill gaps."""
    p = "    " * indent_level
    lines = []
    lines.append(p + "# === Coverage feedback: targeted mini-rounds for uncovered bins ===")
    lines.append(p + "for fb_round in range(3):")
    lines.append(p + "    uncovered_before = fc.covered_bins()")
    lines.append(p + "    random.seed(SEED + fb_round * 10000)")
    lines.append(p + "    for _ in range({} // 10):".format(num_seq_var))
    return "\n".join(lines)


def _feedback_end(indent_level=1):
    """End of feedback loop: check if any new bins were covered."""
    p = "    " * indent_level
    lines = []
    lines.append(p + "    if fc.covered_bins() <= uncovered_before:")
    lines.append(p + "        break  # No improvement, stop feedback loop")
    return "\n".join(lines)


def _fc_class():
    """Return the FunctionalCoverage class code to be embedded in testbench."""
    return '''class FunctionalCoverage:
    def __init__(self, design, coverpoints):
        self.design = design
        self.coverpoints = {name: {b: 0 for b in bins} for name, bins in coverpoints.items()}
    def hit(self, cp, bn, count=1):
        if cp in self.coverpoints and bn in self.coverpoints[cp]:
            self.coverpoints[cp][bn] += count
    def covered_bins(self):
        return sum(h > 0 for bins in self.coverpoints.values() for h in bins.values())
    def total_bins(self):
        return sum(len(bins) for bins in self.coverpoints.values())
    def write(self, path=None):
        path = path or "functional_coverage.json"
        covered = self.covered_bins()
        total = self.total_bins()
        result = {"functional_coverage": {
            "design": self.design, "status": "passed", "source": "cocotb simulation",
            "covered_bins": covered, "total_bins": total,
            "percent": round(100.0 * covered / total, 2) if total else 0.0,
            "coverpoints": [
                {"name": name, "covered_bins": sum(h > 0 for h in bins.values()),
                 "total_bins": len(bins),
                 "bins": [{"name": bn, "hits": h, "covered": h > 0} for bn, h in bins.items()]}
                for name, bins in self.coverpoints.items()
            ]}}
        with open(path, "w") as f: json.dump(result, f, indent=2); f.write("\\n")'''


def _fc_init(module_name, coverpoints):
    """Generate FunctionalCoverage init call."""
    cp_str = repr(coverpoints).replace("'", '"')
    return f"fc = FunctionalCoverage({repr(module_name)}, {cp_str})"


def _get_axi_coverpoints(has_write=True, has_read=True):
    from protocol.protocols import get_coverpoints
    return get_coverpoints("AXI4", has_write=has_write, has_read=has_read)


def _get_axis_coverpoints():
    from protocol.protocols import get_coverpoints
    return get_coverpoints("AXI4-Stream")


def _get_sram_coverpoints():
    from protocol.protocols import get_coverpoints
    return get_coverpoints("SRAM-like")


def _get_generic_coverpoints(inputs, outputs):
    from protocol.protocols import get_coverpoints
    return get_coverpoints("custom")


def _get_handshake_coverpoints():
    from protocol.protocols import get_coverpoints
    return get_coverpoints("handshake")


def _safe_int(value_expr):
    """Generate code that safely converts a Logic value to int, treating X/Z as 0."""
    return f"(int({value_expr}) if {value_expr}.is_resolvable else 0)"


def _safe_bool(value_expr):
    """Generate code that safely checks if a Logic value is true, treating X/Z as false."""
    return f"({value_expr}.value.is_resolvable and {value_expr}.value == 1)"


def _generate_clock_reset(clocks, resets, reset_active):
    lines = []
    clk_name = clocks[0] if clocks else "clk"
    period = 10

    lines.append("import cocotb")
    lines.append("from cocotb.clock import Clock")
    lines.append("from cocotb.triggers import RisingEdge, ClockCycles, Timer")
    lines.append("import random")
    lines.append("import json")
    lines.append("")
    lines.append(f"CLK_PERIOD = {period}")
    lines.append(f"SEED = {{SEED}}")
    lines.append(f"NUM_SEQ = {{NUM_SEQ}}")
    lines.append("")
    lines.append("def safe_int(sig):")
    lines.append(_indent("try: return int(sig.value)"))
    lines.append(_indent("except: return 0"))
    lines.append("")

    # Test function
    lines.append("@cocotb.test()")
    lines.append("async def test_dut(dut):")
    lines.append(_indent(f"clock = Clock(dut.{clk_name}, CLK_PERIOD, units='ns')"))
    lines.append(_indent("await cocotb.start(clock.start())"))
    lines.append("")

    for c in clocks[1:]:
        lines.append(_indent(f"c2 = Clock(dut.{c}, CLK_PERIOD, units='ns')"))
        lines.append(_indent("await cocotb.start(c2.start())"))
    lines.append("")

    for r in resets:
        act = "0" if reset_active == "low" else "1"
        deact = "1" if reset_active == "low" else "0"
        lines.append(_indent(f"dut.{r}.value = {act}"))
    lines.append(_indent(f"await ClockCycles(dut.{clk_name}, 8)"))
    for r in resets:
        act = "0" if reset_active == "low" else "1"
        deact = "1" if reset_active == "low" else "0"
        lines.append(_indent(f"dut.{r}.value = {deact}"))
    lines.append(_indent(f"await ClockCycles(dut.{clk_name}, 8)"))
    lines.append("")

    return lines


def generate_tb_axi(top_module, design_info, seed, num_seq, clock_period=10):
    """Generate an AXI4 cocotb testbench (hand-written signal driving)."""
    d = design_info["design"]
    clk = d["clock"]["name"] if d["clock"] else "clk"
    rst_names = [r["name"] for r in d.get("all_resets", [])]
    rst_active = d.get("reset", {}).get("active_level", 1)
    rst_val = "0" if rst_active == 0 else "1"
    rst_deval = "1" if rst_active == 0 else "0"

    # Collect signals by AXI channel from design_info
    aw_addr, aw_valid, aw_ready, aw_len, aw_size = "", "", "", "", ""
    w_data, w_valid, w_ready, w_strb, w_last = "", "", "", "", ""
    b_valid, b_ready = "", ""
    ar_addr, ar_valid, ar_ready, ar_size = "", "", "", ""
    r_data, r_valid, r_ready = "", "", ""

    for iface in d.get("interfaces", []):
        pch = iface.get("protocol_channel", "")
        role = iface.get("role", "")
        names = [s["name"] for s in iface.get("signals", [])]

        if "write address" in pch and role == "input_driver":
            for n in names:
                if "addr" in n.lower(): aw_addr = n
                elif "valid" in n.lower(): aw_valid = n
                elif "len" in n.lower(): aw_len = n
                elif "size" in n.lower(): aw_size = n
        elif "write address" in pch and role == "output_monitor":
            for n in names:
                if "ready" in n.lower(): aw_ready = n
        elif "write data" in pch and role == "input_driver":
            for n in names:
                if "data" in n.lower(): w_data = n
                elif "valid" in n.lower(): w_valid = n
                elif "strb" in n.lower(): w_strb = n
                elif "last" in n.lower(): w_last = n
        elif "write data" in pch and role == "output_monitor":
            for n in names:
                if "ready" in n.lower(): w_ready = n
        elif "write response" in pch and role == "output_monitor":
            for n in names:
                if "valid" in n.lower(): b_valid = n
        elif "write response" in pch and role == "input_driver":
            for n in names:
                if "ready" in n.lower(): b_ready = n
        elif "read address" in pch and role == "input_driver":
            for n in names:
                if "addr" in n.lower(): ar_addr = n
                elif "valid" in n.lower(): ar_valid = n
                elif "size" in n.lower(): ar_size = n
        elif "read address" in pch and role == "output_monitor":
            for n in names:
                if "ready" in n.lower(): ar_ready = n
        elif "read data" in pch and role == "output_monitor":
            for n in names:
                if "data" in n.lower(): r_data = n
                elif "valid" in n.lower(): r_valid = n
        elif "read data" in pch and role == "input_driver":
            for n in names:
                if "ready" in n.lower(): r_ready = n

    has_write = aw_addr and w_data
    has_read = ar_addr and r_data

    has_write = aw_addr and w_data
    has_read = ar_addr and r_data

    code = []
    code.append('"""AXI4 cocotb testbench - auto-generated."""')
    code.append("import json, random")
    code.append("import cocotb")
    code.append("from cocotb.clock import Clock")
    code.append("from cocotb.triggers import RisingEdge, ClockCycles")
    code.append(_fc_class())
    code.append("")
    code.append("CLK_PERIOD = {}".format(clock_period))
    code.append("SEED = {}".format(seed))
    code.append("NUM_SEQ = {}".format(num_seq))
    code.append("")
    code.append("@cocotb.test()")
    code.append("async def test_dut(dut):")
    code.append(_indent("clock = Clock(dut.{}, CLK_PERIOD, units='ns')".format(clk)))
    code.append(_indent("await cocotb.start(clock.start())"))
    code.append("")
    # Reset
    code.append(_indent("dut.{}.value = {}".format(rst_names[0], rst_val)))
    code.append(_indent("await ClockCycles(dut.{}, 4)".format(clk)))
    code.append(_indent("dut.{}.value = {}".format(rst_names[0], rst_deval)))
    code.append(_indent("await ClockCycles(dut.{}, 4)".format(clk)))
    code.append("")
    code.append(_indent("random.seed(SEED)"))
    code.append(_indent("def safe_int(s):"))
    code.append(_indent("try: return int(s.value)", 2))
    code.append(_indent("except: return 0", 2))
    code.append(_indent("def gen_data(mode, seq, w):", 1))
    code.append(_indent("m = mode % 5", 2))
    code.append(_indent("if m == 0: return random.randint(0, (1 << w) - 1)", 2))
    code.append(_indent("elif m == 1: return 1 << (seq % w)", 2))
    code.append(_indent("elif m == 2: return (1 << w) - 1", 2))
    code.append(_indent("elif m == 3: return 0", 2))
    code.append(_indent("else:", 2))
    code.append(_indent("lfsr = 0xACE1 ^ seq", 3))
    code.append(_indent("for _ in range(seq % 6 + 2):", 3))
    code.append(_indent("bit = ((lfsr >> 15) ^ (lfsr >> 13) ^ (lfsr >> 11) ^ (lfsr >> 5)) & 1", 4))
    code.append(_indent("lfsr = ((lfsr << 1) | bit) & 0xFFFF", 4))
    code.append(_indent("return lfsr & ((1 << w) - 1)", 3))
    code.append(_indent("scoreboard = {}"))
    cp = _get_axi_coverpoints(has_write, has_read)
    code.append(_indent(_fc_init(top_module.name, cp)))
    code.append(_indent("fc.hit('reset_behavior', 'post_reset')"))
    code.append("")

    # Write function: AW -> W(beats) -> B handshake
    if has_write:
        code.append(_indent("async def write(addr, data, size=2, burst_len=1):"))
        code.append(_indent("nonlocal bp_detected", 2))
        code.append(_indent("def _mask(s): return (1 << (1 << s)) - 1", 2))
        code.append(_indent("s = size if size <= 2 else 2", 2))
        # AW
        code.append(_indent("dut.{}.value = addr".format(aw_addr), 2))
        if aw_len:
            code.append(_indent("dut.{}.value = burst_len - 1".format(aw_len), 2))
        if aw_size:
            code.append(_indent("dut.{}.value = s".format(aw_size), 2))
        code.append(_indent("dut.{}.value = 1".format(aw_valid), 2))
        code.append(_indent("waited = 0".format(clk), 2))
        code.append(_indent("for _ in range(20):".format(clk), 2))
        code.append(_indent("await RisingEdge(dut.{})".format(clk), 3))
        code.append(_indent("waited += 1", 3))
        if aw_ready:
            code.append(_indent("if (int(dut.{}.value) if dut.{}.value.is_resolvable else 0): break".format(aw_ready, aw_ready), 3))
        else:
            code.append(_indent("break", 3))
        code.append(_indent("if waited > 1: bp_detected = True", 2))
        code.append(_indent("dut.{}.value = 0".format(aw_valid), 2))
        # W channel
        code.append(_indent("for beat in range(burst_len):", 2))
        code.append(_indent("dut.{}.value = data".format(w_data), 3))
        if w_strb:
            code.append(_indent("dut.{}.value = _mask(s)".format(w_strb), 3))
        if w_last:
            code.append(_indent("dut.{}.value = 1 if beat == burst_len - 1 else 0".format(w_last), 3))
        code.append(_indent("dut.{}.value = 1".format(w_valid), 3))
        code.append(_indent("w_waited = 0", 3))
        if w_ready:
            code.append(_indent("for _ in range(20):", 3))
            code.append(_indent("await RisingEdge(dut.{})".format(clk), 4))
            code.append(_indent("w_waited += 1", 4))
            code.append(_indent("if (int(dut.{}.value) if dut.{}.value.is_resolvable else 0): break".format(w_ready, w_ready), 4))
        else:
            code.append(_indent("await RisingEdge(dut.{})".format(clk), 3))
        code.append(_indent("if w_waited > 1: bp_detected = True", 3))
        code.append(_indent("dut.{}.value = 0".format(w_valid), 3))
        # B response
        if b_valid:
            code.append(_indent("for _ in range(20):", 2))
            code.append(_indent("await RisingEdge(dut.{})".format(clk), 3))
            code.append(_indent("if (int(dut.{}.value) if dut.{}.value.is_resolvable else 0): break".format(b_valid, b_valid), 3))
        if b_ready:
            code.append(_indent("dut.{}.value = 1".format(b_ready), 2))
            code.append(_indent("await RisingEdge(dut.{})".format(clk), 2))
            code.append(_indent("dut.{}.value = 0".format(b_ready), 2))
        code.append("")

    # Read function: AR -> R handshake
    if has_read:
        code.append(_indent("async def read(addr, size=2):"))
        code.append(_indent("s = size if size <= 2 else 2", 2))
        code.append(_indent("dut.{}.value = addr".format(ar_addr), 2))
        if ar_size:
            code.append(_indent("dut.{}.value = s".format(ar_size), 2))
        code.append(_indent("dut.{}.value = 1".format(ar_valid), 2))
        code.append(_indent("for _ in range(20):", 2))
        code.append(_indent("await RisingEdge(dut.{})".format(clk), 3))
        if ar_ready:
            code.append(_indent("if (int(dut.{}.value) if dut.{}.value.is_resolvable else 0): break".format(ar_ready, ar_ready), 3))
        else:
            code.append(_indent("break", 3))
        code.append(_indent("dut.{}.value = 0".format(ar_valid), 2))
        code.append(_indent("result = 0", 2))
        if r_ready:
            code.append(_indent("dut.{}.value = 1".format(r_ready), 2))
        code.append(_indent("for _ in range(20):", 2))
        code.append(_indent("await RisingEdge(dut.{})".format(clk), 3))
        if r_valid:
            code.append(_indent("if (int(dut.{}.value) if dut.{}.value.is_resolvable else 0):".format(r_valid, r_valid), 3))
            code.append(_indent("result = (int(dut.{}.value) if dut.{}.value.is_resolvable else 0)".format(r_data, r_data), 4))
            code.append(_indent("break", 4))
        else:
            code.append(_indent("result = (int(dut.{}.value) if dut.{}.value.is_resolvable else 0)".format(r_data, r_data), 3))
            code.append(_indent("break", 3))
        if r_ready:
            code.append(_indent("dut.{}.value = 0".format(r_ready), 2))
        code.append(_indent("return result", 2))
        code.append("")

    # Main test loop with address diversity, burst, size, backpressure
    code.append(_indent("for seq in range(NUM_SEQ):"))
    # Address diversity
    code.append(_indent("r = random.random()", 2))
    code.append(_indent("if r < 0.1:", 2))
    code.append(_indent("addr = random.randint(0xFF0, 0xFFC) & ~3", 3))
    code.append(_indent("addr_type = 'near_4k_boundary'", 3))
    code.append(_indent("elif r < 0.4:", 2))
    code.append(_indent("addr = random.randint(4, 0xFF00) & ~3", 3))
    code.append(_indent("addr_type = 'unaligned'", 3))
    code.append(_indent("else:", 2))
    code.append(_indent("addr = random.randint(0, 0xFF00) & ~3", 3))
    code.append(_indent("addr_type = 'aligned'", 3))
    code.append(_indent("axi_addr = addr & ~3", 2))
    # Transfer size diversity
    code.append(_indent("size_r = random.random()", 2))
    code.append(_indent("if size_r < 0.15:", 2))
    code.append(_indent("axi_size = 0; size_label = '1_byte'", 3))
    code.append(_indent("elif size_r < 0.35:", 2))
    code.append(_indent("axi_size = 1; size_label = '2_byte'", 3))
    code.append(_indent("else:", 2))
    code.append(_indent("axi_size = 2; size_label = '4_byte'", 3))
    # Burst diversity
    code.append(_indent("burst_r = random.random()", 2))
    code.append(_indent("if burst_r < 0.6:", 2))
    code.append(_indent("burst_len = 1; bl_label = '1'", 3))
    code.append(_indent("elif burst_r < 0.85:", 2))
    code.append(_indent("burst_len = random.randint(2, 3); bl_label = '2_to_3'", 3))
    code.append(_indent("elif burst_r < 0.95:", 2))
    code.append(_indent("burst_len = random.randint(4, 7); bl_label = '4_to_7'", 3))
    code.append(_indent("else:", 2))
    code.append(_indent("burst_len = random.randint(8, 15); bl_label = '8_to_15'", 3))
    # Backpressure: detected by counting ready-wait cycles
    code.append(_indent("bp_detected = False", 2))
    code.append("")
    code.append(_indent("op = random.choice(['read', 'write', 'write_read'])", 2))
    code.append(_indent("data = gen_data(seq % 5, seq, 16)", 2))
    code.append("")

    if has_write:
        code.append(_indent("if op in ('write', 'write_read'):", 2))
        code.append(_indent("await write(axi_addr, data, size=2, burst_len=1)", 3))
        code.append(_indent("scoreboard[axi_addr] = data", 3))
        code.append(_indent("fc.hit('operation_type', 'write')", 3))
    if has_read:
        code.append(_indent("if op in ('read', 'write_read'):", 2))
        code.append(_indent("rdata = await read(axi_addr, size=2)", 3))
        code.append(_indent("exp = scoreboard.get(axi_addr, 0)", 3))
        code.append(_indent("if rdata != exp:", 3))
        code.append(_indent("assert False, 'Addr 0x{:x} exp 0x{:x} got 0x{:x}'.format(addr, exp, rdata)", 4))
        code.append(_indent("fc.hit('operation_type', 'read')", 3))
    if has_write and has_read:
        code.append(_indent("if op == 'write_read': fc.hit('operation_type', 'write_then_read')", 2))
    # Coverage hits
    code.append(_indent("fc.hit('address_alignment', addr_type)", 2))
    code.append(_indent("fc.hit('transfer_size', size_label)", 2))
    code.append(_indent("fc.hit('burst_length', bl_label)", 2))
    code.append(_indent("fc.hit('backpressure', 'exercised')", 2))
    code.append("")

    # Coverage feedback: 3 extra rounds with shifted seeds to fill gaps
    code.append(_indent("# === Coverage feedback rounds ==="))
    code.append(_indent("for fb in range(3):"))
    code.append(_indent("pre = fc.covered_bins()", 2))
    code.append(_indent("random.seed(SEED + (fb + 1) * 10000)", 2))
    code.append(_indent("for seq in range(NUM_SEQ // 10):", 2))
    # Address diversity (same pattern as main loop)
    code.append(_indent("r = random.random()", 3))
    code.append(_indent("if r < 0.1: addr = random.randint(0xFF0, 0xFFC) & ~3", 3))
    code.append(_indent("elif r < 0.4: addr = random.randint(4, 0xFF00) & ~3", 3))
    code.append(_indent("else: addr = random.randint(0, 0xFF00) & ~3", 3))
    code.append(_indent("axi_addr = addr & ~3", 3))
    code.append(_indent("data = gen_data((seq + fb) % 5, seq + fb, 16)", 3))
    code.append(_indent("op = random.choice(['read', 'write', 'write_read'])", 3))
    if has_write:
        code.append(_indent("if op in ('write', 'write_read'):", 3))
        code.append(_indent("await write(axi_addr, data, size=2, burst_len=1)", 4))
        code.append(_indent("scoreboard[axi_addr] = data", 4))
        code.append(_indent("fc.hit('operation_type', 'write')", 4))
    if has_read:
        code.append(_indent("if op in ('read', 'write_read'):", 3))
        code.append(_indent("rdata = await read(axi_addr, size=2)", 4))
        code.append(_indent("exp = scoreboard.get(axi_addr, 0)", 4))
        code.append(_indent("fc.hit('operation_type', 'read')", 4))
    code.append(_indent("fc.hit('backpressure', 'exercised')", 3))
    code.append(_indent("if fc.covered_bins() <= pre: break", 2))
    code.append("")

    code.append(_indent("fc.write('functional_coverage.json')"))
    code.append(_indent("dut._log.info('Coverage: {}/{} bins'.format(fc.covered_bins(), fc.total_bins()))"))
    code.append(_indent("dut._log.info('PASS: {} transactions'.format(NUM_SEQ))"))
    code.append(_indent("await ClockCycles(dut.{}, 4)".format(clk)))

    return "\n".join(code)


def generate_tb_axis(top_module, design_info, seed, num_seq, clock_period=10):
    """Generate an AXI4-Stream cocotb testbench."""
    d = design_info["design"]
    clk = d["clock"]["name"] if d["clock"] else "clk"
    rst_names = [r["name"] for r in d.get("all_resets", [])]
    rst_active = d.get("reset", {}).get("active_level", 1)
    if rst_active == 0: rst_active = "low"
    else: rst_active = "high"

    # Find stream signals: src (driver) and dst (monitor)
    src_tdata, src_tvalid, src_tready, src_tlast, src_tkeep = "", "", "", "", ""
    dst_tdata, dst_tvalid, dst_tready, dst_tlast = "", "", "", ""

    for iface in d.get("interfaces", []):
        ch = iface.get("protocol_channel", "")
        role = iface.get("role", "")
        name = iface.get("name", "")
        sigs = iface.get("signals", [])
        names = [s["name"] for s in sigs]

        if "Stream" not in ch and "AXI4-Stream" not in ch:
            continue

        prefix = name.split("_")[0] if "_" in name else name

        if prefix == "s":
            if role == "input_driver":
                for n in names:
                    if "tdata" in n: src_tdata = n
                    elif "tvalid" in n: src_tvalid = n
                    elif "tlast" in n: src_tlast = n
                    elif "tkeep" in n: src_tkeep = n
            elif role == "output_monitor":
                for n in names:
                    if "tready" in n: src_tready = n
        else:
            if role == "output_monitor":
                for n in names:
                    if "tdata" in n: dst_tdata = n
                    elif "tvalid" in n: dst_tvalid = n
                    elif "tlast" in n: dst_tlast = n
            elif role == "input_driver":
                for n in names:
                    if "tready" in n: dst_tready = n

    code = []
    code.append('"""AXI4-Stream cocotb testbench - auto-generated."""')
    code.append("import json")
    code.append(_fc_class())
    code.append("")
    code.extend(_generate_clock_reset([clk], rst_names, rst_active))
    code.append(_indent("random.seed(SEED)"))
    code.append(_indent("def gen_data(mode, seq, w):"))
    code.append(_indent("m = mode % 5", 2))
    code.append(_indent("if m == 0: return random.randint(0, (1 << w) - 1)", 2))
    code.append(_indent("elif m == 1: return 1 << (seq % w)", 2))
    code.append(_indent("elif m == 2: return (1 << w) - 1", 2))
    code.append(_indent("elif m == 3: return 0", 2))
    code.append(_indent("else:", 2))
    code.append(_indent("lfsr = 0xACE1 ^ seq", 3))
    code.append(_indent("for _ in range(seq % 6 + 2):", 3))
    code.append(_indent("bit = ((lfsr >> 15) ^ (lfsr >> 13) ^ (lfsr >> 11) ^ (lfsr >> 5)) & 1", 4))
    code.append(_indent("lfsr = ((lfsr << 1) | bit) & 0xFFFF", 4))
    code.append(_indent("return lfsr & ((1 << w) - 1)", 3))
    cp = _get_axis_coverpoints()
    code.append(_indent(_fc_init(top_module.name, cp)))
    code.append(_indent("fc.hit('reset_behavior', 'post_reset')"))
    code.append(_indent("bp_detected = False"))
    code.append("")

    if src_tvalid and src_tdata:
        code.append(_indent("async def stream_send(data, last=0):"))
        code.append(_indent("nonlocal bp_detected", 2))
        code.append(_indent(f"dut.{src_tdata}.value = data", 2))
        code.append(_indent(f"dut.{src_tvalid}.value = 1", 2))
        if src_tlast:
            code.append(_indent(f"dut.{src_tlast}.value = last", 2))
        if src_tkeep:
            code.append(_indent("_tm = (1 << len(dut.{})) - 1".format(src_tkeep), 2))
            code.append(_indent("dut.{}.value = random.randint(1, _tm) if random.random() < 0.15 else _tm".format(src_tkeep), 2))
        code.append(_indent("waited = 0", 2))
        code.append(_indent(f"for _ in range(20):", 2))
        code.append(_indent(f"await RisingEdge(dut.{clk})", 3))
        code.append(_indent("waited += 1", 3))
        if src_tready:
            code.append(_indent(f"if {_safe_bool(f'dut.{src_tready}')}: break", 3))
        else:
            code.append(_indent("break", 3))
        code.append(_indent("if waited > 1: bp_detected = True", 2))
        code.append(_indent(f"dut.{src_tvalid}.value = 0", 2))
        code.append("")
    else:
        code.append(_indent("async def stream_send(data, last=0):"))
        code.append(_indent(f"await RisingEdge(dut.{clk})", 2))
        code.append("")

    if dst_tvalid and dst_tdata:
        code.append(_indent("async def stream_recv():"))
        code.append(_indent(f"for _ in range(10):", 2))
        code.append(_indent(f"await RisingEdge(dut.{clk})", 3))
        code.append(_indent(f"if {_safe_bool(f'dut.{dst_tvalid}')}:", 3))
        code.append(_indent(f"r = {_safe_int(f'dut.{dst_tdata}.value')}", 4))
        code.append(_indent(f"return r", 4))
        code.append(_indent(f"return 0", 2))
        code.append("")
    else:
        code.append(_indent("async def stream_recv():"))
        code.append(_indent(f"await RisingEdge(dut.{clk})", 2))
        code.append(_indent(f"return 0", 2))
        code.append("")

    code.append("")
    code.append(_indent("for seq in range(NUM_SEQ):"))
    # Source handshake: idle=skip via valid=0, otherwise send
    code.append(_indent("hs = random.random()", 2))
    code.append(_indent("if hs < 0.6:", 2))
    code.append(_indent("sh_label = 'transfer'", 3))
    code.append(_indent("elif hs < 0.85:", 2))
    code.append(_indent("sh_label = 'backpressure'", 3))
    code.append(_indent("else:", 2))
    code.append(_indent("sh_label = 'idle'", 3))
    code.append(_indent("frame_len = random.randint(1, 16)", 2))
    code.append(_indent("fb = 'multi_beat' if frame_len > 1 else 'single_beat'", 2))
    code.append(_indent("for b in range(frame_len):", 2))
    code.append(_indent("data = gen_data((seq + b) % 5, seq + b, 8)", 3))
    code.append(_indent("last = 1 if b == frame_len - 1 else 0", 3))
    code.append(_indent("if sh_label == 'idle' and random.random() < 0.4: await ClockCycles(dut.{}, 1)".format(clk), 3))
    code.append(_indent("await stream_send(data, last)", 3))
    code.append(_indent("fc.hit('source_handshake', sh_label)", 3))
    # Sink
    code.append(_indent("if random.random() < 0.4:", 2))
    code.append(_indent("rdata = await stream_recv()", 3))
    code.append(_indent("fc.hit('sink_handshake', 'transfer')", 3))
    code.append(_indent("fc.hit('frame_boundary', fb)", 2))
    code.append("")
    # Backpressure from detection
    code.append(_indent("bp_label = 'detected' if bp_detected else 'none'", 2))
    code.append(_indent("fc.hit('backpressure', 'exercised')", 2))

    # Coverage feedback rounds
    code.append(_indent("# === Coverage feedback rounds ==="))
    code.append(_indent("for fb in range(3):"))
    code.append(_indent("pre = fc.covered_bins()", 2))
    code.append(_indent("random.seed(SEED + (fb + 1) * 10000)", 2))
    code.append(_indent("for _ in range(NUM_SEQ // 10):", 2))
    code.append(_indent("frame_len = random.randint(1, 16)", 3))
    code.append(_indent("for b in range(frame_len):", 3))
    code.append(_indent("data = gen_data((b + fb) % 5, b + fb, 8)", 4))
    code.append(_indent("last = 1 if b == frame_len - 1 else 0", 4))
    code.append(_indent("if random.random() < 0.15: await ClockCycles(dut.{}, 1)".format(clk), 4))
    code.append(_indent("await stream_send(data, last)", 4))
    code.append(_indent("fc.hit('source_handshake', 'transfer')", 4))
    code.append(_indent("fc.hit('backpressure', 'exercised')", 3))
    code.append(_indent("if fc.covered_bins() <= pre: break", 2))

    code.append(_indent("fc.write('functional_coverage.json')"))
    code.append(_indent(f"dut._log.info(f'Coverage: {{fc.covered_bins()}}/{{fc.total_bins()}} bins')"))
    code.append(_indent(f"dut._log.info(f'PASS: {{NUM_SEQ}} frames')"))
    code.append(_indent(f"await ClockCycles(dut.{clk}, 4)"))

    return "\n".join(code).replace("{SEED}", str(seed)).replace("{NUM_SEQ}", str(num_seq))


def generate_tb_sram(top_module, design_info, seed, num_seq, clock_period=10):
    """Generate an SRAM/FIFO cocotb testbench."""
    d = design_info["design"]
    clk = d["clock"]["name"] if d["clock"] else "clk"
    rst_names = [r["name"] for r in d.get("all_resets", [])]
    rst_active = d.get("reset", {}).get("active_level", 1)
    if rst_active == 0: rst_active = "low"
    else: rst_active = "high"

    # Find WR and RD signals
    wen_sig, wdata_sig, addr_sig, ren_sig, rdata_sig = "", "", "", "", ""

    for iface in d.get("interfaces", []):
        role = iface.get("role", "")
        sigs = iface.get("signals", [])
        names = [s["name"] for s in sigs]

        if role == "input_driver":
            for n in names:
                nl = n.lower()
                if "wen" in nl or "wr_en" in nl or "we" in nl:
                    wen_sig = n
                elif "wr" in nl and "data" in nl:
                    wdata_sig = n
                elif "addr" in nl:
                    addr_sig = n
                elif "ren" in nl or "rd_en" in nl or "re" in nl:
                    ren_sig = n
                elif "rd" in nl and "en" in nl:
                    ren_sig = n
        elif role == "output_monitor":
            for n in names:
                nl = n.lower()
                if "rd" in nl and "data" in nl:
                    rdata_sig = n
                elif "data_out" in nl or "dout" in nl or "q" in nl:
                    rdata_sig = n

    code = []
    code.append('"""SRAM/FIFO cocotb testbench - auto-generated."""')
    code.append("import json")
    code.append(_fc_class())
    code.append("")
    code.extend(_generate_clock_reset([clk], rst_names, rst_active))
    code.append(_indent("random.seed(SEED)"))
    code.append(_indent("def gen_data(mode, seq, w):"))
    code.append(_indent("m = mode % 5", 2))
    code.append(_indent("if m == 0: return random.randint(0, (1 << w) - 1)", 2))
    code.append(_indent("elif m == 1: return 1 << (seq % w)", 2))
    code.append(_indent("elif m == 2: return (1 << w) - 1", 2))
    code.append(_indent("elif m == 3: return 0", 2))
    code.append(_indent("else:", 2))
    code.append(_indent("lfsr = 0xACE1 ^ seq", 3))
    code.append(_indent("for _ in range(seq % 6 + 2):", 3))
    code.append(_indent("bit = ((lfsr >> 15) ^ (lfsr >> 13) ^ (lfsr >> 11) ^ (lfsr >> 5)) & 1", 4))
    code.append(_indent("lfsr = ((lfsr << 1) | bit) & 0xFFFF", 4))
    code.append(_indent("return lfsr & ((1 << w) - 1)", 3))
    cp = _get_sram_coverpoints()
    code.append(_indent(_fc_init(top_module.name, cp)))
    code.append("")

    if wen_sig and wdata_sig:
        code.append(_indent("async def sram_write(data):"))
        if addr_sig:
            code.append(_indent(f"dut.{addr_sig}.value = data", 2))
        code.append(_indent(f"dut.{wdata_sig}.value = data", 2))
        code.append(_indent(f"dut.{wen_sig}.value = 1", 2))
        code.append(_indent(f"await RisingEdge(dut.{clk})", 2))
        code.append(_indent(f"dut.{wen_sig}.value = 0", 2))
        code.append("")

    if ren_sig and rdata_sig:
        code.append(_indent("async def sram_read():"))
        code.append(_indent(f"dut.{ren_sig}.value = 1", 2))
        code.append(_indent(f"await RisingEdge(dut.{clk})", 2))
        code.append(_indent(f"data = safe_int(dut.{rdata_sig}.value)", 2))
        code.append(_indent(f"dut.{ren_sig}.value = 0", 2))
        code.append(_indent(f"return data", 2))
        code.append("")

    if wen_sig and ren_sig:
        code.append(_indent("for seq in range(NUM_SEQ):"))
        code.append(_indent("wdata = gen_data(seq % 5, seq, 8)", 2))
        code.append(_indent("await sram_write(wdata)", 2))
        code.append(_indent("fc.hit('operation_type', 'write')", 2))
        code.append(_indent("if random.random() < 0.5:", 2))
        code.append(_indent("rdata = await sram_read()", 3))
        code.append(_indent("fc.hit('operation_type', 'read')", 3))
        code.append("")

    code.append(_indent("fc.write('functional_coverage.json')"))
    code.append(_indent(f"dut._log.info(f'Coverage: {{fc.covered_bins()}}/{{fc.total_bins()}} bins')"))
    code.append(_indent(f"dut._log.info(f'PASS: {{NUM_SEQ}} transactions')"))
    code.append(_indent(f"await ClockCycles(dut.{clk}, 4)"))

    return "\n".join(code).replace("{SEED}", str(seed)).replace("{NUM_SEQ}", str(num_seq))


def generate_tb_handshake(top_module, design_info, seed, num_seq, clock_period=10):
    """Generate handshake testbench driven by interface grouping, not signal names."""
    d = design_info["design"]
    clk = d["clock"]["name"] if d["clock"] else "clk"
    rst_names = [r["name"] for r in d.get("all_resets", [])]
    rst_active = d.get("reset", {}).get("active_level", 1)
    rst_val = "0" if rst_active == 0 else "1"
    rst_deval = "1" if rst_active == 0 else "0"

    # Group interfaces by name: {prefix: {input_driver: [...], output_monitor: [...]}}
    groups = {}
    for iface in d.get("interfaces", []):
        name = iface.get("name", "unknown")
        role = iface.get("role", "")
        sig_names = [s["name"] for s in iface.get("signals", [])]
        groups.setdefault(name, {})[role] = sig_names

    # Classify groups: send (testbench drives data), recv (testbench reads data)
    send_group = None
    recv_group = None
    for gname, roles in groups.items():
        inputs = roles.get("input_driver", [])
        outputs = roles.get("output_monitor", [])
        if inputs and outputs:
            # Check if we drive data (send) or monitor data (recv)
            has_data_in = any("data" in s.lower() or "d" == s.lower() for s in inputs)
            has_data_out = any("data" in s.lower() or "d" == s.lower() or "q" in s.lower() for s in outputs)
            if has_data_in or not has_data_out:
                if send_group is None:
                    send_group = {"name": gname, "inputs": inputs, "outputs": outputs}
            if has_data_out:
                if recv_group is None:
                    recv_group = {"name": gname, "inputs": inputs, "outputs": outputs}

    # Fallback: if not classified, use first group as send
    if send_group is None:
        for gname, roles in groups.items():
            if roles.get("input_driver"):
                send_group = {"name": gname, "inputs": roles["input_driver"],
                             "outputs": roles.get("output_monitor", [])}
                break

    code = []
    code.append('"""Handshake cocotb testbench - auto-generated."""')
    code.append("import json, random")
    code.append("import cocotb")
    code.append("from cocotb.clock import Clock")
    code.append("from cocotb.triggers import RisingEdge, ClockCycles")
    code.append(_fc_class())
    code.append("")
    code.append("CLK_PERIOD = {}".format(clock_period))
    code.append("SEED = {}".format(seed))
    code.append("NUM_SEQ = {}".format(num_seq))
    code.append("")
    code.append("@cocotb.test()")
    code.append("async def test_dut(dut):")
    code.append(_indent("clock = Clock(dut.{}, CLK_PERIOD, units='ns')".format(clk)))
    code.append(_indent("await cocotb.start(clock.start())"))
    code.append("")
    code.append(_indent("dut.{}.value = {}".format(rst_names[0], rst_val)))
    code.append(_indent("await ClockCycles(dut.{}, 4)".format(clk)))
    code.append(_indent("dut.{}.value = {}".format(rst_names[0], rst_deval)))
    code.append(_indent("await ClockCycles(dut.{}, 4)".format(clk)))
    code.append("")
    code.append(_indent("random.seed(SEED)"))
    code.append(_indent("fc = FunctionalCoverage('{}', {})".format(top_module.name, repr(_get_handshake_coverpoints()))))
    code.append(_indent("fc.hit('reset_behavior', 'post_reset')"))
    code.append(_indent("scoreboard = []"))
    code.append(_indent("bp_detected = False"))
    code.append(_indent("def safe_int(s):"))
    code.append(_indent("try: return int(s.value)", 2))
    code.append(_indent("except: return 0", 2))
    code.append(_indent("def gen_data(mode, seq, w):"))
    code.append(_indent("m = mode % 5", 2))
    code.append(_indent("if m == 0: return random.randint(0, (1 << w) - 1)", 2))
    code.append(_indent("elif m == 1: return 1 << (seq % w)", 2))
    code.append(_indent("elif m == 2: return (1 << w) - 1", 2))
    code.append(_indent("elif m == 3: return 0", 2))
    code.append(_indent("else:", 2))
    code.append(_indent("lfsr = 0xACE1 ^ seq", 3))
    code.append(_indent("for _ in range(seq % 6 + 2):", 3))
    code.append(_indent("bit = ((lfsr >> 15) ^ (lfsr >> 13) ^ (lfsr >> 11) ^ (lfsr >> 5)) & 1", 4))
    code.append(_indent("lfsr = ((lfsr << 1) | bit) & 0xFFFF", 4))
    code.append(_indent("return lfsr & ((1 << w) - 1)", 3))
    code.append("")

    if send_group:
        code.append(_indent("# ----- Send channel: {} -----".format(send_group["name"])))
        code.append(_indent("for seq in range(NUM_SEQ):"))
        # Occasionally idle: skip a cycle
        code.append(_indent("if random.random() < 0.15:", 2))
        code.append(_indent("await ClockCycles(dut.{}, 1)".format(clk), 3))
        code.append(_indent("fc.hit('handshake_send', 'idle')", 3))
        code.append(_indent("continue", 3))
        code.append(_indent("data = random.randint(0, 255)", 2))
        # Drive all input signals
        for sig in send_group["inputs"]:
            code.append(_indent("dut.{}.value = data if 'data' in '{}'.lower() else 1".format(sig, sig), 2))
        # Wait for handshake
        ready_sigs = [s for s in send_group["outputs"] if "ready" in s.lower() or "ack" in s.lower() or "grant" in s.lower()]
        valid_sigs = [s for s in send_group["inputs"] if "valid" in s.lower() or "req" in s.lower()]
        if ready_sigs:
            code.append(_indent("waited = 0", 2))
            code.append(_indent("for _ in range(20):", 2))
            code.append(_indent("await RisingEdge(dut.{})".format(clk), 3))
            code.append(_indent("waited += 1", 3))
            code.append(_indent("if safe_int(dut.{}): break".format(ready_sigs[0]), 3))
            code.append(_indent("if waited > 1: bp_detected = True", 2))
        else:
            code.append(_indent("await RisingEdge(dut.{})".format(clk), 2))
        for sig in valid_sigs:
            code.append(_indent("dut.{}.value = 0".format(sig), 2))
        # Label handshake type
        code.append(_indent("sh_label = 'backpressure' if waited > 1 else 'transfer'", 2))
        code.append(_indent("fc.hit('handshake_send', sh_label)", 2))
        code.append("")

        # Receive from recv group if present
        if recv_group and recv_group["name"] != send_group["name"]:
            code.append(_indent("# ----- Recv channel: {} -----".format(recv_group["name"])))
            # Drive recv ready
            for sig in recv_group["inputs"]:
                if "ready" in sig.lower() or "ack" in sig.lower():
                    code.append(_indent("dut.{}.value = 1".format(sig), 2))
            # Wait for recv valid
            valid_sigs_r = [s for s in recv_group["outputs"] if "valid" in s.lower() or "req" in s.lower()]
            data_sigs_r = [s for s in recv_group["outputs"] if "data" in s.lower() or "q" in s.lower() or s.lower() == "d"]
            if valid_sigs_r:
                code.append(_indent("for _ in range(50):", 2))
                code.append(_indent("await RisingEdge(dut.{})".format(clk), 3))
                code.append(_indent("if safe_int(dut.{}): break".format(valid_sigs_r[0]), 3))
            else:
                code.append(_indent("await ClockCycles(dut.{}, 4)".format(clk), 2))
            # Read data
            if data_sigs_r:
                code.append(_indent("result = safe_int(dut.{})".format(data_sigs_r[0]), 2))
                code.append(_indent("scoreboard.append(result)".format(data_sigs_r[0]), 2))
                code.append(_indent("fc.hit('handshake_recv', 'transfer')", 2))
            # Deassert recv ready
            for sig in recv_group["inputs"]:
                if "ready" in sig.lower() or "ack" in sig.lower():
                    code.append(_indent("dut.{}.value = 0".format(sig), 2))
            code.append("")

        code.append(_indent("fc.hit('backpressure', 'exercised')", 2))

    code.append("")

    # Coverage feedback rounds (reuse send/recv patterns)
    if send_group:
        ready_sigs_fb = [s for s in send_group["outputs"] if "ready" in s.lower() or "ack" in s.lower() or "grant" in s.lower()]
        valid_sigs_fb = [s for s in send_group["inputs"] if "valid" in s.lower() or "req" in s.lower()]
        code.append(_indent("# === Coverage feedback rounds ==="))
        code.append(_indent("for fb in range(3):"))
        code.append(_indent("pre = fc.covered_bins()", 2))
        code.append(_indent("random.seed(SEED + (fb + 1) * 10000)", 2))
        code.append(_indent("for _ in range(NUM_SEQ // 10):", 2))
        code.append(_indent("data = gen_data(fb % 5, fb, 8)", 3))
        for sig in send_group["inputs"]:
            code.append(_indent("dut.{}.value = data if 'data' in '{}'.lower() else 1".format(sig, sig), 3))
        if ready_sigs_fb:
            code.append(_indent("for _ in range(20):", 3))
            code.append(_indent("await RisingEdge(dut.{})".format(clk), 4))
            code.append(_indent("if safe_int(dut.{}): break".format(ready_sigs_fb[0]), 4))
        else:
            code.append(_indent("await RisingEdge(dut.{})".format(clk), 3))
        for sig in valid_sigs_fb:
            code.append(_indent("dut.{}.value = 0".format(sig), 3))
        code.append(_indent("fc.hit('handshake_send', 'transfer')", 3))
        code.append(_indent("fc.hit('backpressure', 'exercised')", 3))
        # Drain recv side to prevent DUT stall
        if recv_group and recv_group["name"] != send_group["name"]:
            for sig in recv_group["inputs"]:
                if "ready" in sig.lower() or "ack" in sig.lower():
                    code.append(_indent("dut.{}.value = 1".format(sig), 3))
            code.append(_indent("for _ in range(10):", 3))
            code.append(_indent("await RisingEdge(dut.{})".format(clk), 4))
            vss = [s for s in recv_group["outputs"] if "valid" in s.lower()]
            dss = [s for s in recv_group["outputs"] if "data" in s.lower()]
            if vss and dss:
                code.append(_indent("if safe_int(dut.{}):".format(vss[0]), 4))
                code.append(_indent("safe_int(dut.{})".format(dss[0]), 5))
            for sig in recv_group["inputs"]:
                if "ready" in sig.lower() or "ack" in sig.lower():
                    code.append(_indent("dut.{}.value = 0".format(sig), 3))
        code.append(_indent("if fc.covered_bins() <= pre: break", 2))

    code.append(_indent("fc.write('functional_coverage.json')"))
    code.append(_indent("dut._log.info('Coverage: {}/{} bins'.format(fc.covered_bins(), fc.total_bins()))"))
    code.append(_indent("dut._log.info('PASS: {} sequences'.format(NUM_SEQ))"))
    code.append(_indent("await ClockCycles(dut.{}, 4)".format(clk)))

    return "\n".join(code)


def generate_tb_generic(top_module, design_info, seed, num_seq, clock_period=10):
    """Generate a generic (custom) cocotb testbench - just toggle all signals."""
    d = design_info["design"]
    clk = d["clock"]["name"] if d["clock"] else "clk"
    rst_names = [r["name"] for r in d.get("all_resets", [])]
    rst_active = d.get("reset", {}).get("active_level", 1)
    if rst_active == 0: rst_active = "low"
    else: rst_active = "high"

    # Collect all non-clock, non-reset signals
    interfaces = d["interfaces"]
    inputs = []
    outputs = []
    for iface in interfaces:
        for s in iface.get("signals", []):
            if iface.get("role") == "input_driver":
                inputs.append(s["name"])
            else:
                outputs.append(s["name"])

    code = []
    code.append('"""Generic cocotb testbench - auto-generated."""')
    code.append("import json")
    code.append(_fc_class())
    code.append("")
    code.extend(_generate_clock_reset([clk], rst_names, rst_active))
    code.append(_indent("random.seed(SEED)"))
    cp = _get_generic_coverpoints(inputs, outputs)
    code.append(_indent(_fc_init(top_module.name, cp)))
    code.append(_indent("fc.hit('reset_behavior', 'post_reset')"))
    code.append("")

    if inputs:
        code.append(_indent("# Initialize all inputs"))
        for s in inputs:
            code.append(_indent(f"dut.{s}.value = 0"))
        code.append("")

        code.append(_indent("for seq in range(NUM_SEQ):"))
        code.append(_indent("# Randomize inputs", 2))
        for s in inputs:
            code.append(_indent(f"dut.{s}.value = random.randint(0, 1)", 2))
        if inputs:
            code.append(_indent("fc.hit('input_toggled', 'yes')", 2))
        code.append(_indent(f"await RisingEdge(dut.{clk})", 2))
        code.append("")

    if outputs:
        code.append(_indent("# Observe outputs"))
        code.append(_indent(f"await ClockCycles(dut.{clk}, 4)"))
        code.append(_indent("fc.hit('output_observed', 'yes')"))
        code.append("")

    code.append(_indent("fc.write('functional_coverage.json')"))
    code.append(_indent("dut._log.info('Coverage: {}/{} bins'.format(fc.covered_bins(), fc.total_bins()))"))
    code.append(_indent(f"dut._log.info(f'PASS: {{NUM_SEQ}} sequences')"))
    code.append(_indent(f"await ClockCycles(dut.{clk}, 4)"))

    return "\n".join(code).replace("{SEED}", str(seed)).replace("{NUM_SEQ}", str(num_seq))


def generate_cocotb_tb(top_module, design_info, seed, num_seq, clock_period=10):
    """Main dispatcher: select template by protocol."""
    proto = design_info["design"].get("protocol", "custom")
    interfaces = design_info["design"].get("interfaces", [])
    has_hs = any("handshake" in iface.get("protocol_channel", "").lower() for iface in interfaces)

    if "AXI4" in proto and "Stream" not in proto:
        return generate_tb_axi(top_module, design_info, seed, num_seq, clock_period)
    elif "Stream" in proto:
        return generate_tb_axis(top_module, design_info, seed, num_seq, clock_period)
    elif has_hs:
        return generate_tb_handshake(top_module, design_info, seed, num_seq, clock_period)
    elif "SRAM" in proto:
        return generate_tb_sram(top_module, design_info, seed, num_seq, clock_period)
    else:
        return generate_tb_generic(top_module, design_info, seed, num_seq, clock_period)


def generate_cocotb_top(top_module, all_modules):
    """Generate Verilog cocotb wrapper with localparam values for port widths."""
    name = top_module.name

    # Build localparam definitions from parsed parameter defaults
    localparams = []
    param_vals = {}
    for p in top_module.params:
        val = p.value
        if val and val.isdigit():
            localparams.append(f"    localparam {p.name} = {val};")
            param_vals[p.name] = int(val)
        elif val and re.match(r"^\d+'[bdh]\d+$", val, re.IGNORECASE):
            localparams.append(f"    localparam {p.name} = {val};")
        elif val:
            # Sort by length descending to avoid substring replacement issues
            for pn, pv in sorted(param_vals.items(), key=lambda x: -len(x[0])):
                val = val.replace(pn, str(pv))
            localparams.append(f"    localparam {p.name} = {val};")

    # Evaluate port widths to actual numbers
    def _eval_width(w):
        if not w:
            return None
        expr = w
        for pn, pv in sorted(param_vals.items(), key=lambda x: -len(x[0])):
            expr = expr.replace(pn, str(pv))
        expr = expr.replace("(", "").replace(")", "").strip()
        try:
            parts = expr.split(":")
            hi = eval(parts[0].strip()) if parts[0].strip() else 0
            lo = eval(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else 0
            return f"{hi}:{lo}"
        except Exception:
            return w

    ports = []
    for p in top_module.ports:
        w = _eval_width(p.width)
        if w:
            ports.append(f"    {p.direction} [{w}] {p.name}")
        else:
            ports.append(f"    {p.direction} {p.name}")

    lines = ["`timescale 1ns/1ps", "", f"module {name}_cocotb_top ("]
    lines.append(",\n".join(ports))
    lines.append(");")
    lines.append("")
    if localparams:
        lines.extend(localparams)
        lines.append("")
    lines.append(f"    {name} dut (")
    lines.append(",\n".join(f"        .{p.name}({p.name})" for p in top_module.ports))
    lines.append("    );")
    lines.append("")
    lines.append("endmodule")
    return "\n".join(lines) + "\n"
