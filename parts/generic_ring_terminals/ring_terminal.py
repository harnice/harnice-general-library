"""Generic ring-terminal chooser.

Legal SKUs are the curated AWG, stud, and insulation combinations sold as
common vinyl-insulated and bare copper ring terminals. Dimensions are
estimated envelopes, not a vendor drawing. Harness build instructions
import this module, not the generator.

    import os
    import sys

    from harnice.lists import instances_list
    from harnice.utils import library_utils

    LIBRARY_REPO = "https://github.com/harnice/harnice-general-library"
    LIBRARY_SUBPATH = "parts/generic_ring_terminals/"
    sys.path.append(
        os.path.join(library_utils.get_local_path(LIBRARY_REPO), LIBRARY_SUBPATH)
    )
    import ring_terminal

    for instance in instances_list.read():
        if instance.get("item_type") != "part":
            continue
        gauge = instance.get("wire_gauge_awg")
        stud = instance.get("stud_size")
        if not gauge or not stud:
            continue
        instances_list.modify(
            instance.get("instance_name"),
            {
                "mpn": ring_terminal.choose_part(
                    gauge, stud, insulation=instance.get("insulation_color")
                ),
                "lib_repo": LIBRARY_REPO,
                "lib_subpath": LIBRARY_SUBPATH,
            },
        )
"""
import re

LIBRARY_REPO = "https://github.com/harnice/harnice-general-library"
LIBRARY_SUBPATH = "parts/generic_ring_terminals/"
MANUFACTURER = ""

# Stud clearance holes, inches. estimate: typical vinyl and bare copper
# terminals, not a single manufacturer table.
# https://www.mcmaster.com/products/ring-terminals/
STUD_SIZES = {
    "#0": 0.067,  "#1": 0.08,   "#2": 0.093,  "#4": 0.119,
    "#5": 0.132,  "#6": 0.145,  "#8": 0.171,  "#10": 0.197,
    "#12": 0.223, "#14": 0.25,
    "1/4": 0.265, "5/16": 0.328, "3/8": 0.39, "7/16": 0.453,
    "1/2": 0.515, "5/8": 0.656, "3/4": 0.781, "7/8": 0.906,
    "1": 1.031,
}

AWG_OD = {
    "4/0": 0.46,     "3/0": 0.409642, "2/0": 0.364797, "1/0": 0.324861,
    "1": 0.289297,   "2": 0.257626,   "3": 0.229423,   "4": 0.204307,
    "5": 0.181941,   "6": 0.162023,   "7": 0.144285,   "8": 0.128490,
    "9": 0.114424,   "10": 0.101897,  "11": 0.090742,  "12": 0.080808,
    "13": 0.071962,  "14": 0.064084,  "15": 0.057068,  "16": 0.050821,
    "17": 0.045257,  "18": 0.040303,  "19": 0.035891,  "20": 0.031961,
    "21": 0.028462,  "22": 0.025347,  "23": 0.022572,  "24": 0.020101,
    "25": 0.017900,  "26": 0.015941,  "27": 0.014196,  "28": 0.012641,
    "29": 0.011258,  "30": 0.010025,  "31": 0.008928,  "32": 0.007950,
    "33": 0.007080,  "34": 0.006305,  "35": 0.005615,  "36": 0.005000,
    "37": 0.004453,  "38": 0.003965,  "39": 0.003531,  "40": 0.003145,
}

# Standard insulation colour coding per wire-gauge band
INSULATION_COLORS = {
    "red":    "#FF0000",  # 22-18 AWG
    "blue":   "#0000FF",  # 16-14 AWG
    "yellow": "#FFFF00",  # 12-10 AWG
}

