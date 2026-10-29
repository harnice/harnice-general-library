import csv
import math
import xlwt
import os
from harnice import fileio
from harnice.lists import instances_list
from harnice.utils import appearance, circuit_utils, svg_utils

artifact_mpn = "wirelist_exporter"

#arguments:
#input_instances

# ============== SETUP VARIABLES ===============================================
LENGTH_SIGNIFICANT_FIGURES = 3

# =============== PATHS ===============
def macro_file_structure():
    return {
        f"{artifact_id}-wirelist.csv": "wirelist no formats",
        f"{artifact_id}-wirelist.xls": "wirelist pretty",
        f"{artifact_id}-wirelist-master.svg": "wirelist svg",
        "instance_data": {},
    }


# this runs automatically and is used to assign a default base directory if it is not called by the caller.
if base_directory == None:  # path between cwd and the file structure for this macro
    base_directory = os.path.join("instance_data", "macro", artifact_id)

# call this in your script to get the path to a file in this macro. it references logic from fileio but passes in the structure from this macro. 
def path(target_value):
    return fileio.path(
        target_value,
        structure_dict=macro_file_structure(),
        base_directory=base_directory,
        #
    )


def dirpath(target_value):
    # target_value = None will return the root of this macro
    return fileio.dirpath(
        target_value,
        structure_dict=macro_file_structure(),
        base_directory=base_directory,
    )

# =============== WIRELIST COLUMNS ===============
WIRELIST_COLUMNS = [
    {"name": "circuit_id", "printed": "Circuit ID"},
    {"name": "Length", "printed": "Length"},
    {"name": "Cable", "printed": "Cable ID"},
    {"name": "conductor_identifier", "printed": "Conductor"},
    {"name": "From_connector", "printed": "From Connector"},
    {"name": "From_connector_cavity", "printed": "From Cavity"},
    {"name": "To_connector", "printed": "To Connector"},
    {"name": "To_connector_cavity", "printed": "To Cavity"},
]

layout_dict = {
    "origin_corner": "top-left",
    "build_direction": "down",
}

format_dict = {
    "globals": {
        "font_size": 8,
        "font_family": "Arial",
        "row_height": 12,
        "stroke_color": "black",
        "stroke_width": 1,
    },
    "header": {
        "font_weight": "B",
    },
}


def _ensure_row_format(appearance_val):
    """Build a style dict from this conductor's appearance and register it on format_dict."""
    parsed = appearance.parse(appearance_val) or {}
    colors = []
    if parsed.get("base_color"):
        colors.append(parsed["base_color"])
    for key in ("parallelstripe", "perpstripe"):
        stripes = parsed.get(key) or []
        if isinstance(stripes, str):
            stripes = [stripes]
        colors.extend(c for c in stripes if c)
    if not colors:
        fill = parsed.get("outline_color")
        if not fill:
            return None
    else:
        rgbs = [appearance.to_rgb(c) for c in colors]
        avg = tuple(round(sum(ch) / len(rgbs)) for ch in zip(*rgbs))
        fill = "#{:02x}{:02x}{:02x}".format(*avg)
    if fill not in format_dict:
        format_dict[fill] = {
            "fill_color": fill,
            "stroke_color": parsed.get("outline_color") or "#000000",
            "text_color": appearance.black_or_white_to_contrast_with_color(fill),
        }
    return fill


def _build_xlwt_row_styles(workbook):
    """Build reusable cell styles for the .xls export (xlwt writes Excel 97-2003).

    That format only has a 56-slot custom colour palette (indices 8–63), so each
    RGB is registered once and styles are cached by the same format_key used for
    SVG rows.
    """
    colour_to_idx = {}
    next_idx = 8

    def colour_idx(rgb):
        nonlocal next_idx
        if rgb not in colour_to_idx:
            if next_idx > 63:
                raise ValueError("xlwt custom colour palette full")
            workbook.set_colour_RGB(next_idx, rgb[0], rgb[1], rgb[2])
            colour_to_idx[rgb] = next_idx
            next_idx += 1
        return colour_to_idx[rgb]

    style_cache = {}

    def xf_for(format_key, *, header=False, num_format=None):
        key = (format_key, header, num_format)
        if key in style_cache:
            return style_cache[key]
        st = format_dict.get(format_key) or {}
        fill_i = colour_idx(appearance.to_rgb(st.get("fill_color") or "#ffffff"))
        text_i = colour_idx(appearance.to_rgb(st.get("text_color") or "#000000"))
        if header:
            font = f"font: bold on, colour {text_i};"
        else:
            font = f"font: colour {text_i};"
        pat = f"pattern: pattern solid, fore_colour {fill_i};"
        x = xlwt.easyxf(pat + " " + font)
        if num_format:
            x.num_format_str = num_format
        style_cache[key] = x
        return x

    return xf_for


