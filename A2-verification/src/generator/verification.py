def generate_verification_skeleton(top_module, design_info):
    d = design_info["design"]
    clock_info = d.get("clock", {})
    reset_info = d.get("reset", {})
    interfaces = d.get("interfaces", [])

    clock_entry = None
    if clock_info and clock_info.get("name"):
        clock_entry = {
            "signal": clock_info["name"],
            "period_ns": clock_info.get("period_ns", 10),
            "duty_cycle": "50%",
            "generation": f"cocotb.fork(Clock(dut.{clock_info['name']}, {clock_info.get('period_ns', 10)}, units='ns').start())",
        }

    reset_entry = None
    if reset_info and reset_info.get("name"):
        active_val = "0" if reset_info.get("active_level") == 0 else "1"
        inactive_val = "1" if reset_info.get("active_level") == 0 else "0"
        reset_entry = {
            "signal": reset_info["name"],
            "active_value": active_val,
            "active_cycles": reset_info.get("minimum_cycles", 2) * 4,
            "post_reset_idle_cycles": 8,
            "sequence": f"dut.{reset_info['name']}.value = {active_val}; await ClockCycles(8); dut.{reset_info['name']}.value = {inactive_val}; await ClockCycles(8)",
        }

    drivers = []
    monitors = []
    for iface in interfaces:
        role = iface.get("role")
        pch = iface.get("protocol_channel", "custom")
        sig_names = [s["name"] for s in iface.get("signals", [])]

        if role == "input_driver":
            drivers.append({
                "name": f"{iface['name']}_driver",
                "interface": iface["name"],
                "protocol_channel": pch,
                "drives": sig_names,
                "sampling": "drive on falling edge, observe on rising edge" if "AXI" in pch
                           else "drive before rising edge",
            })
        elif role == "output_monitor":
            monitors.append({
                "name": f"{iface['name']}_monitor",
                "interface": iface["name"],
                "protocol_channel": pch,
                "monitors": sig_names,
                "sampling": "sample on rising edge",
            })

    skeleton = {
        "verification_skeleton": {
            "design": top_module.name,
            "clock_reset_generation": {
                "clock": clock_entry,
                "reset": reset_entry,
            },
            "input_drivers": drivers,
            "output_monitors": monitors,
            "scoreboard": {
                "type": "reference_model",
                "description": "Reference model comparing expected vs actual output",
                "checks": [
                    "All output signals verified against expected values",
                    "Protocol handshake timing validated",
                    "Response ordering matches request ordering",
                ],
                "failure_reporting": "AssertionError with signal name and expected vs actual",
            },
            "generated_files": {
                "testbench_top": f"generated_tb/{top_module.name}_cocotb_top.v",
                "testbench_py": f"generated_tb/{top_module.name}_tb.py",
                "makefile": "generated_tb/Makefile",
            },
        }
    }
    return skeleton