# (wire gauges, stud sizes, insulation options)
COMMON_COMBOS = [
    # Small insulated terminals (colour-coded red / blue / yellow)
    (["22", "20", "18"], ["#4", "#6", "#8", "#10", "1/4", "5/16", "3/8"],
     ["#FF0000", None]),
    (["16", "14"],       ["#4", "#6", "#8", "#10", "1/4", "5/16", "3/8"],
     ["#0000FF", None]),
    (["12", "10"],       ["#6", "#8", "#10", "1/4", "5/16", "3/8", "1/2"],
     ["#FFFF00", None]),
    # Larger bare terminals
    (["8"],              ["#8", "#10", "1/4", "5/16", "3/8", "1/2"],        [None]),
    (["6"],              ["#10", "1/4", "5/16", "3/8", "1/2"],              [None]),
    (["4"],              ["1/4", "5/16", "3/8", "1/2", "5/8"],             [None]),
    (["3", "2"],         ["1/4", "5/16", "3/8", "1/2", "5/8"],             [None]),
    (["1"],              ["1/4", "5/16", "3/8", "1/2", "5/8", "3/4"],      [None]),
    (["1/0"],            ["1/4", "5/16", "3/8", "1/2", "5/8", "3/4"],      [None]),
    (["2/0"],            ["5/16", "3/8", "1/2", "5/8", "3/4"],             [None]),
    (["3/0"],            ["3/8", "1/2", "5/8", "3/4"],                     [None]),
    (["4/0"],            ["3/8", "1/2", "5/8", "3/4", "1"],                [None]),
]

_PN_RE = re.compile(
    r"^RING[_-]?TERMINAL[-_]"
    r"(?P<gauge>\d+(?:_\d+)?|\d+/\d+)"
    r"[-_]"
    r"(?P<stud>#?\d+(?:_\d+)?|#?\d+/\d+)"
    r"(?:[-_](?P<ins>[0-9A-Fa-f]{6}))?$",
    re.IGNORECASE,
)

_HEX_TO_COLOR = {
    hex_code.lstrip("#").upper(): name
    for name, hex_code in INSULATION_COLORS.items()
}
_COLOR_TO_HEX = {
    name.upper(): hex_code.lstrip("#").upper()
    for name, hex_code in INSULATION_COLORS.items()
}


def iter_part_configurations():
    """Yield one dict per legal SKU."""
    for gauges, studs, insulations in COMMON_COMBOS:
        for gauge in gauges:
            for stud in studs:
                for ins in insulations:
                    yield {
                        "wire_gauge": gauge,
                        "stud_size": stud,
                        "insulation": ins,
                    }


def make_part_number(cfg):
    """Filesystem-safe library PN, e.g. RING_TERMINAL-18-8-FF0000."""
    gauge = str(cfg["wire_gauge"]).lstrip("#").replace("/", "_")
    stud = str(cfg["stud_size"]).lstrip("#").replace("/", "_")
    ins = ""
    if cfg["insulation"]:
        ins = f"-{cfg['insulation'].lstrip('#')}"
    return f"RING_TERMINAL-{gauge}-{stud}{ins}"


def official_pin(cfg):
    return make_part_number(cfg)


def insulation_color_name(insulation):
    if not insulation:
        return None
    key = str(insulation).lstrip("#").upper()
    if key in _HEX_TO_COLOR:
        return _HEX_TO_COLOR[key]
    if key in _COLOR_TO_HEX:
        return key.lower()
    return None


def description_from_cfg(cfg):
    """Short catalog description: gauge, stud, and insulation color."""
    stud = cfg["stud_size"]
    stud_text = "1 IN" if stud == "1" else stud
    desc = f"RING TERMINAL, {cfg['wire_gauge']} AWG, {stud_text} STUD"
    insulation = cfg.get("insulation")
    if insulation:
        color = insulation_color_name(insulation)
        desc += f", {(color or insulation).upper()}"
    return desc


def insulation_hex(insulation):
    if insulation is None or insulation is False:
        return None
    text = str(insulation).strip()
    if text.lower() in ("bare", "none", "uninsulated", ""):
        return None
    key = text.lstrip("#").upper()
    if key in _HEX_TO_COLOR:
        return f"#{key}"
    if key in _COLOR_TO_HEX:
        return f"#{_COLOR_TO_HEX[key]}"
    raise ValueError(
        f"Unknown insulation {insulation!r}. "
        f"Expected bare/None or one of: {', '.join(INSULATION_COLORS)}."
    )


