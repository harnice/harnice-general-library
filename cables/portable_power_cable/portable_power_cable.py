"""Portable-power-cable chooser (UL letter-code service cord).

Legal SKUs are the UL 62 type / AWG / conductor-count combinations that
are commonly sold as bulk portable cord. McMaster-Carr bulk PNs are
recorded when they exist; types they do not stock are still emitted if
the UL designation is commercially real. Harness build instructions
import this module, not the generator.

    import os
    import sys

    from harnice.lists import instances_list
    from harnice.utils import library_utils

    LIBRARY_REPO = "https://github.com/harnice/harnice-general-library"
    LIBRARY_SUBPATH = "cables/portable_power_cable"
    sys.path.append(
        os.path.join(library_utils.get_local_path(LIBRARY_REPO), LIBRARY_SUBPATH)
    )
    import portable_power_cable

    for instance in instances_list.read():
        if instance.get("item_type") != "cable":
            continue
        code = instance.get("cable_type")
        gauge = instance.get("gauge_awg")
        n = instance.get("conductors")
        if not code or not gauge or not n:
            continue
        instances_list.modify(
            instance.get("instance_name"),
            {
                "mpn": portable_power_cable.choose_part(code, gauge, n),
                "lib_repo": LIBRARY_REPO,
                "lib_subpath": LIBRARY_SUBPATH,
            },
        )
"""

from __future__ import annotations

import re

LIBRARY_REPO = "https://github.com/harnice/harnice-general-library"
LIBRARY_SUBPATH = "cables/portable_power_cable"
MANUFACTURER = ""

# Bare-copper conductor OD, inches (AWG).
AWG_OD = {
    "4/0": 0.460000,
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
}

# ASTM B172 Class K (30 AWG strand) — typical for portable cord.
CLASS_K_STRANDING = {
    "18": "16x30",
    "17": "19x30",
    "16": "26x30",
    "14": "41x30",
    "12": "65x30",
    "10": "104x30",
    "8": "168x30",
    "6": "266x30",
    "4": "420x30",
    "2": "665x30",
    "1/0": "1064x30",
    "2/0": "1330x30",
    "3/0": "1672x30",
    "4/0": "2109x30",
}

EVEN_AWG = [
    "18", "16", "14", "12", "10", "8", "6", "4", "2",
    "1/0", "2/0", "3/0", "4/0",
]

# Portable-cord color code: hots, then neutral, then equipment ground last.
CONDUCTOR_COLORS = {
    2: ["black", "white"],
    3: ["black", "white", "green"],
    4: ["black", "white", "red", "green"],
    5: ["black", "white", "red", "orange", "green"],
}

# McMaster-Carr bulk (by-the-foot) catalog numbers, black jacket unless noted.
# Sourced from mcmaster.com power-cable tables. Sizes they do not sell are omitted.
# https://www.mcmaster.com/products/portable-cord/
MCMASTER_SOOW = {
    ("18", 2): "7081K11",
    ("18", 3): "7081K12",
    ("18", 4): "7081K13",
    ("16", 2): "7081K14",
    ("16", 3): "7081K22",
    ("16", 4): "7081K31",
    ("14", 2): "7081K15",
    ("14", 3): "7081K23",
    ("14", 4): "7081K32",
    ("12", 2): "7081K16",
    ("12", 3): "7081K24",
    ("12", 4): "7081K33",
    ("10", 2): "7081K17",
    ("10", 3): "7081K41",
    ("10", 4): "7081K42",
    ("8", 3): "7081K35",
    ("8", 4): "7081K82",
    ("6", 3): "7081K84",
    ("6", 4): "7081K25",
    ("4", 3): "7081K3",
    ("4", 4): "7081K28",
    ("2", 4): "7081K34",
}
MCMASTER_SJOOW = {
    ("18", 2): "7422K2",
    ("18", 3): "7422K21",
    ("18", 4): "7422K11",
    ("16", 2): "7422K61",
    ("16", 3): "7422K22",
    ("16", 4): "7422K23",
    ("14", 2): "7422K62",
    ("14", 3): "7422K24",
    ("14", 4): "7422K25",
    ("12", 2): "7422K1",
    ("12", 3): "7422K26",
    ("12", 4): "7422K27",
    ("10", 2): "7422K75",
    ("10", 3): "7422K28",
    ("10", 4): "7422K29",
}
MCMASTER_SJTOW = {
    ("18", 3): "8169K31",
    ("16", 3): "8169K32",
    ("16", 4): "8169K34",
}
MCMASTER_STOW = {
    ("18", 3): "8201K41",
    ("16", 3): "8201K42",
    ("16", 4): "8201K43",
    ("14", 3): "8201K44",
    ("14", 4): "8201K45",
    ("12", 3): "8201K46",
    ("12", 4): "8201K47",
}
MCMASTER_SPT1 = {
    ("18", 2): "7870T21",
}


