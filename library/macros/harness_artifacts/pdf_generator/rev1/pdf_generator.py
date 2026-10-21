import os
import json
import re
import subprocess
import sys
from pypdf import PdfWriter

from harnice import fileio, state
from harnice.utils import svg_utils, library_utils, pdf_drawings_utils

# ARGS
# artifact_id = "unique identifier for this instance of the macro (drawing-1)"
# page_setup = {"pages": [{"tblock_mpn": "harnice_tblock", "text_replacements": {"tblock-key-pagedesc": "overview", "tblock-key-pn": state.partnumber("pn"), "tblock-key-scale": scales.get("A"), ...}, ...}, ...]}

artifact_mpn = "pdf_generator"

_INKSCAPE_DEFAULT = "/Applications/Inkscape.app/Contents/MacOS/inkscape"
# Inkscape/GLib noise: CSS props it recognizes by id but does not implement (e.g. cursor=400).
_INKSCAPE_STDERR_IGNORE_SUBSTRINGS = (
    "Unimplemented style property",
    "unknown type: svg:configuration",
)


def _inkscape_bin():
    """Resolve Inkscape from paths/paths.json, else paths.example.json, else default."""
    paths_dir = os.path.join(fileio.harnice_root(), "paths")
    for name in ("paths.json", "paths.example.json"):
        p = os.path.join(paths_dir, name)
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("inkscape"):
                return data["inkscape"]
        except (json.JSONDecodeError, OSError):
            pass
    return _INKSCAPE_DEFAULT


def _run_inkscape(args, *, check=True):
    """Run Inkscape, filtering known-harmless stderr warnings."""
    result = subprocess.run([_inkscape_bin(), *args], capture_output=True, text=True)
    if result.stderr:
        kept = [
            line
            for line in result.stderr.splitlines()
            if line.strip()
            and not any(s in line for s in _INKSCAPE_STDERR_IGNORE_SUBSTRINGS)
        ]
        if kept:
            print("\n".join(kept), file=sys.stderr)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, result.args, result.stdout, result.stderr
        )
    return result


# =============== PATHS ===================================================================================
def macro_file_structure(page_name=None, page_counter=None):
    return {
        f"{artifact_id}-mastercontents.svg": "master contents svg",
        f"{artifact_id}.pdf": "output pdf",
        "page_svgs": {
            f"{page_counter}-{page_name}-user-editable.svg": "user editable page svg"
        },
    }


if base_directory is None:  # path between cwd and the file structure for this macro
    base_directory = os.path.join("instance_data", "macro", artifact_id)


def path(target_value, page_name=None, page_counter=None):
    return fileio.path(
        target_value,
        structure_dict=macro_file_structure(page_name, page_counter),
        base_directory=base_directory,
    )


def dirpath(target_value, page_name=None, page_counter=None):
    # target_value = None will return the root of this macro
    return fileio.dirpath(
        target_value,
        structure_dict=macro_file_structure(page_name, page_counter),
        base_directory=base_directory,
    )


os.makedirs(
    dirpath("page_svgs"),
    exist_ok=True,
)
# ==========================================================================================================


# ==========================================================================================================
#              PAGE SETUP (from run_macro page_setup= arg)
# ==========================================================================================================

page_data = globals().get("page_setup")
if not isinstance(page_data, dict):
    page_data = pdf_drawings_utils.default_page_setup()
page_data = pdf_drawings_utils.normalize_page_setup(page_data)

page_names = [pdf_drawings_utils.page_name(p) for p in page_data.get("pages", [])]
duplicates = {name for name in page_names if page_names.count(name) > 1}
if duplicates:
    raise ValueError(f"Duplicate page name(s) found: {', '.join(duplicates)}")


# HOW TO QUERY PAGE SETUP DATA

# page_data.get('pages', [])
# → returns the list of all pages (and their content as dict of top level list)

# page_names = [pdf_drawings_utils.page_name(p) for p in page_data.get("pages", [])]
# → returns a list of all page names (from text_replacements["tblock-key-pagedesc"])