def default_insulation_hex(gauge):
    if "/0" in gauge:
        n = 1 - int(gauge.split("/")[0])
    else:
        n = int(gauge)
    if 18 <= n <= 22:
        return "#FF0000"
    if 14 <= n <= 16:
        return "#0000FF"
    if 10 <= n <= 12:
        return "#FFFF00"
    return None


def list_gauges():
    seen = []
    for cfg in iter_part_configurations():
        if cfg["wire_gauge"] not in seen:
            seen.append(cfg["wire_gauge"])
    return seen


def list_stud_sizes():
    seen = []
    for cfg in iter_part_configurations():
        if cfg["stud_size"] not in seen:
            seen.append(cfg["stud_size"])
    return seen


def _normalize_gauge(value):
    text = str(value).strip().upper().replace("_", "/")
    if text.endswith("AWG"):
        text = text[:-3].strip()
    if text not in AWG_OD:
        raise ValueError(
            f"Unknown wire gauge {value!r}. This library has: {', '.join(list_gauges())}."
        )
    if "/0" in text:
        return text
    if text.isdigit():
        return str(int(text))
    return text


def _normalize_stud(value):
    text = str(value).strip().replace("_", "/")
    if text.upper().startswith("NO"):
        text = "#" + text[2:].lstrip(". ")
    if not text.startswith("#") and "/" not in text and text.isdigit():
        number = str(int(text))
        machine = f"#{number}"
        sold = set(list_stud_sizes())
        if machine in sold and number not in sold:
            text = machine
        elif number in sold and machine not in sold:
            text = number
        elif machine in STUD_SIZES:
            text = machine
        else:
            text = number
    if text.startswith("#"):
        rest = text[1:]
        if rest.isdigit():
            text = f"#{int(rest)}"
    aliases = {
        "1/4IN": "1/4",
        "5/16IN": "5/16",
        "3/8IN": "3/8",
        "7/16IN": "7/16",
        "1/2IN": "1/2",
        "5/8IN": "5/8",
        "3/4IN": "3/4",
        "7/8IN": "7/8",
        "1IN": "1",
    }
    compact = text.upper().replace(" ", "")
    text = aliases.get(compact, text)
    if text not in STUD_SIZES:
        raise ValueError(
            f"Unknown stud size {value!r}. This library has: {', '.join(list_stud_sizes())}."
        )
    return text


def list_parts(gauge=None, stud_size=None):
    """Library PNs, optionally filtered."""
    out = []
    for cfg in iter_part_configurations():
        if gauge is not None and cfg["wire_gauge"] != _normalize_gauge(gauge):
            continue
        if stud_size is not None and cfg["stud_size"] != _normalize_stud(stud_size):
            continue
        out.append(make_part_number(cfg))
    return out


def choose_part(wire_gauge, stud_size, insulation=None):
    """Choose a ring terminal that exists in this library.

    wire_gauge is an AWG such as 18, "18", "1/0", or "1_0". stud_size is
    #8, 8, 1/4, 1_4, or 5/16. insulation is None or bare for uninsulated,
    True for the default vinyl colour of that AWG band, or a colour name
    or hex such as red or #FF0000.

    Returns the library PN. Raises ValueError when that combination is not
    in this library.
    """
    gauge = _normalize_gauge(wire_gauge)
    stud = _normalize_stud(stud_size)
    if insulation is True:
        hex_code = default_insulation_hex(gauge)
    else:
        hex_code = insulation_hex(insulation)
    cfg = {"wire_gauge": gauge, "stud_size": stud, "insulation": hex_code}
    pn = make_part_number(cfg)
    if pn not in _CATALOG:
        legal = list_parts(gauge=gauge)
        preview = ", ".join(legal[:12])
        if len(legal) > 12:
            preview += "…"
        if hex_code:
            kind = f"insulated {insulation_color_name(hex_code) or 'vinyl'}"
        else:
            kind = "bare"
        raise ValueError(
            f"No ring terminal for {gauge} AWG / {stud} stud / {kind} in this library. "
            f"Examples for {gauge} AWG: {preview}."
        )
    return pn


