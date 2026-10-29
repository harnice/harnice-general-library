import math
import os
import re

from harnice import fileio
from harnice.utils import pdf_drawings_utils, system_utils

# ARGS
# artifact_id = unique instance name. The file is {artifact_id}-master.svg.
# scale = drawing scale baked into the master. 1 is the block diagram size.
# The show_* arguments are the old block-diagram sheet checkboxes.
# True leaves that layer visible. False sets display="none".
#
# build_utils.run_macro(
#     "block-diagram-svg-exporter",
#     "library/macros/system_artifacts",
#     "https://github.com/harnice/harnice-general-library",
#     artifact_id="block-diagram-1",
#     scale=1,
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

artifact_mpn = "block-diagram-svg-exporter"

_SHOW_FLAGS = (
    "show_boundary",
    "show_devices",
    "show_subsystems",
    "show_harnesses",
    "show_mating_connectors",
    "show_external_interface_flags",
    "show_harness_labels",
    "show_channel_traces",
    "show_circuit_traces",
)


def macro_file_structure():
    return {
        f"{artifact_id}-master.svg": "output svg",
    }


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


def export_block_diagram_master_svg(svg_text, master_name, scale, show):
    """Block-diagram markup as a normal ``{master_name}-master.svg`` document."""

    def element_bounds(text, element_id):
        """Open-tag end and matching close start for ``id``, or None."""
        needle = f'id="{element_id}"'
        attr_i = text.find(needle)
        if attr_i < 0:
            return None
        start = text.rfind("<", 0, attr_i)
        if start < 0:
            return None
        name_m = re.match(r"<([A-Za-z_][\w:.-]*)", text[start:])
        if not name_m:
            return None
        tag = name_m.group(1)
        gt = text.find(">", start)
        if gt < 0:
            return None
        open_tag = text[start : gt + 1]
        if open_tag.rstrip().endswith("/>"):
            return (gt + 1, gt + 1, tag)
        open_re = re.compile(rf"<{re.escape(tag)}\b", re.IGNORECASE)
        close_re = re.compile(rf"</{re.escape(tag)}\s*>", re.IGNORECASE)
        depth = 0
        pos = start
        while pos < len(text):
            om = open_re.search(text, pos)
            cm = close_re.search(text, pos)
            if cm is None:
                return None
            if om is not None and om.start() < cm.start():
                ogt = text.find(">", om.start())
                if ogt >= 0 and text[om.start() : ogt + 1].rstrip().endswith("/>"):
                    pos = ogt + 1
                    continue
                depth += 1
                pos = om.end()
                continue
            depth -= 1
            if depth == 0:
                return (gt + 1, cm.start(), tag)
            pos = cm.end()
        return None

    def hide_by_id(text, element_id):
        needle = f'id="{element_id}"'
        attr_i = text.find(needle)
        if attr_i < 0:
            return text
        start = text.rfind("<", 0, attr_i)
        gt = text.find(">", start)
        if start < 0 or gt < 0:
            return text
        tag = text[start : gt + 1]
        if re.search(r"\bdisplay\s*=", tag):
            tag = re.sub(
                r'\bdisplay\s*=\s*"[^"]*"', 'display="none"', tag, count=1
            )
        else:
            tag = tag[:-1] + ' display="none">'
        return text[:start] + tag + text[gt + 1 :]

    def hide_placed(text, show_devices, show_subsystems):
        if show_devices and show_subsystems:
            return text
        bounds = element_bounds(text, "devices")
        if bounds is None:
            return text
        inner_start, inner_end, _tag = bounds
        ids = []
        depth = 0
        pos = inner_start
        token_re = re.compile(r"</?g\b[^>]*>", re.IGNORECASE)
        while pos < inner_end:
            match = token_re.search(text, pos, inner_end)
            if match is None:
                break
            token = match.group(0)
            if token.startswith("</"):
                depth -= 1
                pos = match.end()
                continue
            if depth == 0 and not token.rstrip().endswith("/>"):
                class_m = re.search(r'\bclass="([^"]*)"', token)
                classes = set((class_m.group(1) if class_m else "").split())
                if "subsystem" in classes:
                    kind = "subsystem"
                elif "device" in classes:
                    kind = "device"
                else:
                    kind = ""
                id_m = re.search(r'\bid="([^"]*)"', token)
                if kind == "device" and not show_devices and id_m:
                    ids.append(id_m.group(1))
                elif kind == "subsystem" and not show_subsystems and id_m:
                    ids.append(id_m.group(1))
            if not token.rstrip().endswith("/>"):
                depth += 1
            pos = match.end()
        for placed_id in ids:
            text = hide_by_id(text, placed_id)
        return text

    def contents_name(text):
        match = re.search(r'id="([^"]+)-contents-start"', text)
        if not match:
            raise ValueError("Block diagram has no contents-start group")
        return match.group(1)

    def root_open_tag(text):
        match = re.search(r"<svg\b[^>]*>", text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return '<svg xmlns="http://www.w3.org/2000/svg">'
        return match.group(0)

    if not isinstance(scale, (int, float)) or isinstance(scale, bool):
        raise TypeError(f"scale must be a number; got {scale!r}")
    scale = float(scale)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("scale must be a positive number")

    text = pdf_drawings_utils.strip_configuration_elements(svg_text)
    group_ids = (
        ("boundary", show["show_boundary"]),
        ("harnesses", show["show_harnesses"]),
        ("mating-connectors", show["show_mating_connectors"]),
        ("external-interface-flags", show["show_external_interface_flags"]),
        ("harness-segment-refdes-labels", show["show_harness_labels"]),
        ("channel_traces", show["show_channel_traces"]),
        ("circuit_traces", show["show_circuit_traces"]),
    )
    for element_id, visible in group_ids:
        if not visible:
            text = hide_by_id(text, element_id)
    text = hide_placed(text, show["show_devices"], show["show_subsystems"])

    source_name = contents_name(text)
    bounds = element_bounds(text, f"{source_name}-contents-start")
    if bounds is None:
        raise ValueError("Block diagram contents-start group was not found")
    inner_start, inner_end, _tag = bounds
    inner = text[inner_start:inner_end]
    trace_bounds = element_bounds(text, "applied-traces")
    traces = ""
    if trace_bounds is not None:
        trace_open = text.rfind("<", 0, trace_bounds[0])
        trace_close = text.find(">", trace_bounds[1])
        if trace_open >= 0 and trace_close >= 0:
            if not (inner_start <= trace_open and trace_close <= inner_end):
                traces = text[trace_open : trace_close + 1]

    scale_text = str(int(scale)) if scale == int(scale) else format(scale, "g")
    body = inner
    if traces:
        body += "\n" + traces
    body = f'<g transform="scale({scale_text})">\n{body}\n</g>'
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + root_open_tag(text)
        + "\n"
        + f'  <g id="{master_name}-contents-start">\n'
        + body
        + "\n"
        + "  </g>\n"
        + f'  <g id="{master_name}-contents-end"></g>\n'
        + "</svg>\n"
    )


def _flag(name):
    if name not in globals() or globals()[name] is None:
        return True
    value = globals()[name]
    if isinstance(value, bool):
        return value
    raise TypeError(f"{name} must be True or False; got {value!r}")


if __name__ == "__main__":
    if "base_directory" not in globals() or base_directory is None:
        base_directory = os.path.join("instance_data", "macro", artifact_id)
    if "scale" not in globals() or scale is None:
        scale = 1

    os.makedirs(dirpath(None), exist_ok=True)

    diagram_path = fileio.path("block diagram")
    if not diagram_path or not os.path.isfile(diagram_path):
        raise FileNotFoundError("Block diagram not found")
    with open(diagram_path, encoding="utf-8") as handle:
        diagram_text = handle.read()
    try:
        diagram_text = system_utils.apply_block_diagram_trace_overlays(diagram_text)
    except ValueError as exc:
        if "No harness wire segments" not in str(exc):
            raise

    show = {name: _flag(name) for name in _SHOW_FLAGS}
    master_svg = export_block_diagram_master_svg(
        diagram_text, artifact_id, scale, show
    )
    with open(path("output svg"), "w", encoding="utf-8") as handle:
        handle.write(master_svg)
