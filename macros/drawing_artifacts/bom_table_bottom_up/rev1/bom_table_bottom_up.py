import os
import csv
from harnice import fileio, state
from harnice.lists import instances_list
from harnice.utils import svg_utils

artifact_mpn = "bom_table_bottom_up"

# Writes a bill of materials table: {artifact_id}.tsv and {artifact_id}-master.svg.
# Works in any project type. Reads the instances list and groups every instance
# that has a bom_line_number by that number. Assign the numbers first with
# instances_list.assign_bom_line_numbers().
#
# Each BOM line gets a total row: item bubble, QTY, MFG, MPN. Disclosed
# instance rows under it are italic. Only the header row is bold.
#
# Optional kwargs:
#   per_instance_disclosure  (default {})  {instance_name: {column header: value}}
#       - Each header becomes a table column.
#       - An instance gets its own arrow row under its BOM line only when at
#         least one of its values is not blank. Instances not in the dict get
#         no arrow row.
#       - The total row shows the sum of a column when every value in that
#         column on that line is a number. Otherwise the total stays blank.
#       Example, built in build.py before the call:
#           bom_disclosure = {}
#           for instance in instances_list.read():
#               if instance.get("item_type") == "cable" and instance.get("length"):
#                   bom_disclosure[instance.get("instance_name")] = {
#                       "Length with margin": float(instance.get("length")) + 12,
#                   }

# ============== SETUP VARIABLES ===============================================
per_instance_disclosure = globals().get("per_instance_disclosure") or {}

# Shapes drawn straight into the table SVG. They live here instead of the
# library or instance_data so this macro is self-contained.
# Numbered bubble in the ITEM cell of each total row. ITEM_NUMBER is replaced per row.
BUBBLE_SVG = """
    <circle cx="0" cy="0" r="8.5" fill="#FFFFFF" stroke="#000000"/>
    <text x="0" y="0" style="font-size:8px;font-family:Arial" text-anchor="middle" dominant-baseline="middle">ITEM_NUMBER</text>
  """

# Arrow in the ITEM cell of each disclosed instance row.
ARROW_SVG = """
    <path d="M -4 -5 V 1 H 3" fill="none" stroke="#000000" stroke-width="1"/>
    <polygon points="7,1 3,-2 3,4" fill="#000000" stroke="none"/>
  """


# =============== PATHS ===================================================================================
def macro_file_structure():
    return {
        f"{artifact_id}.tsv": "bom tsv",
        f"{artifact_id}-master.svg": "bom svg",
    }


if base_directory is None:  # path between cwd and the file structure for this macro
    base_directory = os.path.join("instance_data", "macro", artifact_id)


def path(target_value):
    return fileio.path(
        target_value,
        structure_dict=macro_file_structure(),
        base_directory=base_directory,
    )


# ================= GROUP INSTANCES BY BOM LINE ======================================================
bom_lines = {}  # line number -> list of instances
for instance in instances_list.read():
    line_number = str(instance.get("bom_line_number") or "").strip()
    if not line_number:
        continue
    if not line_number.isdigit():
        raise ValueError(
            f"Instance {instance.get('instance_name')} has bom_line_number "
            f"'{line_number}'. Call instances_list.assign_bom_line_numbers() "
            "before this macro."
        )
    bom_lines.setdefault(int(line_number), []).append(instance)

if not bom_lines:
    raise ValueError(
        "bom_table_bottom_up found no instances with a bom_line_number. Mark the "
        "instances that belong on the BOM, then call "
        "instances_list.assign_bom_line_numbers() before this macro."
    )

# ================= DISCLOSE INSTANCES ===============================================================
disclosure_columns = []  # headers, in the order they first appear
disclosed = {}  # line number -> list of (instance, {header: display text})
for line_number in sorted(bom_lines):
    disclosed[line_number] = []
    for instance in bom_lines[line_number]:
        values = per_instance_disclosure.get(instance.get("instance_name")) or {}
        texts = {}
        for header, value in values.items():
            if value is None:
                value = ""
            if isinstance(value, float):
                value = round(value, 2)
            texts[header] = str(value).strip()
        if not any(texts.values()):
            continue
        for header in texts:
            if header not in disclosure_columns:
                disclosure_columns.append(header)
        disclosed[line_number].append((instance, texts))

# ================= BUILD ROWS ========================================================================
bom_table_contents = []
bom_tsv = []
bubbles_to_build = []  # (bubble instance name, item number)
arrows_to_build = []
show_instance_column = any(disclosed[line_number] for line_number in disclosed)

