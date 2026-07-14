import os
import re
import subprocess
import tempfile
from utils.helpers import find_verilog_files, read_file


IVERILOG = r"F:\iverilog\iverilog\bin\iverilog.exe"


class PortInfo:
    def __init__(self, name, direction, width=None, port_type="wire"):
        self.name = name
        self.direction = direction
        self.width = width
        self.port_type = port_type

    def to_dict(self):
        d = {"name": self.name, "direction": self.direction, "type": self.port_type}
        if self.width:
            d["width"] = self.width
        return d


class ParamInfo:
    def __init__(self, name, value=None):
        self.name = name
        self.value = value

    def to_dict(self):
        d = {"name": self.name}
        if self.value:
            d["value"] = self.value.strip()
        return d


class ModuleInfo:
    def __init__(self, name):
        self.name = name
        self.params = []
        self.ports = []
        self.file_path = ""
        self.reset_active = "high"

    def detect_reset_polarity(self, content):
        rst_names = self.reset_signals()
        if not rst_names:
            return
        rst = rst_names[0]
        for rst_name in set([rst, rst + "_n", rst.replace("_n", "")]):
            if re.search(r"negedge\s+" + re.escape(rst_name), content, re.IGNORECASE):
                self.reset_active = "low"
                return
            if re.search(r"!\s*" + re.escape(rst_name), content, re.IGNORECASE):
                self.reset_active = "low"
                return

    def clock_signals(self):
        from utils.helpers import is_clock
        return [p.name for p in self.ports if is_clock(p.name) and p.direction == "input"]

    def reset_signals(self):
        from utils.helpers import is_reset
        return [p.name for p in self.ports if is_reset(p.name)]

    def input_signals(self):
        return [p for p in self.ports if p.direction == "input"]

    def output_signals(self):
        return [p for p in self.ports if p.direction == "output"]

    def io_signals(self):
        return [p for p in self.ports if p.direction in ("inout", "output") and "clk" not in p.name.lower()]


def _preprocess_with_iverilog(filepath):
    lines = read_file(filepath)
    if not lines.strip().startswith("`timescale"):
        lines = "`timescale 1ns/1ps\n" + lines

    with tempfile.NamedTemporaryFile(mode="w", suffix=".v", delete=False, encoding="utf-8") as tf:
        tf.write(lines)
        tmp_in = tf.name

    tmp_out = tmp_in + ".pp"
    env = os.environ.copy()
    env["PATH"] = os.path.dirname(IVERILOG) + ";" + env.get("PATH", "")
    env["IVL_LIBRARY_DIR"] = os.path.join(os.path.dirname(IVERILOG), "..", "lib", "ivl")

    try:
        subprocess.run(
            [IVERILOG, "-E", "-o", tmp_out, tmp_in],
            capture_output=True, text=True, timeout=30, env=env
        )
        if os.path.isfile(tmp_out) and os.path.getsize(tmp_out) > 0:
            preproc = read_file(tmp_out)
            if preproc.count("module") >= lines.count("module"):
                return preproc
        return lines
    except Exception:
        return lines
    finally:
        for f in [tmp_in, tmp_out]:
            try:
                os.unlink(f)
            except OSError:
                pass


def parse_verilog_file(filepath):
    content = _preprocess_with_iverilog(filepath)
    modules = []

    mod_pattern = re.compile(
        r"^\s*module\s+(\w+)\s*"
        r"(?:#\s*\(\s*([\s\S]*?)\)\s*)?"
        r"\(",
        re.MULTILINE,
    )

    for m in mod_pattern.finditer(content):
        mod = ModuleInfo(m.group(1))
        mod.file_path = filepath

        params_text = m.group(2)
        if params_text:
            param_entries = split_parameters(params_text)
            for name, val in param_entries:
                mod.params.append(ParamInfo(name, val))

        ports_text = extract_port_list(content, m.end() - 1)
        mod.ports = parse_ports(ports_text)
        mod.detect_reset_polarity(content)
        modules.append(mod)

    return modules


def split_parameters(text):
    entries = []
    depth = 0
    current = ""
    for ch in text:
        if ch in "([":
            depth += 1
            current += ch
        elif ch in ")]":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            entries.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        entries.append(current.strip())

    result = []
    for e in entries:
        e = e.strip()
        e = re.sub(r"//.*$", "", e, flags=re.MULTILINE)
        e = e.strip()
        if not e:
            continue
        parts = e.split("=", 1)
        name = (
            parts[0]
            .strip()
            .replace("parameter", "")
            .replace("localparam", "")
            .strip()
        )
        name = name.split()[-1] if name else ""
        val = parts[1].strip() if len(parts) > 1 else None
        if name:
            result.append((name, val))
    return result


def extract_port_list(content, start_pos):
    depth = 0
    for i in range(start_pos, len(content)):
        ch = content[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                port_text = content[start_pos + 1 : i]
                port_text = re.sub(r"//.*", "", port_text)
                port_text = re.sub(r"/\*.*?\*/", "", port_text, flags=re.DOTALL)
                return port_text
    return ""


def parse_ports(ports_text):
    """
    Parse port declarations.
    Strategy: strip all type keywords (reg/wire/tri/logic) first,
    then match direction + optional [width] + name.
    """
    ports = []
    text = ports_text.replace("\n", " ").replace("\r", " ")

    # Remove type keywords: reg, wire, tri, logic
    text = re.sub(r"\b(reg|wire|tri|logic)\b", "", text, flags=re.IGNORECASE)

    # Remove line comments
    text = re.sub(r"//.*", "", text)

    # Match: direction [width] name  (width brackets may not have spaces around)
    pattern = r"(input|output|inout)\s+(?:\[\s*([^\[\]]+?)\s*\]\s*)?(\w+)"
    for m in re.finditer(pattern, text, re.IGNORECASE):
        direction = m.group(1)
        width = m.group(2)
        name = m.group(3)
        ports.append(PortInfo(name, direction.lower(), width))

    return ports


def parse_rtl_directory(rtl_dir):
    files = find_verilog_files(rtl_dir)
    all_modules = []
    for f in files:
        mods = parse_verilog_file(f)
        all_modules.extend(mods)
    return all_modules
