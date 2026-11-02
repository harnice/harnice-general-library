import json
import os

from harnice import fileio, state
from harnice.utils import system_symbol_utils

# ARGS
# artifact_id = unique identifier for this instance of the macro
# scale = factor applied to the system block diagram primitive (default 0.1).
# This call copies the current block diagram into the system-diagram
# primitives on this symbol and updates that scale. Another run_macro
# call is another copy, with its own flags.
# The primitive stays where it was drawn. A symbol with no diagram primitive
# is left as drawn.
# Each show_* flag is one layer. True draws it. False sets display="none".
# Omitted flags are True.
#
# build_utils.run_macro(
#     "subsystem_symbol",
#     "macros/system_artifacts",
#     "https://github.com/harnice/harnice-general-library",
#     artifact_id="subsystem-symbol-1",
#     scale=0.1,
#     show_boundary=True,
#     show_devices=True,
#     show_subsystems=True,
#     show_harnesses=True,
#     show_mating_connectors=True,
#     show_external_interface_flags=True,
#     show_harness_labels=True,
#     show_channel_traces=True,
#     show_circuit_traces=True,
# )
#
# Connector pins are copied from unique connector_name values in the system ICD.
# generate_icd() runs after build instructions, so this uses the ICD from the
# previous build. After changing external-interface flags, build twice.
# Also runs device signals-list checks against that ICD. Pin mismatches vs the
# ICD print a warning and do not fail the build.

artifact_mpn = "subsystem_symbol"

if "scale" not in globals() or scale is None:
    scale = 0.1
try:
    scale = float(scale)
except (TypeError, ValueError):
    scale = 0.1

show = {"scale": scale}
for _name in system_symbol_utils.DIAGRAM_SHOW_FLAGS:
    if _name not in globals() or globals()[_name] is None:
        show[_name] = True
        continue
    _value = globals()[_name]
    if not isinstance(_value, bool):
        raise TypeError("%s must be True or False; got %r" % (_name, _value))
    show[_name] = _value


def macro_file_structure():
    return {
        "symbol.svg": "subsystem symbol",
        "params.json": "params",
    }


if base_directory is None:
    base_directory = os.path.join("instance_data", "macro", artifact_id)


def path(target_value):
    return fileio.path(
        target_value,
        structure_dict=macro_file_structure(),
        base_directory=base_directory,
    )


def dirpath(target_value):
    return fileio.dirpath(
        target_value,
        structure_dict=macro_file_structure(),
        base_directory=base_directory,
    )


os.makedirs(dirpath(None), exist_ok=True)

params_path = path("params")
with open(params_path, "w", encoding="utf-8") as f:
    json.dump(show, f, indent=2)
    f.write("\n")

symbol_path = path("subsystem symbol")
if not os.path.exists(symbol_path) or os.path.getsize(symbol_path) == 0:
    pn_rev = state.partnumber("pn-rev")
    contents_id = f"{pn_rev}-{artifact_id}-contents-start"
    contents_end = f"{pn_rev}-{artifact_id}-contents-end"
    svg_text = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <g id="{contents_id}" class="component device"></g>
  <g id="{contents_end}"></g>
</svg>
'''
    with open(symbol_path, "w", encoding="utf-8") as f:
        f.write(svg_text)

# Uses the ICD already on disk (from the previous build). See comment above.
system_symbol_utils.verify_as_device(artifact_id)