def parse_ring_terminal(part_number):
    """Parse a library PN into wire_gauge, stud_size, and insulation hex."""
    text = str(part_number).strip()
    match = _PN_RE.match(text.replace(" ", ""))
    if not match:
        raise ValueError(
            f"Could not parse {part_number!r} as a ring terminal. "
            "Expected RING_TERMINAL-18-8 or RING_TERMINAL-18-8-FF0000."
        )
    gauge = _normalize_gauge(match.group("gauge"))
    stud = _normalize_stud(match.group("stud"))
    raw_ins = match.group("ins")
    insulation = f"#{raw_ins.upper()}" if raw_ins else None
    cfg = {"wire_gauge": gauge, "stud_size": stud, "insulation": insulation}
    pn = make_part_number(cfg)
    if pn not in _CATALOG:
        raise ValueError(
            f"{part_number!r} is not a SKU in this library."
        )
    return dict(_CATALOG[pn])


def _commercial_band(wire_gauge):
    """Gauge band commercial ring terminals are sold in."""
    gauge = str(wire_gauge)
    if gauge in ("22", "20", "18"):
        return "22-18"
    if gauge in ("16", "14"):
        return "16-14"
    if gauge in ("12", "10"):
        return "12-10"
    return gauge


# Molex InsulKrimp 19070, PVC, tin-plated copper, loose piece. When several
# lengths exist, this is the shorter carton/bag number.
# https://www.molex.com/en-us/products/series-chart/19070
MOLEX_INSULATED = {
    ("22-18", "#4"): "19070-0007",
    ("22-18", "#6"): "19070-0009",
    ("22-18", "#8"): "19070-0013",
    ("22-18", "#10"): "19070-0015",
    ("22-18", "1/4"): "19070-0023",
    ("22-18", "5/16"): "19070-0026",
    ("22-18", "3/8"): "19070-0033",
    ("16-14", "#6"): "19070-0083",
    ("16-14", "#8"): "19070-0086",
    ("16-14", "#10"): "19070-0090",
    ("16-14", "1/4"): "19070-0075",
    ("16-14", "5/16"): "19070-0078",
    ("12-10", "#6"): "19070-0119",
    ("12-10", "#8"): "19070-0121",
    ("12-10", "#10"): "19070-0123",
    ("12-10", "1/4"): "19070-0132",
    ("12-10", "1/2"): "19070-0109",
}

# Molex VersaKrimp 19193, noninsulated tin-plated copper, carton.
# https://www.molex.com/en-us/products/series-chart/19193
MOLEX_BARE = {
    ("22-18", "#4"): "19193-0007",
    ("22-18", "#6"): "19193-0009",
    ("22-18", "#8"): "19193-0014",
    ("22-18", "#10"): "19193-0016",
    ("22-18", "5/16"): "19193-0023",
    ("16-14", "#6"): "19193-0078",
    ("16-14", "#8"): "19193-0080",
    ("16-14", "#10"): "19193-0082",
    ("16-14", "1/4"): "19193-0055",
    ("16-14", "5/16"): "19193-0074",
    ("16-14", "3/8"): "19193-0057",
}

# McMaster-Carr vinyl, tin-plated copper. #4 and the two 12-10 studs that
# are missing from the basic vinyl table are the vinyl-with-brass-sleeve
# parts. https://www.mcmaster.com/products/ring-terminals/
MCMASTER_INSULATED = {
    ("22-18", "#4"): "7113K201",
    ("22-18", "#6"): "7113K35",
    ("22-18", "#8"): "7113K611",
    ("22-18", "#10"): "7113K98",
    ("22-18", "1/4"): "7113K612",
    ("22-18", "5/16"): "7113K613",
    ("22-18", "3/8"): "7113K614",
    ("16-14", "#4"): "7113K202",
    ("16-14", "#6"): "7113K23",
    ("16-14", "#8"): "7113K49",
    ("16-14", "#10"): "7113K24",
    ("16-14", "1/4"): "7113K25",
    ("16-14", "5/16"): "7113K92",
    ("16-14", "3/8"): "7113K95",
    ("12-10", "#6"): "7113K203",
    ("12-10", "#8"): "7113K48",
    ("12-10", "#10"): "7113K29",
    ("12-10", "1/4"): "7113K31",
    ("12-10", "5/16"): "7113K204",
    ("12-10", "3/8"): "7113K32",
    ("12-10", "1/2"): "7113K82",
}

