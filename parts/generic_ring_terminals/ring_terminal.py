"""Generic ring-terminal chooser.

Legal SKUs are the curated AWG / stud / insulation combinations sold as
common vinyl-insulated and bare copper ring terminals (Panduit, 3M,
McMaster generic). Dimensions are estimated envelopes, not a vendor
drawing. Harness build instructions import this module, not the generator.

    import os
    import sys

    from harnice.lists import instances_list
    from harnice.utils import library_utils

    LIBRARY_REPO = "https://github.com/harnice/harnice-general-library"
    LIBRARY_SUBPATH = "parts/generic_ring_terminals"
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

from __future__ import annotations

import re

LIBRARY_REPO = "https://github.com/harnice/harnice-general-library"
LIBRARY_SUBPATH = "parts/generic_ring_terminals"
MANUFACTURER = ""

# Stud clearance holes, inches. estimate: typical vinyl / bare copper
# terminals, not a single manufacturer table.
# https://www.mcmaster.com/products/ring-terminals/
STUD_SIZES = {
    "#0": 0.067,
    "#1": 0.08,
    "#2": 0.093,
    "#4": 0.119,
    "#5": 0.132,
    "#6": 0.145,
    "#8": 0.171,
    "#10": 0.197,
    "#12": 0.223,
    "#14": 0.25,
    "1/4": 0.265,
    "5/16": 0.328,
    "3/8": 0.39,
    "7/16": 0.453,
    "1/2": 0.515,
    "5/8": 0.656,
    "3/4": 0.781,
    "7/8": 0.906,
    "1": 1.031,
}

# Bare-copper conductor OD, inches (AWG).
AWG_OD = {
    "4/0": 0.46,
    "3/0": 0.409642,
    "2/0": 0.364797,
    "1/0": 0.324861,
    "1": 0.289297,
    "2": 0.257626,
    "3": 0.229423,
    "4": 0.204307,
    "5": 0.181941,
    "6": 0.162023,
    "7": 0.144285,
    "8": 0.128490,
    "9": 0.114424,
    "10": 0.101897,
    "11": 0.090742,
    "12": 0.080808,
    "13": 0.071962,
    "14": 0.064084,
    "15": 0.057068,
    "16": 0.050821,
    "17": 0.045257,
    "18": 0.040303,
    "19": 0.035891,
    "20": 0.031961,
    "21": 0.028462,
    "22": 0.025347,
    "23": 0.022572,
    "24": 0.020101,
    "25": 0.017900,
    "26": 0.015941,
    "27": 0.014196,
    "28": 0.012641,
    "29": 0.011258,
    "30": 0.010025,
    "31": 0.008928,
    "32": 0.007950,
    "33": 0.007080,
    "34": 0.006305,
    "35": 0.005615,
    "36": 0.005000,
    "37": 0.004453,
    "38": 0.003965,
    "39": 0.003531,
    "40": 0.003145,
}

# Standard vinyl insulation colour coding per wire-gauge band.
INSULATION_COLORS = {
    "red": "#FF0000",  # 22-18 AWG
    "blue": "#0000FF",  # 16-14 AWG
    "yellow": "#FFFF00",  # 12-10 AWG
}

# (wire gauges, stud sizes, insulation options as hex or None).
# Curated common combinations; not every AWG/stud pair is sold.
COMMON_COMBOS = [
    (["22", "20", "18"], ["#4", "#6", "#8", "#10", "1/4", "5/16", "3/8"],
     ["#FF0000", None]),
    (["16", "14"], ["#4", "#6", "#8", "#10", "1/4", "5/16", "3/8"],
     ["#0000FF", None]),
    (["12", "10"], ["#6", "#8", "#10", "1/4", "5/16", "3/8", "1/2"],
     ["#FFFF00", None]),
    (["8"], ["#8", "#10", "1/4", "5/16", "3/8", "1/2"], [None]),
    (["6"], ["#10", "1/4", "5/16", "3/8", "1/2"], [None]),
    (["4"], ["1/4", "5/16", "3/8", "1/2", "5/8"], [None]),
    (["3", "2"], ["1/4", "5/16", "3/8", "1/2", "5/8"], [None]),
    (["1"], ["1/4", "5/16", "3/8", "1/2", "5/8", "3/4"], [None]),
    (["1/0"], ["1/4", "5/16", "3/8", "1/2", "5/8", "3/4"], [None]),
    (["2/0"], ["5/16", "3/8", "1/2", "5/8", "3/4"], [None]),
    (["3/0"], ["3/8", "1/2", "5/8", "3/4"], [None]),
    (["4/0"], ["3/8", "1/2", "5/8", "3/4", "1"], [None]),
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


def make_part_number(cfg: dict) -> str:
    """Filesystem-safe library PN, e.g. RING_TERMINAL-18-8-FF0000."""
    gauge = _fs_token(cfg["wire_gauge"])
    stud = _fs_token(cfg["stud_size"])
    ins = f"-{cfg['insulation'].lstrip('#')}" if cfg["insulation"] else ""
    return f"RING_TERMINAL-{gauge}-{stud}{ins}"


def official_pin(cfg: dict) -> str:
    return make_part_number(cfg)


def description_from_cfg(cfg: dict) -> str:
    color = insulation_color_name(cfg["insulation"])
    if color:
        ins = f"{color.upper()} VINYL INSULATION"
    else:
        ins = "BARE"
    return (
        f"RING TERMINAL, {cfg['wire_gauge']} AWG, {cfg['stud_size']} STUD, "
        f"{ins}, TIN-PLATED COPPER"
    )


def insulation_color_name(insulation) -> str | None:
    if not insulation:
        return None
    key = str(insulation).lstrip("#").upper()
    if key in _HEX_TO_COLOR:
        return _HEX_TO_COLOR[key]
    if key in _COLOR_TO_HEX:
        return key.lower()
    return None


def insulation_hex(insulation) -> str | None:
    if insulation is None or insulation is False:
        return None
    if insulation is True:
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


def default_insulation_hex(gauge: str) -> str | None:
    n = _awg_sort_key(gauge)
    if 18 <= n <= 22:
        return "#FF0000"
    if 14 <= n <= 16:
        return "#0000FF"
    if 10 <= n <= 12:
        return "#FFFF00"
    return None


def choose_part(wire_gauge, stud_size, insulation=None):
    """
    Choose a ring terminal that exists in this library.

    wire_gauge:
      AWG as 18, "18", "1/0", "1_0".
    stud_size:
      #8, 8, 1/4, 1_4, 5/16, …
    insulation:
      None / bare — uninsulated
      True — default vinyl colour for that AWG band (red/blue/yellow)
      red / blue / yellow / #FF0000 — that vinyl colour

    Returns the library PN. Raises ValueError if that combo is not sold here.
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
        legal = ", ".join(list_parts(gauge=gauge)[:12])
        more = "…" if len(list_parts(gauge=gauge)) > 12 else ""
        raise ValueError(
            f"No ring terminal for {gauge} AWG / {stud} stud / "
            f"{'insulated ' + (insulation_color_name(hex_code) or 'vinyl') if hex_code else 'bare'} "
            f"in this library. Examples for {gauge} AWG: {legal}{more}."
        )
    return pn