def mcmaster_part(code: str, gauge: str, n_conductors: int) -> dict | None:
    """Return the McMaster bulk PN for this type/gauge/count, if they sell one.

    Exact designation is preferred. When McMaster does not stock that letter
    code as bulk cable, the closest bulk type they do sell is used and recorded
    as `designation`.
    """
    key = (gauge, n_conductors)

    def hit(designation: str, table: dict) -> dict | None:
        pn = table.get(key)
        if not pn:
            return None
        return {
            "pn": pn,
            "designation": designation,
            "url": f"https://www.mcmaster.com/{pn}/",
        }

    if code == "SOOW":
        return hit("SOOW", MCMASTER_SOOW)
    if code in ("S", "SO", "SOO"):
        return hit("SOOW", MCMASTER_SOOW)
    if code == "SJTOW":
        return hit("SJTOW", MCMASTER_SJTOW) or hit("SJOOW", MCMASTER_SJOOW)
    if code in ("SJT", "SJTW", "SJTO", "SJTOOW"):
        return hit("SJOOW", MCMASTER_SJOOW)
    if code in ("ST", "STW", "STO"):
        return hit("STOW", MCMASTER_STOW) or hit("SOOW", MCMASTER_SOOW)
    if code == "SPT-1":
        return hit("SPT-1", MCMASTER_SPT1)
    return None


def awg_span(start: str, end: str) -> list[str]:
    return EVEN_AWG[EVEN_AWG.index(start) : EVEN_AWG.index(end) + 1]


def awg_numeric(gauge: str) -> int:
    """Sort key: 4/0 < 2 < 10 < 18."""
    if "/0" in gauge:
        return 1 - int(gauge.split("/")[0])
    return int(gauge)


def fmt_in(value: float) -> str:
    return f"{value:.3f}in"


def insulated_od(gauge: str, insulation_in: float) -> str:
    return fmt_in(AWG_OD[gauge] + 2.0 * insulation_in)


def conductor_appearance(color: str) -> dict:
    if color == "green":
        return {"base_color": "green", "parallelstripe": ["yellow"]}
    if color == "white":
        return {"base_color": "white", "outline_color": "black"}
    return {"base_color": color}


# Insulation / jacket wall, inches. estimate: typical UL 62 portable-cord
# walls by AWG class, not a single manufacturer table.
def sj_insulation_in(gauge: str) -> float:
    return 0.045 if awg_numeric(gauge) <= 10 else 0.030


def sj_jacket_in(gauge: str) -> float:
    n = awg_numeric(gauge)
    if n <= 10:
        return 0.060
    if n <= 12:
        return 0.045
    return 0.030


def s_insulation_in(gauge: str) -> float:
    n = awg_numeric(gauge)
    if n >= 16:
        return 0.030
    if n >= 10:
        return 0.045
    return 0.060


def s_jacket_in(gauge: str) -> float:
    n = awg_numeric(gauge)
    if n >= 16:
        return 0.060
    if n == 14:
        return 0.080
    if n >= 10:
        return 0.095
    if n == 8:
        return 0.125
    if n == 6:
        return 0.140
    if n == 4:
        return 0.155
    return 0.170


def w_insulation_in(gauge: str) -> float:
    return 0.080 if awg_numeric(gauge) <= 0 else 0.060


def w_jacket_in(gauge: str) -> float:
    n = awg_numeric(gauge)
    if n >= 8:
        return 0.140
    if n >= 4:
        return 0.155
    if n >= 2:
        return 0.170
    if n >= 0:
        return 0.185
    if n >= -1:
        return 0.200
    if n >= -2:
        return 0.215
    return 0.230


