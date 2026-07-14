import os
import re
import json


def find_verilog_files(rtl_dir):
    files = []
    for root, dirs, names in os.walk(rtl_dir):
        for n in names:
            if n.endswith(".v") or n.endswith(".sv") or n.endswith(".vh"):
                files.append(os.path.join(root, n))
    return files


def read_file(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def deduplicate(items):
    seen = set()
    result = []
    for i in items:
        if i not in seen:
            seen.add(i)
            result.append(i)
    return result


RESET_FALSE_POSITIVES = ["burst", "first", "thrust", "worst", "trust"]


def is_clock(name):
    low = name.lower()
    return "clk" in low or "clock" in low


def is_reset(name):
    low = name.lower()
    for fp in RESET_FALSE_POSITIVES:
        if fp in low:
            return False
    return "rst" in low or "reset" in low


def find_top_module(all_modules):
    """
    Find the module that is NOT instantiated by any other module.
    This is the true top-level module.
    """
    if not all_modules:
        return None
    if len(all_modules) == 1:
        return all_modules[0]

    module_names = {m.name for m in all_modules}
    instantiated = set()

    for m in all_modules:
        try:
            content = read_file(m.file_path)
            for name in module_names:
                if name == m.name:
                    continue
                # Match: module_name #(...) instance_name (   or  module_name instance_name (
                pat = r"\b" + re.escape(name) + r"\s+(?:#\s*\([\s\S]*?\)\s*)?\w+\s*\("
                if re.search(pat, content):
                    instantiated.add(name)
        except Exception:
            continue

    for m in all_modules:
        if m.name not in instantiated:
            return m

    return all_modules[0]