def parse_ring_terminal(part_number):
    """Parse a library PN into wire_gauge, stud_size, insulation hex."""
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
            f"{part_number!r} is not a SKU in this library. "
            f"Legal PNs: {', '.join(list_parts())}."
        )
    return dict(_CATALOG[pn])


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


def list_gauges():
    return list(dict.fromkeys(cfg["wire_gauge"] for cfg in iter_part_configurations()))


def list_stud_sizes():
    return list(dict.fromkeys(cfg["stud_size"] for cfg in iter_part_configurations()))


CATALOG_COLUMNS = (
    "library_pn",
    "wire_gauge_awg",
    "stud_size",
    "insulated",
    "insulation_color",
    "insulation_hex",
    "stud_hole_id_in",
    "library_subpath",
)


def catalog_row(cfg: dict) -> dict:
    hex_code = cfg["insulation"]
    return {
        "library_pn": make_part_number(cfg),
        "wire_gauge_awg": cfg["wire_gauge"],
        "stud_size": cfg["stud_size"],
        "insulated": hex_code is not None,
        "insulation_color": insulation_color_name(hex_code) or "",
        "insulation_hex": hex_code.lstrip("#") if hex_code else "",
        "stud_hole_id_in": STUD_SIZES[cfg["stud_size"]],
        "library_subpath": LIBRARY_SUBPATH,
    }


def _fs_token(value: str) -> str:
    return str(value).lstrip("#").replace("/", "_")


def _normalize_gauge(value) -> str:
    text = str(value).strip().upper().replace("_", "/")
    if text.endswith("AWG"):
        text = text[:-3].strip()
    if text not in AWG_OD:
        raise ValueError(
            f"Unknown wire gauge {value!r}. "
            f"This library has: {', '.join(list_gauges())}."
        )
    return text if "/0" in text else str(int(text)) if text.isdigit() else text


def _normalize_stud(value) -> str:
    text = str(value).strip().replace("_", "/")
    if text.upper().startswith("NO"):
        text = "#" + text[2:].lstrip(". ")
    if not text.startswith("#") and "/" not in text and text.isdigit():
        if int(text) <= 14:
            text = f"#{int(text)}"
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
            f"Unknown stud size {value!r}. "
            f"This library has: {', '.join(list_stud_sizes())}."
        )
    return text


def _awg_sort_key(gauge: str) -> int:
    if "/0" in gauge:
        return 1 - int(gauge.split("/")[0])
    return int(gauge)


_CATALOG = {make_part_number(cfg): cfg for cfg in iter_part_configurations()}