# McMaster-Carr noninsulated tin-plated copper. Steel and nickel rows for
# the same gauge and stud are not used.
MCMASTER_BARE = {
    ("22-18", "#4"): "7113K148",
    ("22-18", "#6"): "7113K11",
    ("22-18", "#8"): "7113K551",
    ("22-18", "#10"): "7113K97",
    ("22-18", "1/4"): "7113K552",
    ("22-18", "5/16"): "7113K553",
    ("22-18", "3/8"): "7113K554",
    ("16-14", "#4"): "7113K142",
    ("16-14", "#6"): "7113K34",
    ("16-14", "#8"): "7113K38",
    ("16-14", "#10"): "7113K12",
    ("16-14", "1/4"): "7113K13",
    ("16-14", "5/16"): "7113K91",
    ("16-14", "3/8"): "7113K94",
    ("12-10", "#6"): "7113K141",
    ("12-10", "#8"): "7113K37",
    ("12-10", "#10"): "7113K17",
    ("12-10", "1/4"): "7113K18",
    ("12-10", "3/8"): "7113K19",
    ("12-10", "1/2"): "7113K81",
    ("8", "#10"): "7113K241",
    ("8", "1/4"): "7113K242",
    ("8", "5/16"): "7113K243",
    ("8", "3/8"): "7113K244",
    ("8", "1/2"): "7113K271",
    ("6", "#10"): "7113K445",
    ("6", "1/4"): "7113K446",
    ("6", "5/16"): "7113K447",
    ("6", "3/8"): "7113K448",
    ("6", "1/2"): "7113K273",
    ("4", "1/4"): "7113K249",
    ("4", "5/16"): "7113K251",
    ("4", "3/8"): "7113K252",
    ("4", "1/2"): "7113K253",
    ("4", "5/8"): "7113K563",
}


def molex_part(wire_gauge, stud_size, insulation=None):
    """Molex part number for this gauge, stud, and insulation, or None."""
    table = MOLEX_INSULATED if insulation else MOLEX_BARE
    return table.get((_commercial_band(wire_gauge), stud_size))


def mcmaster_part(wire_gauge, stud_size, insulation=None):
    """McMaster-Carr part number for this gauge, stud, and insulation, or None."""
    table = MCMASTER_INSULATED if insulation else MCMASTER_BARE
    return table.get((_commercial_band(wire_gauge), stud_size))


CSV_COLUMNS = (
    "library_pn",
    "wire_gauge_awg",
    "stud_size",
    "insulated",
    "insulation_color",
    "insulation_hex",
    "stud_hole_id_in",
    "molex_pn",
    "mcmaster_pn",
    "library_subpath",
)


def catalog_row(cfg):
    hex_code = cfg["insulation"]
    return {
        "library_pn": make_part_number(cfg),
        "wire_gauge_awg": cfg["wire_gauge"],
        "stud_size": cfg["stud_size"],
        "insulated": hex_code is not None,
        "insulation_color": insulation_color_name(hex_code) or "",
        "insulation_hex": hex_code.lstrip("#") if hex_code else "",
        "stud_hole_id_in": STUD_SIZES[cfg["stud_size"]],
        "molex_pn": molex_part(cfg["wire_gauge"], cfg["stud_size"], hex_code) or "",
        "mcmaster_pn": mcmaster_part(cfg["wire_gauge"], cfg["stud_size"], hex_code) or "",
        "library_subpath": LIBRARY_SUBPATH,
    }


_CATALOG = {make_part_number(cfg): cfg for cfg in iter_part_configurations()}