# page_data.get('pages', [])[n]
# → returns the nth page (0-indexed) and all of its content

# pdf_drawings_utils.page_name(page_data.get('pages', [])[n])
# → returns the name of the nth page

# next(page for page in page_data.get('pages', []) if pdf_drawings_utils.page_name(page) == "x")
# → returns the full page dictionary whose pagedesc equals "x"

# ==========================================================================================================
#            PREP MASTER SVG
# searches the entire rev directory for anything that ends in -master.svg and adds it to this file
# ==========================================================================================================
masters_translate = [0, -960000]  # 10000 in at 96 dpi, off-page in -y
masters = []

# Discover all master SVGs in a folder of the entire project (output of the other macros).
# Only import when the SVG contains a group whose id matches the filename stem:
#   {master_name}-master.svg  →  requires id="{master_name}-contents-start"
directory_to_search = fileio.dirpath(None)

for root, _, files in os.walk(directory_to_search):
    for filename in files:
        if not filename.endswith("-master.svg"):
            continue
        if filename.endswith("-mastercontents.svg") or filename.endswith(
            "mastercontents.svg"
        ):
            continue

        master_name = filename[: -len("-master.svg")]
        if not master_name:
            continue

        source_svg_path = os.path.join(root, filename)
        try:
            with open(source_svg_path, "r", encoding="utf-8") as f:
                source_text = f.read()
        except OSError:
            continue
        # Group id must match the filename-derived master name.
        if f'id="{master_name}-contents-start"' not in source_text:
            continue

        masters.append((master_name, source_svg_path))

extra_master_names = set()
for extra in pdf_drawings_utils.extra_project_masters():
    extra_master_names.add(extra["name"])
    if extra["name"] not in {name for name, _ in masters}:
        masters.append((extra["name"], extra["path"]))

masters.sort(key=lambda x: x[0])  # sort alphabetically by master_name

# write the svg structure
svg = [
    '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
    (
        '<svg xmlns="http://www.w3.org/2000/svg"'
        ' xmlns:schem="https://example.com/schema/v1" version="1.1">'
    ),
    '  <g id="svg-master-contents-start">',
]

for master_name, _ in masters:
    translate_str = f"translate({masters_translate[0]},{masters_translate[1]})"
    svg += [
        f'    <g id="{master_name}" transform="{translate_str}">',
        f'      <g id="{master_name}-contents-start"></g>',
        f'      <g id="{master_name}-contents-end"></g>',
        f"    </g>",
    ]

svg += [
    "  </g>",  # Close svg-master-contents-start
    '  <g id="svg-master-contents-end"></g>',
    "</svg>",
]

with open(path("master contents svg"), "w", encoding="utf-8") as f:
    f.write("\n".join(svg))

# fetch content from each -master.svg into the master contents svg
for master_name, source_svg_path in masters:
    if master_name in extra_master_names:
        pdf_drawings_utils.copy_svg_inner_into_group(
            source_svg_path, path("master contents svg"), master_name
        )
        continue
    svg_utils.find_and_replace_svg_group(
        source_svg_path, master_name, path("master contents svg"), master_name
    )