# UL 62 letter-code families commonly sold as portable cord.
# https://www.mcmaster.com/products/portable-cord/
CABLE_TYPES = [
    {
        "code": "SPT-1",
        "name": "Service Parallel Thermoplastic, 0.030\" Insulation",
        "gauges": ["18"],
        "conductors": [2, 3],
        "insulation_material": "pvc",
        "jacket_material": None,
        "jacketed": False,
        "construction": "parallel",
        "voltage": "300 V AC",
        "usage": "Indoor Use Only",
        "insulation_in": lambda _g: 0.030,
        "jacket_in": lambda _g: 0.0,
        "jacket_color": None,
    },
    {
        "code": "SPT-2",
        "name": "Service Parallel Thermoplastic, 0.045\" Insulation",
        "gauges": awg_span("18", "16"),
        "conductors": [2, 3],
        "insulation_material": "pvc",
        "jacket_material": None,
        "jacketed": False,
        "construction": "parallel",
        "voltage": "300 V AC",
        "usage": "Indoor Use Only",
        "insulation_in": lambda _g: 0.045,
        "jacket_in": lambda _g: 0.0,
        "jacket_color": None,
    },
    {
        "code": "SPT-3",
        "name": "Service Parallel Thermoplastic, 0.060\" Insulation",
        "gauges": awg_span("18", "10"),
        "conductors": [2, 3],
        "insulation_material": "pvc",
        "jacket_material": None,
        "jacketed": False,
        "construction": "parallel",
        "voltage": "300 V AC",
        "usage": "Indoor Use Only",
        "insulation_in": lambda _g: 0.060,
        "jacket_in": lambda _g: 0.0,
        "jacket_color": None,
    },
    {
        "code": "SVT",
        "name": "Service Vacuum Thermoplastic",
        "gauges": ["18", "17"],
        "conductors": [2, 3],
        "insulation_material": "pvc",
        "jacket_material": "pvc",
        "jacketed": True,
        "construction": "round",
        "voltage": "300 V AC",
        "usage": "Light Usage Indoors",
        "insulation_in": lambda _g: 0.015,
        "jacket_in": lambda _g: 0.015,
        "jacket_color": "gray",
    },
    {
        "code": "SJT",
        "name": "Service Junior Thermoplastic",
        "gauges": awg_span("18", "10"),
        "conductors": [2, 3, 4],
        "insulation_material": "pvc",
        "jacket_material": "pvc",
        "jacketed": True,
        "construction": "round",
        "voltage": "300 V AC",
        "usage": "Hard Usage Indoors",
        "insulation_in": sj_insulation_in,
        "jacket_in": sj_jacket_in,
        "jacket_color": "black",
    },
    {
        "code": "SJTW",
        "name": "SJT, Weather-Resistant",
        "gauges": awg_span("18", "10"),
        "conductors": [2, 3, 4],
        "insulation_material": "pvc",
        "jacket_material": "pvc",
        "jacketed": True,
        "construction": "round",
        "voltage": "300 V AC",
        "usage": "Hard Usage Outdoors",
        "insulation_in": sj_insulation_in,
        "jacket_in": sj_jacket_in,
        "jacket_color": "black",
        "weather_resistant": True,
    },
    {
        "code": "SJTO",
        "name": "SJT, Oil-Resistant Jacket",
        "gauges": awg_span("18", "10"),
        "conductors": [2, 3, 4],
        "insulation_material": "pvc",
        "jacket_material": "pvc",
        "jacketed": True,
        "construction": "round",
        "voltage": "300 V AC",
        "usage": "Hard Usage Indoors",
        "insulation_in": sj_insulation_in,
        "jacket_in": sj_jacket_in,
        "jacket_color": "black",
        "oil_resistant_jacket": True,
    },
    {
        "code": "SJTOW",
        "name": "SJT, Oil- & Weather-Resistant Jacket",
        "gauges": awg_span("18", "10"),
        "conductors": [2, 3, 4],
        "insulation_material": "pvc",
        "jacket_material": "pvc",
        "jacketed": True,
        "construction": "round",
        "voltage": "300 V AC",
        "usage": "Hard Usage Outdoors",
        "insulation_in": sj_insulation_in,
        "jacket_in": sj_jacket_in,
        "jacket_color": "black",
        "oil_resistant_jacket": True,
        "weather_resistant": True,
    },
    {
        "code": "SJTOOW",
        "name": "SJT, Oil-Resistant Insulation, Oil- & Weather-Resistant Jacket",
        "gauges": awg_span("18", "10"),
        "conductors": [2, 3, 4],
        "insulation_material": "pvc",
        "jacket_material": "pvc",
        "jacketed": True,
        "construction": "round",
        "voltage": "300 V AC",
        "usage": "Extra Hard Usage Outdoors",
        "insulation_in": sj_insulation_in,
        "jacket_in": sj_jacket_in,
        "jacket_color": "black",
        "oil_resistant_insulation": True,
        "oil_resistant_jacket": True,
        "weather_resistant": True,
    },
    {
        "code": "S",
        "name": "Service",
        "gauges": awg_span("18", "2"),
        "conductors": [2, 3, 4],
        "insulation_material": "rubber",
        "jacket_material": "rubber",
        "jacketed": True,
        "construction": "round",
        "voltage": "600 V AC",
        "usage": "Extra Hard Usage Indoors",
        "insulation_in": s_insulation_in,
        "jacket_in": s_jacket_in,
        "jacket_color": "black",
    },
    {
        "code": "SO",
        "name": "Service, Oil-Resistant Jacket",
        "gauges": awg_span("18", "2"),
        "conductors": [2, 3, 4],
        "insulation_material": "rubber",
        "jacket_material": "neoprene",
        "jacketed": True,
        "construction": "round",
        "voltage": "600 V AC",
        "usage": "Extra Hard Usage Indoors",
        "insulation_in": s_insulation_in,
        "jacket_in": s_jacket_in,
        "jacket_color": "black",
        "oil_resistant_jacket": True,
    },
    {
        "code": "SOO",
        "name": "Service, Oil-Resistant Insulation & Jacket",
        "gauges": awg_span("18", "2"),
        "conductors": [2, 3, 4],
        "insulation_material": "rubber",
        "jacket_material": "neoprene",
        "jacketed": True,
        "construction": "round",
        "voltage": "600 V AC",
        "usage": "Extra Hard Usage Indoors",
        "insulation_in": s_insulation_in,
        "jacket_in": s_jacket_in,
        "jacket_color": "black",
        "oil_resistant_insulation": True,
        "oil_resistant_jacket": True,
    },
    {
        "code": "SOOW",
        "name": "Service, Oil-Resistant Insulation & Jacket, Weather-Resistant",
        "gauges": awg_span("18", "2"),
        "conductors": [2, 3, 4],
        "insulation_material": "rubber",
        "jacket_material": "neoprene",
        "jacketed": True,
        "construction": "round",
        "voltage": "600 V AC",
        "usage": "Extra Hard Usage Outdoors",
        "insulation_in": s_insulation_in,
        "jacket_in": s_jacket_in,
        "jacket_color": "black",
        "oil_resistant_insulation": True,
        "oil_resistant_jacket": True,
        "weather_resistant": True,
    },
    {
        "code": "ST",
        "name": "Service Thermoplastic",
        "gauges": awg_span("18", "2"),
        "conductors": [2, 3, 4],
        "insulation_material": "pvc",
        "jacket_material": "pvc",
        "jacketed": True,
        "construction": "round",
        "voltage": "600 V AC",
        "usage": "Extra Hard Usage Indoors",
        "insulation_in": s_insulation_in,
        "jacket_in": s_jacket_in,
        "jacket_color": "black",
    },
    {
        "code": "STW",
        "name": "ST, Weather-Resistant Jacket",
        "gauges": awg_span("18", "2"),
        "conductors": [2, 3, 4],
        "insulation_material": "pvc",
        "jacket_material": "pvc",
        "jacketed": True,
        "construction": "round",
        "voltage": "600 V AC",
        "usage": "Extra Hard Usage Outdoors",
        "insulation_in": s_insulation_in,
        "jacket_in": s_jacket_in,
        "jacket_color": "black",
        "weather_resistant": True,
    },
    {
        "code": "STO",
        "name": "ST, Oil-Resistant Jacket",
        "gauges": awg_span("18", "2"),
        "conductors": [2, 3, 4],
        "insulation_material": "pvc",
        "jacket_material": "pvc",
        "jacketed": True,
        "construction": "round",
        "voltage": "600 V AC",
        "usage": "Extra Hard Usage Indoors",
        "insulation_in": s_insulation_in,
        "jacket_in": s_jacket_in,
        "jacket_color": "black",
        "oil_resistant_jacket": True,
    },
    {
        "code": "SRDT",
        "name": "Service Round Dry Thermoplastic (flat or round)",
        "gauges": awg_span("10", "6"),
        "conductors": [3, 4],
        "insulation_material": "pvc",
        "jacket_material": "pvc",
        "jacketed": True,
        "construction": "round",
        "voltage": "600 V AC",
        "usage": "Electric Range and Dryer Cords",
        "insulation_in": s_insulation_in,
        "jacket_in": s_jacket_in,
        "jacket_color": "gray",
    },
    {
        "code": "W",
        "name": "Power Supply Cable",
        "gauges": awg_span("8", "4/0"),
        "conductors": [2, 3, 4, 5],
        "insulation_material": "epdm",
        "jacket_material": "super vu-tron",
        "jacketed": True,
        "construction": "round",
        "voltage": "2000 V AC",
        "usage": "Extra Hard Usage Outdoors",
        "insulation_in": w_insulation_in,
        "jacket_in": w_jacket_in,
        "jacket_color": "yellow",
        "weather_resistant": True,
    },
]

