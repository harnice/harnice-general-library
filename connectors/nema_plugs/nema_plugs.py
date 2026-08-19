"""NEMA WD-6 power plugs and cord connectors.

Chooser API for the library in this folder. Configurations are the commercially
available grounded (plus still-common 10-series dryer) NEMA wiring devices:
straight-blade 5 / 6 / 7 / 10 / 14 / 15 / TT-30, and locking L5–L9, L14–L17,
L21–L26.

Library PNs: NEMA-5-15P, NEMA-L14-30R, NEMA-TT-30P.
Official WD-6 names drop the NEMA- prefix (5-15P, L14-30R, TT-30P).
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Families
# ---------------------------------------------------------------------------
#
# Contact letters follow ANSI/NEMA WD-6: G ground, W grounded neutral,
# X/Y/Z ungrounded hots. Amp lists are the ratings that are actually
# manufactured (reserved / never-tooled series are omitted).

FAMILIES = [
    {
        "series": "5",
        "locking": False,
        "voltage": "125 V AC",
        "system": "hot-neutral-ground",
        "poles": 2,
        "wires": 3,
        "grounded": True,
        "contacts": ["X", "W", "G"],
        "amps": [15, 20, 30, 50],
        "common_name": "2-pole 3-wire grounding, 125 V",
    },
    {
        "series": "6",
        "locking": False,
        "voltage": "250 V AC",
        "system": "hot-hot-ground",
        "poles": 2,
        "wires": 3,
        "grounded": True,
        "contacts": ["X", "Y", "G"],
        "amps": [15, 20, 30, 50],
        "common_name": "2-pole 3-wire grounding, 250 V",
    },
    {
        "series": "7",
        "locking": False,
        "voltage": "277 V AC",
        "system": "hot-neutral-ground",
        "poles": 2,
        "wires": 3,
        "grounded": True,
        "contacts": ["X", "W", "G"],
        "amps": [15, 20, 30, 50],
        "common_name": "2-pole 3-wire grounding, 277 V",
    },
    {
        "series": "10",
        "locking": False,
        "voltage": "125/250 V AC",
        "system": "hot-hot-neutral",
        "poles": 3,
        "wires": 3,
        "grounded": False,
        "contacts": ["X", "Y", "W"],
        "amps": [20, 30, 50],
        "common_name": "3-pole 3-wire ungrounded, 125/250 V (deprecated dryer/range)",
    },
    {
        "series": "14",
        "locking": False,
        "voltage": "125/250 V AC",
        "system": "hot-hot-neutral-ground",
        "poles": 3,
        "wires": 4,
        "grounded": True,
        "contacts": ["X", "Y", "W", "G"],
        "amps": [15, 20, 30, 50, 60],
        "common_name": "3-pole 4-wire grounding, 125/250 V",
    },
    {
        "series": "15",
        "locking": False,
        "voltage": "250 V AC 3Φ",
        "system": "3-phase delta hot-hot-hot-ground",
        "poles": 3,
        "wires": 4,
        "grounded": True,
        "contacts": ["X", "Y", "Z", "G"],
        "amps": [15, 20, 30, 50, 60],
        "common_name": "3-pole 4-wire grounding, 3-phase 250 V",
    },
    {
        "series": "TT",
        "locking": False,
        "voltage": "125 V AC",
        "system": "hot-neutral-ground",
        "poles": 2,
        "wires": 3,
        "grounded": True,
        "contacts": ["X", "W", "G"],
        "amps": [30],
        "common_name": "Travel Trailer 2-pole 3-wire grounding, 125 V",
    },
    {
        "series": "5",
        "locking": True,
        "voltage": "125 V AC",
        "system": "hot-neutral-ground",
        "poles": 2,
        "wires": 3,
        "grounded": True,
        "contacts": ["X", "W", "G"],
        "amps": [15, 20, 30],
        "common_name": "locking 2-pole 3-wire grounding, 125 V",
    },
    {
        "series": "6",
        "locking": True,
        "voltage": "250 V AC",
        "system": "hot-hot-ground",
        "poles": 2,
        "wires": 3,
        "grounded": True,
        "contacts": ["X", "Y", "G"],
        "amps": [15, 20, 30],
        "common_name": "locking 2-pole 3-wire grounding, 250 V",
    },
    {
        "series": "7",
        "locking": True,
        "voltage": "277 V AC",
        "system": "hot-neutral-ground",
        "poles": 2,
        "wires": 3,
        "grounded": True,
        "contacts": ["X", "W", "G"],
        "amps": [15, 20, 30],
        "common_name": "locking 2-pole 3-wire grounding, 277 V",
    },
    {
        "series": "8",
        "locking": True,
        "voltage": "480 V AC",
        "system": "hot-hot-ground",
        "poles": 2,
        "wires": 3,
        "grounded": True,
        "contacts": ["X", "Y", "G"],
        "amps": [20, 30],
        "common_name": "locking 2-pole 3-wire grounding, 480 V",
    },
    {
        "series": "9",
        "locking": True,
        "voltage": "600 V AC",
        "system": "hot-hot-ground",
        "poles": 2,
        "wires": 3,
        "grounded": True,
        "contacts": ["X", "Y", "G"],
        "amps": [20, 30],
        "common_name": "locking 2-pole 3-wire grounding, 600 V",
    },
    {
        "series": "14",
        "locking": True,
        "voltage": "125/250 V AC",
        "system": "hot-hot-neutral-ground",
        "poles": 3,
        "wires": 4,
        "grounded": True,
        "contacts": ["X", "Y", "W", "G"],
        "amps": [20, 30],
        "common_name": "locking 3-pole 4-wire grounding, 125/250 V",
    },
    {
        "series": "15",
        "locking": True,
        "voltage": "250 V AC 3Φ",
        "system": "3-phase delta hot-hot-hot-ground",
        "poles": 3,
        "wires": 4,
        "grounded": True,
        "contacts": ["X", "Y", "Z", "G"],
        "amps": [20, 30],
        "common_name": "locking 3-pole 4-wire grounding, 3-phase 250 V",
    },
    {
        "series": "16",
        "locking": True,
        "voltage": "480 V AC 3Φ",
        "system": "3-phase delta hot-hot-hot-ground",
        "poles": 3,
        "wires": 4,
        "grounded": True,
        "contacts": ["X", "Y", "Z", "G"],
        "amps": [20, 30],
        "common_name": "locking 3-pole 4-wire grounding, 3-phase 480 V",
    },
    {
        "series": "17",
        "locking": True,
        "voltage": "600 V AC 3Φ",
        "system": "3-phase delta hot-hot-hot-ground",
        "poles": 3,
        "wires": 4,
        "grounded": True,
        "contacts": ["X", "Y", "Z", "G"],
        "amps": [30],
        "common_name": "locking 3-pole 4-wire grounding, 3-phase 600 V",
    },
    {
        "series": "21",
        "locking": True,
        "voltage": "120/208 V AC 3ΦY",
        "system": "3-phase wye hot-hot-hot-neutral-ground",
        "poles": 4,
        "wires": 5,
        "grounded": True,
        "contacts": ["X", "Y", "Z", "W", "G"],
        "amps": [20, 30],
        "common_name": "locking 4-pole 5-wire grounding, 3-phase 120/208 Y",
    },
    {
        "series": "22",
        "locking": True,
        "voltage": "277/480 V AC 3ΦY",
        "system": "3-phase wye hot-hot-hot-neutral-ground",
        "poles": 4,
        "wires": 5,
        "grounded": True,
        "contacts": ["X", "Y", "Z", "W", "G"],
        "amps": [20, 30],
        "common_name": "locking 4-pole 5-wire grounding, 3-phase 277/480 Y",
    },
    {
        "series": "23",
        "locking": True,
        "voltage": "347/600 V AC 3ΦY",
        "system": "3-phase wye hot-hot-hot-neutral-ground",
        "poles": 4,
        "wires": 5,
        "grounded": True,
        "contacts": ["X", "Y", "Z", "W", "G"],
        "amps": [20, 30],
        "common_name": "locking 4-pole 5-wire grounding, 3-phase 347/600 Y",
    },
    {
        "series": "24",
        "locking": True,
        "voltage": "347 V AC",
        "system": "hot-neutral-ground",
        "poles": 2,
        "wires": 3,
        "grounded": True,
        "contacts": ["X", "W", "G"],
        "amps": [20, 30],
        "common_name": "locking 2-pole 3-wire grounding, 347 V",
    },
    {
        "series": "25",
        "locking": True,
        "voltage": "240 V AC",
        "system": "hot-neutral-ground",
        "poles": 2,
        "wires": 3,
        "grounded": True,
        "contacts": ["X", "W", "G"],
        "amps": [30],
        "common_name": "locking 2-pole 3-wire grounding, 240 V (IT line-neutral)",
    },
    {
        "series": "26",
        "locking": True,
        "voltage": "240/415 V AC 3ΦY",
        "system": "3-phase wye hot-hot-hot-neutral-ground",
        "poles": 4,
        "wires": 5,
        "grounded": True,
        "contacts": ["X", "Y", "Z", "W", "G"],
        "amps": [20, 30],
        "common_name": "locking 4-pole 5-wire grounding, 3-phase 240/415 Y",
    },
]

GENDERS = {
    "P": {
        "name": "Plug",
        "contacts": "pin",
        "mounting": "cord cap",
    },
    "R": {
        "name": "Connector",
        "contacts": "socket",
        "mounting": "cord connector",
    },
}

# 20 A T-slot receptacles that also accept the 15 A plug of the same series.
T_SLOT_RECEPTACLES = {
    "5-20": ["5-15", "5-20"],
    "6-20": ["6-15", "6-20"],
}

_MAX_AWG = {15: "14", 20: "12", 30: "10", 50: "6", 60: "4"}

_PN_RE = re.compile(
    r"^(?:NEMA-)?(?P<config>L?\d+|TT)-(?P<amps>\d+)(?P<gender>P|R|C|M|F)?$",
    re.IGNORECASE,
)

_GENDER_ALIASES = {
    "P": "P",
    "PLUG": "P",
    "MALE": "P",
    "M": "P",
    "PIN": "P",
    "R": "R",
    "RECEPTACLE": "R",
    "CONNECTOR": "R",
    "JACK": "R",
    "FEMALE": "R",
    "F": "R",
    "SOCKET": "R",
    "C": "R",
}


def config_id(family: dict, amps: int) -> str:
    if family["series"] == "TT":
        return f"TT-{amps}"
    prefix = "L" if family["locking"] else ""
    return f"{prefix}{family['series']}-{amps}"


def make_part_number(config: str, gender: str) -> str:
    return f"NEMA-{config}{gender}"


def official_name(config: str, gender: str) -> str:
    return f"{config}{gender}"


def max_wire_awg(amps: int) -> str:
    try:
        return _MAX_AWG[amps]
    except KeyError as exc:
        raise ValueError(f"Unsupported current rating {amps} A") from exc


def _index_configs() -> dict[str, dict]:
    out = {}
    for family in FAMILIES:
        for amps in family["amps"]:
            cid = config_id(family, amps)
            out[cid] = {
                **family,
                "config": cid,
                "amps": amps,
                "max_wire_awg": max_wire_awg(amps),
            }
    return out


CONFIGS = _index_configs()


def iter_part_configurations():
    for cid, spec in CONFIGS.items():
        for gender in GENDERS:
            yield {
                "config": cid,
                "gender": gender,
                "spec": spec,
            }


def description_from_cfg(cfg: dict) -> str:
    spec = cfg["spec"]
    gender = GENDERS[cfg["gender"]]
    locking = "LOCKING, " if spec["locking"] else ""
    return (
        f"CONNECTOR, NEMA {official_name(cfg['config'], cfg['gender'])}, "
        f"{locking}{spec['voltage']}, {spec['amps']} A, {gender['name']}"
    ).upper()


# ---------------------------------------------------------------------------
# Chooser
# ---------------------------------------------------------------------------

def choose_part(config, gender="P", return_divider=None):
    """
    Choose a NEMA power connector that exists in this library.

    config:
      WD-6 configuration, with or without gender suffix.
      Examples: "5-15", "L14-30", "TT-30", "NEMA-L5-20P", "5-15P"

    gender:
      P / plug / male     — cord-cap plug (blades)
      R / receptacle / connector / female / C — cord connector (slots)

    return_divider:
      Default library PNs are NEMA-5-15P. Pass "" to return the official
      WD-6 name (5-15P). Other values are inserted after "NEMA".

    Returns:
      Library part number string, e.g. NEMA-L14-30P.
    """
    parsed = _parse_config_or_pn(config, default_gender=gender)
    _require_config(parsed["config"])
    if return_divider == "":
        return official_name(parsed["config"], parsed["gender"])
    if return_divider is None:
        return make_part_number(parsed["config"], parsed["gender"])
    return f"NEMA{return_divider}{parsed['config']}{parsed['gender']}"


def find_mating_connector(part_number, override_gender=None, return_divider=None):
    """
    Given a NEMA library or official PN, return the opposite-gender mate
    of the same configuration.

    Sample: NEMA-L14-30P  ->  NEMA-L14-30R

    T-slot receptacles (5-20R, 6-20R) also accept the 15 A plug of the
    same series; see compatible_mates().
    """
    parsed = parse_nema(part_number)
    gender = parsed["gender"]
    if override_gender is None:
        gender = "R" if gender == "P" else "P"
    else:
        gender = _normalize_gender(override_gender)
    return _format_pn(parsed["config"], gender, return_divider)


def compatible_mates(part_number):
    """
    All library PNs this connector can physically mate with.

    Includes the same-configuration opposite gender, plus 15 A plugs into
    20 A T-slot receptacles (5-20R, 6-20R).
    """
    parsed = parse_nema(part_number)
    cid = parsed["config"]
    gender = parsed["gender"]
    mates = []
    if gender == "P":
        mates.append(make_part_number(cid, "R"))
        for receptacle, plugs in T_SLOT_RECEPTACLES.items():
            if cid in plugs and cid != receptacle:
                mates.append(make_part_number(receptacle, "R"))
    else:
        mates.append(make_part_number(cid, "P"))
        for plug in T_SLOT_RECEPTACLES.get(cid, []):
            if plug != cid:
                mates.append(make_part_number(plug, "P"))
    return mates


def parse_nema(part_number):
    """Parse a library or official NEMA connector part number."""
    return _parse_config_or_pn(part_number, default_gender=None)


def list_configs():
    """WD-6 configuration ids in this library, e.g. ['5-15', 'L5-15', ...]."""
    return list(CONFIGS)


def _parse_config_or_pn(value, default_gender):
    text = str(value).strip().upper().replace(" ", "").replace("_", "-")
    match = _PN_RE.match(text)
    if not match:
        raise ValueError(
            f"Could not parse {value!r} as a NEMA connector. "
            "Expected 5-15, L14-30P, NEMA-TT-30R, etc."
        )
    cid = f"{match.group('config')}-{int(match.group('amps'))}"
    _require_config(cid)
    raw_gender = match.group("gender")
    if raw_gender:
        gender = _normalize_gender(raw_gender)
    elif default_gender is not None:
        gender = _normalize_gender(default_gender)
    else:
        raise ValueError(
            f"{value!r} has no gender suffix. Pass gender='P' or 'R', "
            "or a PN like NEMA-5-15P."
        )
    return {"config": cid, "gender": gender, "spec": CONFIGS[cid]}


def _require_config(cid: str) -> None:
    if cid not in CONFIGS:
        raise ValueError(
            f"Unknown NEMA configuration {cid!r}. "
            f"This library has: {', '.join(CONFIGS)}"
        )


def _normalize_gender(gender: str) -> str:
    key = str(gender).strip().upper().replace(" ", "").replace("-", "")
    if key not in _GENDER_ALIASES:
        raise ValueError(
            f"Unknown gender {gender!r}. Expected P/R, plug/connector, "
            "male/female, or pin/socket."
        )
    return _GENDER_ALIASES[key]


def _format_pn(config, gender, return_divider):
    if return_divider == "":
        return official_name(config, gender)
    if return_divider is None:
        return make_part_number(config, gender)
    return f"NEMA{return_divider}{config}{gender}"