for line_number in sorted(bom_lines):
    instances = bom_lines[line_number]
    first = instances[0]
    bubble_instance_name = f"bom_table_item-{line_number}-bubble"

    # Sum each disclosure column when every disclosed value on this line is a number.
    totals = {}
    for header in disclosure_columns:
        total = 0
        for instance, texts in disclosed[line_number]:
            try:
                total += float(texts.get(header, ""))
            except ValueError:
                total = None
                break
        if total is not None and disclosed[line_number]:
            totals[header] = str(round(total, 2))
        else:
            totals[header] = ""

    total_columns = {
        "bom_line_number": {
            "instance_name": bubble_instance_name,
            "item_type": "flagnote",
        },
        "qty": len(instances),
        "mfg": first.get("mfg", ""),
        "mpn": first.get("mpn", ""),
    }
    tsv_row = {
        "part_of_part_number": state.partnumber("pn"),
        "bom_line_number": line_number,
        "row_type": "line",
        "instance_name": "",
        "mfg": first.get("mfg", ""),
        "mpn": first.get("mpn", ""),
        "item_type": first.get("item_type", ""),
        "qty": len(instances),
        "lib_repo": first.get("lib_repo", ""),
        "lib_subpath": first.get("lib_subpath", ""),
    }
    for n, header in enumerate(disclosure_columns):
        total_columns[f"disclosure_{n}"] = totals[header]
        tsv_row[header] = totals[header]
    bom_table_contents.append({"columns": total_columns})
    bom_tsv.append(tsv_row)
    bubbles_to_build.append((bubble_instance_name, line_number))

    # one arrow row per disclosed instance
    for instance, texts in disclosed[line_number]:
        arrow_instance_name = f"bom_table_item-{instance.get('instance_name')}-arrow"
        instance_columns = {
            "bom_line_number": {
                "instance_name": arrow_instance_name,
                "item_type": "flagnote",
            },
            "instance_name": instance.get("instance_name"),
        }
        tsv_row = {
            "part_of_part_number": state.partnumber("pn"),
            "bom_line_number": line_number,
            "row_type": "instance",
            "instance_name": instance.get("instance_name"),
            "mfg": instance.get("mfg", ""),
            "mpn": instance.get("mpn", ""),
            "item_type": instance.get("item_type", ""),
            "qty": 1,
            "lib_repo": instance.get("lib_repo", ""),
            "lib_subpath": instance.get("lib_subpath", ""),
        }
        for n, header in enumerate(disclosure_columns):
            instance_columns[f"disclosure_{n}"] = texts.get(header, "")
            tsv_row[header] = texts.get(header, "")
        bom_table_contents.append({"format_key": "disclosure_line", "columns": instance_columns})
        bom_tsv.append(tsv_row)
        arrows_to_build.append(arrow_instance_name)

# ============= BUILD TABLE ===========================================================
layout_dict = {
    "origin_corner": "bottom-right",
    "build_direction": "up",
}

format_dict = {
    "globals": {
        "font_size": 8,
        "font_family": "Arial, Helvetica, sans-serif",
        # 0.2 in rows leave about 1 px above and below the 17 px item bubble.
        "row_height": 0.2 * 96,
    },
    "header": {
        "font_weight": "B",
        "fill_color": "lightgray",
    },
    "disclosure_line": {
        "font_weight": "I",
    },
}

columns_list = [
    {"name": "bom_line_number", "width": 0.375 * 96},
    {"name": "qty", "width": 0.375 * 96},
    {"name": "mfg", "width": 1.0 * 96, "justify": "left"},
    {"name": "mpn", "width": 1.75 * 96, "justify": "left"},
]
header_columns = {
    "bom_line_number": "ITEM",
    "qty": "QTY",
    "mfg": "MFG",
    "mpn": "MPN",
}
if show_instance_column:
    columns_list.append({"name": "instance_name", "width": 1.0 * 96, "justify": "left"})
    header_columns["instance_name"] = "INSTANCE"
for n, header in enumerate(disclosure_columns):
    columns_list.append({"name": f"disclosure_{n}", "width": 1.0 * 96})
    header_columns[f"disclosure_{n}"] = header

# append header row at the end because we want it on the bottom of the table
bom_table_contents.append({"format_key": "header", "columns": header_columns})

svg_utils.table(
    layout_dict,
    format_dict,
    columns_list,
    bom_table_contents,
    path("bom svg"),
    artifact_id,
)

# ============= WRITE TSV FILE =======================================================================
tsv_columns = list(bom_tsv[0].keys())
with open(path("bom tsv"), "w", newline="", encoding="utf-8") as tsv_file:
    writer = csv.DictWriter(tsv_file, fieldnames=tsv_columns, delimiter="\t")
    writer.writeheader()
    writer.writerows(bom_tsv)

# ============= ADD SYMBOLS TO TABLE =======================================================================
# The table leaves an empty {name}-contents-start group in each ITEM cell that
# holds a symbol. Fill each one with its shapes.
symbols = [
    (bubble_instance_name, BUBBLE_SVG.replace("ITEM_NUMBER", str(item_number)))
    for bubble_instance_name, item_number in bubbles_to_build
]
symbols += [(arrow_instance_name, ARROW_SVG) for arrow_instance_name in arrows_to_build]

with open(path("bom svg"), "r", encoding="utf-8") as f:
    svg_content = f.read()

for group_name, shapes in symbols:
    start_tag = svg_content.find(f'id="{group_name}-contents-start"')
    start = svg_content.find(">", start_tag) + 1
    end = svg_content.rfind("<", 0, svg_content.find(f'id="{group_name}-contents-end"'))
    # Replace everything between the start tag and the end group, including
    # the start group's closing tag, so close it again after the shapes.
    svg_content = svg_content[:start] + shapes + "</g>\n  " + svg_content[end:]

with open(path("bom svg"), "w", encoding="utf-8") as f:
    f.write(svg_content)