_TYPES_BY_CODE = {spec["code"]: spec for spec in CABLE_TYPES}

_PN_RE = re.compile(
    r"^(?P<code>[A-Z]+(?:-\d+)?)"
    r"[-_ ]"
    r"(?P<gauge>\d+(?:[_/]\d+)?)"
    r"[-_ ]"
    r"(?P<n>\d+)\s*C?$",
    re.IGNORECASE,
)


def iter_part_configurations():
    for spec in CABLE_TYPES:
        for gauge in spec["gauges"]:
            for n in spec["conductors"]:
                yield {"spec": spec, "gauge": gauge, "n_conductors": n}


def make_part_number(cfg: dict) -> str:
    gauge = cfg["gauge"].replace("/", "_")
    return f"{cfg['spec']['code']}-{gauge}-{cfg['n_conductors']}C"


def official_pin(cfg: dict) -> str:
    return make_part_number(cfg)


def description_from_cfg(cfg: dict) -> str:
    spec = cfg["spec"]
    return (
        f"CABLE, PORTABLE POWER, {spec['code']}, "
        f"{cfg['gauge']} AWG, {cfg['n_conductors']} CONDUCTOR, {spec['voltage']}"
    )


def choose_part(cable_type, gauge=None, conductors=None, n_conductors=None):
    """
    Choose a portable-power-cable SKU that exists in this library.

    cable_type:
      UL letter code (SOOW, SJT, SPT-1, W, …) or a full library PN.
    gauge:
      AWG as 14, "14", "1/0", "1_0". Ignored when cable_type is a full PN.
    conductors / n_conductors:
      2..5. Ignored when cable_type is a full PN.

    Returns the library PN. Raises ValueError if that combo is not sold here.
    """
    text = str(cable_type).strip()
    if _looks_like_pn(text) and gauge is None and conductors is None and n_conductors is None:
        return parse_portable_power_cable(text)["mpn"]
    if conductors is None:
        conductors = n_conductors
    if _looks_like_pn(text) and gauge is not None and conductors is not None:
        parsed = parse_portable_power_cable(text)
        gauge = parsed["gauge"]
        conductors = parsed["n_conductors"]
        text = parsed["spec"]["code"]
    if gauge is None or conductors is None:
        raise ValueError(
            "choose_part requires cable_type, gauge, and conductors "
            "(or a full PN like SOOW-14-3C)."
        )
    code = _normalize_code(text)
    gauge = _normalize_gauge(gauge)
    n = int(conductors)
    spec = _TYPES_BY_CODE[code]
    if gauge not in spec["gauges"] or n not in spec["conductors"]:
        raise ValueError(
            f"No {code} cable for {gauge} AWG / {n} conductor in this library. "
            f"Legal gauges: {', '.join(spec['gauges'])}. "
            f"Legal conductor counts: {', '.join(str(c) for c in spec['conductors'])}."
        )
    return make_part_number({"spec": spec, "gauge": gauge, "n_conductors": n})