# ==========================================================================================================
#             PAGE FRAME (parametric border + zone marks)
# ==========================================================================================================
def build_page_frame_markup(
    page_w,
    page_h,
    outer_margin=20,
    inner_margin=40,
    tick_spacing=96,
    tblock_h=48,
):
    """Return SVG markup for the sheet frame (borders + zone marks).

    Zone ticks are drawn first; the inner drawing rect is drawn last with an
    opaque white fill so it covers ticks inside the usable area (same as the
    original titleblock layout).
    """
    ox = outer_margin
    oy = outer_margin
    ow = page_w - 2 * outer_margin
    oh = page_h - 2 * outer_margin
    ix = inner_margin
    iy = inner_margin
    iw = page_w - 2 * inner_margin
    ih = page_h - 2 * inner_margin

    lines = [
        # Outer sheet border (no fill)
        f'<rect id="page-outer-border" x="{ox}" y="{oy}" width="{ow}" height="{oh}" '
        f'fill="none" stroke="black" stroke-width="1"/>',
    ]

    # Vertical zones (numbers) across the inner width
    n_cols = max(1, int(iw // tick_spacing))
    for i in range(n_cols):
        x0 = ix + i * tick_spacing
        x1 = ix + (i + 1) * tick_spacing if i < n_cols - 1 else ix + iw
        cx = (x0 + x1) / 2.0
        label = str(i + 1)
        lines.append(
            f'<text x="{cx}" y="{oy + 10}" style="font-size:8px;font-family:Arial" '
            f'text-anchor="middle">{label}</text>'
        )
        lines.append(
            f'<text x="{cx}" y="{oy + oh - 6}" style="font-size:8px;font-family:Arial" '
            f'text-anchor="middle">{label}</text>'
        )
        if i < n_cols - 1:
            tx = ix + (i + 1) * tick_spacing
            lines.append(
                f'<line x1="{tx}" y1="{oy}" x2="{tx}" y2="{oy + oh}" '
                f'stroke="black" stroke-width="0.5"/>'
            )

    # Horizontal zones (letters) — leave bottom strip for titleblock
    usable_h = max(tick_spacing, ih - tblock_h)
    n_rows = max(1, int(usable_h // tick_spacing))
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i in range(n_rows):
        y0 = iy + i * tick_spacing
        y1 = iy + (i + 1) * tick_spacing if i < n_rows - 1 else iy + usable_h
        cy = (y0 + y1) / 2.0
        label = letters[i] if i < len(letters) else str(i + 1)
        lines.append(
            f'<text x="{ox + 10}" y="{cy + 3}" style="font-size:8px;font-family:Arial" '
            f'text-anchor="middle">{label}</text>'
        )
        lines.append(
            f'<text x="{ox + ow - 10}" y="{cy + 3}" style="font-size:8px;font-family:Arial" '
            f'text-anchor="middle">{label}</text>'
        )
        if i < n_rows - 1:
            ty = iy + (i + 1) * tick_spacing
            lines.append(
                f'<line x1="{ox}" y1="{ty}" x2="{ox + ow}" y2="{ty}" '
                f'stroke="black" stroke-width="0.5"/>'
            )

    # Inner drawing area — opaque white, on top so ticks only show in the margin ring
    lines.append(
        f'<rect id="page-drawing-area" x="{ix}" y="{iy}" width="{iw}" height="{ih}" '
        f'fill="#ffffff" fill-opacity="1" stroke="black" stroke-width="1"/>'
    )

    return "\n".join(f"      {line}" for line in lines)


def ensure_page_svg_scaffold(svg_path, page_w, page_h):
    """Create or upgrade a user-editable page SVG with frame/tblock/master groups."""
    scaffold = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg"
    xmlns:schem="https://example.com/schema/v1"
    xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
    version="1.1"
    width="{page_w}"
    height="{page_h}">
    <g id="page-frame-contents-start">
    </g>
    <g id="page-frame-contents-end"></g>
    <g id="tblock-contents-start">
    </g>
    <g id="tblock-contents-end"></g>
    <g id="svg-master-contents-start">
    </g>
    <g id="svg-master-contents-end"></g>
</svg>
"""
    if not os.path.exists(svg_path):
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(scaffold)
        return

    with open(svg_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = pdf_drawings_utils.ensure_attr_on_root_svg(
        content, "xmlns:schem", "https://example.com/schema/v1"
    )

    # Keep existing clone content; ensure markers + size attributes exist.
    content = re.sub(
        r'(<svg\b[^>]*?)\bwidth="[^"]*"',
        rf'\1width="{page_w}"',
        content,
        count=1,
    )
    content = re.sub(
        r'(<svg\b[^>]*?)\bheight="[^"]*"',
        rf'\1height="{page_h}"',
        content,
        count=1,
    )
    if 'id="page-frame-contents-start"' not in content:
        # Insert frame markers before tblock if present, else after <svg>
        if 'id="tblock-contents-start"' in content:
            content = content.replace(
                '<g id="tblock-contents-start"',
                '<g id="page-frame-contents-start">\n    </g>\n'
                '    <g id="page-frame-contents-end"></g>\n'
                '    <g id="tblock-contents-start"',
                1,
            )
        else:
            content = re.sub(
                r"(<svg[^>]*>)",
                r'\1\n    <g id="page-frame-contents-start">\n    </g>\n'
                r'    <g id="page-frame-contents-end"></g>',
                content,
                count=1,
            )
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(content)


def write_frame_source_svg(frame_path, page_w, page_h, tblock_h):
    markup = build_page_frame_markup(page_w, page_h, tblock_h=tblock_h)
    with open(frame_path, "w", encoding="utf-8") as f:
        f.write(
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1">\n'
            '  <g id="page-frame-contents-start">\n'
            f"{markup}\n"
            "  </g>\n"
            '  <g id="page-frame-contents-end"></g>\n'
            "</svg>\n"
        )


def wrap_tblock_with_translate(tblock_svg_path, tx, ty):
    """Wrap tblock contents in a translate so the local (0,0) sits at (tx, ty).

    Titleblock artwork uses a bottom-right local origin (extends -x / -y).
    """
    with open(tblock_svg_path, "r", encoding="utf-8") as f:
        content = f.read()
    start = 'id="tblock-contents-start"'
    end = 'id="tblock-contents-end"'
    si = content.find(start)
    ei = content.find(end)
    if si < 0 or ei < 0:
        raise ValueError("tblock contents markers missing after pull")
    # Find '>' of start group tag
    start_gt = content.find(">", si)
    end_tag_lt = content.rfind("<", 0, ei)
    inner = content[start_gt + 1 : end_tag_lt]
    # Avoid double-wrapping on rebuilds of the imported file (fresh pull each time)
    wrapped = (
        f'\n    <g id="tblock-placement" transform="translate({tx},{ty})">\n'
        f"{inner}\n"
        "    </g>\n  "
    )
    content = content[: start_gt + 1] + wrapped + content[end_tag_lt:]
    with open(tblock_svg_path, "w", encoding="utf-8") as f:
        f.write(content)


def tblock_origin_on_page(page_w, page_h, tblock_w, tblock_h, anchor, offset_xy):
    """Page-space translate for a tblock whose local origin is its bottom-right."""
    ox, oy = float(offset_xy[0]), float(offset_xy[1])
    w, h = float(tblock_w), float(tblock_h)
    anchor = (anchor or "bottom-right").strip().lower().replace("_", "-")
    if anchor == "top-left":
        return (ox + w, oy + h)
    if anchor == "top-right":
        return (page_w - ox, oy + h)
    if anchor == "bottom-left":
        return (ox + w, page_h - oy)
    return (page_w - ox, page_h - oy)


# ==========================================================================================================
#             PREP USER EDITABLE PAGE SVGS
# ==========================================================================================================
page_counter = 0
for page in page_data.get("pages", []):
    page_counter += 1
    this_page_name = pdf_drawings_utils.page_name(page)

    lib_imported_dirpath = os.path.join(
        dirpath(None), "instance_data", "titleblock", f"{artifact_id}-{this_page_name}"
    )

    fileio.silentremove(lib_imported_dirpath)

    library_utils.pull(
        {
            "instance_name": f"{artifact_id}-{this_page_name}",
            "mpn": page.get("tblock_mpn"),
            "lib_repo": page.get("tblock_lib_repo"),
            "lib_subpath": page.get("tblock_lib_subpath") or "library/titleblocks/",
        },
        update_instances_list=False,
        destination_directory=lib_imported_dirpath,
    )

    tblock_name = f"{artifact_id}-{this_page_name}"
    lib_imported_drawing_filepath = os.path.join(
        lib_imported_dirpath, "drawing.svg"
    )
    lib_imported_attributes_filepath = os.path.join(
        lib_imported_dirpath, "attributes.json"
    )

    text_map = page.get("text_replacements", {})
    with open(lib_imported_drawing_filepath, "r", encoding="utf-8") as f:
        svg = f.read()

    for old, new in text_map.items():
        if isinstance(new, bool) or new is None:
            new = "" if new is None else str(new)
        elif isinstance(new, (int, float)):
            new = f"{float(new):.3f}"
        else:
            new = str(new)

        if new == "autosheet":
            total_pages = len(page_data.get("pages", []))
            new = f"{page_counter} of {total_pages}"

        svg = svg.replace(old, new)

    with open(lib_imported_drawing_filepath, "w", encoding="utf-8") as f:
        f.write(svg)

    with open(lib_imported_attributes_filepath) as f:
        tblock_attributes = json.load(f)

    page_size_in = page.get("page_size_in") or [11.0, 8.5]
    page_size_px = [int(page_size_in[0] * 96), int(page_size_in[1] * 96)]
    tblock_size = tblock_attributes.get("tblock_size_px") or [604, 48]
    tblock_w, tblock_h = int(tblock_size[0]), int(tblock_size[1])

    anchor = page.get("tblock_anchor") or "bottom-right"
    offset = page.get("tblock_offset_px") or [40.0, 40.0]
    tx, ty = tblock_origin_on_page(
        page_size_px[0], page_size_px[1], tblock_w, tblock_h, anchor, offset
    )
    wrap_tblock_with_translate(lib_imported_drawing_filepath, tx, ty)

    page_svg = path(
        "user editable page svg", page_name=this_page_name, page_counter=page_counter
    )
    ensure_page_svg_scaffold(page_svg, page_size_px[0], page_size_px[1])

    frame_src = os.path.join(
        dirpath(None), "instance_data", f"{artifact_id}-{this_page_name}-page-frame.svg"
    )
    os.makedirs(os.path.dirname(frame_src), exist_ok=True)
    write_frame_source_svg(frame_src, page_size_px[0], page_size_px[1], tblock_h)

    svg_utils.find_and_replace_svg_group(
        frame_src,
        "page-frame",
        page_svg,
        "page-frame",
    )

    svg_utils.find_and_replace_svg_group(
        lib_imported_drawing_filepath,
        "tblock",
        page_svg,
        "tblock",
    )

    svg_utils.find_and_replace_svg_group(
        path("master contents svg"),
        "svg-master",
        page_svg,
        "svg-master",
    )

# ============================================
#            PRODUCE MULTIPAGE PDF
# ============================================
temp_pdfs = []

page_counter = 0
for this_page_name in [
    pdf_drawings_utils.page_name(p) for p in page_data.get("pages", [])
]:
    page_counter += 1
    svg_path = path(
        "user editable page svg", page_name=this_page_name, page_counter=page_counter
    )
    pdf_path = svg_path.replace(".svg", ".temp.pdf")

    with open(svg_path, encoding="utf-8") as f:
        page_svg = f.read()
    export_svg = pdf_drawings_utils.strip_configuration_elements(page_svg)
    export_path = svg_path
    export_tmp = None
    if export_svg != page_svg:
        export_tmp = svg_path.replace(".svg", ".inkscape.svg")
        with open(export_tmp, "w", encoding="utf-8") as f:
            f.write(export_svg)
        export_path = export_tmp

    try:
        _run_inkscape(
            [
                export_path,
                "--export-type=pdf",
                f"--export-filename={pdf_path}",
            ],
            check=True,
        )
    finally:
        if export_tmp and os.path.exists(export_tmp):
            os.remove(export_tmp)

    temp_pdfs.append(pdf_path)

# Merge into the project root (rev directory). Omit base_directory so this
# does not land under instance_data/macro/{artifact_id}/.
writer = PdfWriter()
for pdf_path in temp_pdfs:
    writer.append(pdf_path)
writer.write(fileio.path("output pdf", structure_dict=macro_file_structure()))
writer.close()

# Optional cleanup
for temp in temp_pdfs:
    os.remove(temp)