def _format_length(value, sigfigs=LENGTH_SIGNIFICANT_FIGURES):
    """Format a length to ``sigfigs`` significant figures. Non-numeric values pass through."""
    try:
        x = float(value)
        # `:.Ng` would use scientific notation (e.g. 1500 → 1.5e+03); keep plain decimal.
        n = sigfigs - 1 - int(math.floor(math.log10(abs(x))))
        x = round(x, n)
        return f"{x:.{max(sigfigs - 1 - int(math.floor(math.log10(abs(x)))), 0)}f}"
    except (ValueError, TypeError, OverflowError):
        return value


def _excel_num_format_for_length(formatted):
    """Excel format matching the decimal places of a sig-fig length string."""
    s = str(formatted)
    if "." in s:
        return "0." + "0" * len(s.split(".", 1)[1])
    return "0"


# =============== POPULATE DATA ===============
wirelist = []

# Prefer explicit input_instances; fall back to a fresh instances list.
try:
    _input_rows = input_instances
except NameError:
    _input_rows = instances_list.read()


def _instance_named(name):
    if not name:
        return {}
    for inst in instances_list.read():
        if inst.get("instance_name") == name:
            return inst
    return {}


# Locate cavities / ends for each conductor
for instance in _input_rows:
    if instance.get("item_type") != "conductor":
        continue

    circuit_id = instance.get("circuit_id")
    cable_group = instance.get("cable_group")
    cable_identifier = instance.get("cable_identifier")
    length = _format_length(instance.get("length"))

    # Prefer harness node_at_end_*; fall back to circuit_port ends.
    zero_port_instance, max_port_instance = circuit_utils.end_ports_of_circuit(
        circuit_id
    )
    zero_port_instance = (
        _instance_named(instance.get("node_at_end_a")) or zero_port_instance
    )
    max_port_instance = (
        _instance_named(instance.get("node_at_end_b")) or max_port_instance
    )

    from_connector = zero_port_instance.get("connector_group")
    from_connector_cavity = zero_port_instance.get("print_name") or (
        str(zero_port_instance.get("instance_name") or "").rsplit(".", 1)[-1]
        if zero_port_instance.get("instance_name")
        else ""
    )
    to_connector = max_port_instance.get("connector_group")
    to_connector_cavity = max_port_instance.get("print_name") or (
        str(max_port_instance.get("instance_name") or "").rsplit(".", 1)[-1]
        if max_port_instance.get("instance_name")
        else ""
    )

    wirelist.append(
        {
            "circuit_id": circuit_id,
            "Length": length,
            "Cable": cable_group,
            "conductor_identifier": cable_identifier,
            "From_connector": from_connector,
            "From_connector_cavity": from_connector_cavity,
            "To_connector": to_connector,
            "To_connector_cavity": to_connector_cavity,
            "format_key": _ensure_row_format(instance.get("appearance")),
        }
    )

headers = [col["name"] for col in WIRELIST_COLUMNS]

# =============== WRITE TO CSV ===============
with open(path("wirelist no formats"), "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(wirelist)

# =============== WRITE TO XLS ===============
workbook = xlwt.Workbook()
sheet = workbook.add_sheet("Sheet1")
xf_for = _build_xlwt_row_styles(workbook)

length_col_idx = None
for col_idx, header in enumerate(headers):
    if header == "Length":
        length_col_idx = col_idx
    sheet.write(0, col_idx, header, xf_for("header", header=True))

for row_idx, row_dict in enumerate(wirelist, start=1):
    fmt_key = row_dict.get("format_key")
    for col_idx, header in enumerate(headers):
        cell = row_dict.get(header, "")
        if col_idx == length_col_idx:
            try:
                num_format = _excel_num_format_for_length(cell)
                sheet.write(
                    row_idx,
                    col_idx,
                    float(cell),
                    xf_for(fmt_key, num_format=num_format),
                )
            except (ValueError, TypeError):
                sheet.write(row_idx, col_idx, cell, xf_for(fmt_key))
        else:
            sheet.write(row_idx, col_idx, cell, xf_for(fmt_key))

workbook.save(path("wirelist pretty"))

# =============== WRITE TO SVG ===============
columns_list = []
for col in WIRELIST_COLUMNS:
    columns_list.append(
        {
            "name": col["name"],
            "width": 76,
            "fill_color": col.get("fill", "white"),
            "text_color": col.get("font", "black"),
        }
    )

content_list = []
header_columns = {}

# append header
for col in WIRELIST_COLUMNS:
    header_columns[col["name"]] = col["printed"]
content_list.append(
    {
        "format_key": "header",
        "columns": header_columns,
    }
)

# append data rows
for row in wirelist:
    row_columns = {}
    for col in WIRELIST_COLUMNS:
        row_columns[col["name"]] = row.get(col["name"], "")
    content_list.append({
        "columns": row_columns, 
        "format_key": row.get("format_key")
        })

svg_utils.table(
    layout_dict,
    format_dict,
    columns_list,
    content_list,
    path("wirelist svg"),
    f"{artifact_id}-wirelist",
)