def parse_portable_power_cable(part_number):
    """Parse a library PN into spec / gauge / conductor count."""
    text = str(part_number).strip()
    match = _PN_RE.match(text.replace(" ", ""))
    if not match:
        raise ValueError(
            f"Could not parse {part_number!r} as portable power cable. "
            "Expected SOOW-14-3C or SPT-1-18-2C."
        )
    code = _normalize_code(match.group("code"))
    gauge = _normalize_gauge(match.group("gauge"))
    n = int(match.group("n"))
    spec = _TYPES_BY_CODE[code]
    if gauge not in spec["gauges"] or n not in spec["conductors"]:
        raise ValueError(
            f"{part_number!r} is not a SKU in this library. "
            f"Legal {code} PNs: {', '.join(list_parts(code))}."
        )
    cfg = {"spec": spec, "gauge": gauge, "n_conductors": n}
    cfg["mpn"] = make_part_number(cfg)
    return cfg


def list_parts(cable_type=None):
    """Library PNs, optionally filtered by UL letter code."""
    code = _normalize_code(cable_type) if cable_type is not None else None
    out = []
    for cfg in iter_part_configurations():
        if code is not None and cfg["spec"]["code"] != code:
            continue
        out.append(make_part_number(cfg))
    return out


def list_types():
    return [spec["code"] for spec in CABLE_TYPES]


CATALOG_COLUMNS = (
    "library_pn",
    "type",
    "name",
    "description",
    "gauge_awg",
    "conductors",
    "conductor_colors",
    "voltage",
    "usage",
    "construction",
    "jacketed",
    "jacket_material",
    "jacket_color",
    "jacket_thickness",
    "insulation_material",
    "insulation_thickness",
    "conductor_od",
    "stranding",
    "conductor_material",
    "oil_resistant_jacket",
    "oil_resistant_insulation",
    "weather_resistant",
    "mcmaster_pn",
    "mcmaster_designation",
    "mcmaster_url",
    "mfg",
    "library_subpath",
)


def catalog_row(cfg: dict) -> dict:
    spec = cfg["spec"]
    gauge = cfg["gauge"]
    n = cfg["n_conductors"]
    pn = make_part_number(cfg)
    mcmaster = mcmaster_part(spec["code"], gauge, n) or {}
    insulation_in = spec["insulation_in"](gauge)
    jacket_in = spec["jacket_in"](gauge)
    return {
        "library_pn": pn,
        "type": spec["code"],
        "name": spec["name"],
        "description": description_from_cfg(cfg),
        "gauge_awg": gauge,
        "conductors": n,
        "conductor_colors": ", ".join(CONDUCTOR_COLORS[n]),
        "voltage": spec["voltage"],
        "usage": spec["usage"],
        "construction": spec["construction"],
        "jacketed": spec["jacketed"],
        "jacket_material": spec["jacket_material"] or "",
        "jacket_color": spec["jacket_color"] or "",
        "jacket_thickness": fmt_in(jacket_in) if jacket_in else "",
        "insulation_material": spec["insulation_material"],
        "insulation_thickness": fmt_in(insulation_in),
        "conductor_od": insulated_od(gauge, insulation_in),
        "stranding": CLASS_K_STRANDING[gauge],
        "conductor_material": "copper",
        "oil_resistant_jacket": bool(spec.get("oil_resistant_jacket")),
        "oil_resistant_insulation": bool(spec.get("oil_resistant_insulation")),
        "weather_resistant": bool(spec.get("weather_resistant")),
        "mcmaster_pn": mcmaster.get("pn", ""),
        "mcmaster_designation": mcmaster.get("designation", ""),
        "mcmaster_url": mcmaster.get("url", ""),
        "mfg": "McMaster-Carr" if mcmaster else "",
        "library_subpath": LIBRARY_SUBPATH,
    }


def _looks_like_pn(value: str) -> bool:
    return bool(_PN_RE.match(str(value).strip().replace(" ", "")))


def _normalize_code(value: str) -> str:
    text = str(value).strip().upper().replace("_", "-")
    if text not in _TYPES_BY_CODE:
        raise ValueError(
            f"Unknown portable-cord type {value!r}. "
            f"This library has: {', '.join(list_types())}."
        )
    return text


def _normalize_gauge(value) -> str:
    text = str(value).strip().upper().replace("_", "/")
    if text.endswith("AWG"):
        text = text[:-3].strip()
    if text.isdigit():
        text = str(int(text))
    if text not in AWG_OD:
        raise ValueError(f"Unknown wire gauge {value!r}.")
    return text
