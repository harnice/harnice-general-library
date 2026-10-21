import csv
import json
import os

from harnice import state
from harnice.lists import rev_history

REVISION = "1"
DATE_STARTED = "8/18/26"
LIBRARY_REPO = "https://github.com/harnice/harnice-general-library"
LIBRARY_SUBPATH = "cables/portable_power_cable/"

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Cable types called out in the article
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Attribute compilation
# ---------------------------------------------------------------------------

def build_configurations() -> list[dict]:
    configs = []
    for spec in CABLE_TYPES:
        for gauge in spec["gauges"]:
            for n in spec["conductors"]:
                configs.append({"spec": spec, "gauge": gauge, "n_conductors": n})
    return configs


def part_number_from_cfg(cfg: dict) -> str:
    gauge = cfg["gauge"].replace("/", "_")
    return f"{cfg['spec']['code']}-{gauge}-{cfg['n_conductors']}C"


def description_from_cfg(cfg: dict) -> str:
    spec = cfg["spec"]
    return (
        f"PORTABLE POWER CABLE, {spec['code']}, "
        f"{cfg['gauge']} AWG, {cfg['n_conductors']} CONDUCTOR, {spec['voltage']}"
    ).upper()


def compile_cable_attributes(cfg: dict) -> dict:
    spec = cfg["spec"]
    gauge = cfg["gauge"]
    n = cfg["n_conductors"]
    insulation_in = spec["insulation_in"](gauge)
    jacket_in = spec["jacket_in"](gauge)

    conductors = {}
    for color in CONDUCTOR_COLORS[n]:
        conductors[color] = {
            "conductor": True,
            "properties": {
                "insulation material": spec["insulation_material"],
                "od": insulated_od(gauge, insulation_in),
                "gauge": f"{gauge}AWG",
                "construction": CLASS_K_STRANDING[gauge],
                "material": "copper",
            },
            "appearance": conductor_appearance(color),
        }
        if spec.get("oil_resistant_insulation"):
            conductors[color]["properties"]["oil resistant"] = True

    jacket_properties = {
        "construction": spec["construction"],
        "voltage": spec["voltage"],
        "usage": spec["usage"],
        "type": spec["code"],
        "jacketed": spec["jacketed"],
    }
    if spec["jacket_material"]:
        jacket_properties["material"] = spec["jacket_material"]
    if spec["jacket_color"]:
        jacket_properties["color"] = spec["jacket_color"]
    if jacket_in:
        jacket_properties["thickness"] = fmt_in(jacket_in)
    for flag in (
        "oil_resistant_jacket",
        "oil_resistant_insulation",
        "weather_resistant",
    ):
        if spec.get(flag):
            jacket_properties[flag.replace("_", " ")] = True

    return {"jacket": {**{"properties": jacket_properties}, **conductors}}


CSV_COLUMNS = [
    "pn",
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
    "mfg",
    "library_subpath",
]


def csv_row_from_cfg(cfg: dict) -> dict:
    spec = cfg["spec"]
    gauge = cfg["gauge"]
    n = cfg["n_conductors"]
    pn = part_number_from_cfg(cfg)
    insulation_in = spec["insulation_in"](gauge)
    jacket_in = spec["jacket_in"](gauge)
    return {
        "pn": pn,
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
        "mfg": "",
        "library_subpath": LIBRARY_SUBPATH,
    }


def write_family_csv(configs: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(csv_row_from_cfg(cfg) for cfg in configs)


def write_conductor_list(attrs: dict, path: str) -> int:
    """Walk the attributes tree the same way harnice.project_types.cable.build does."""
    rows = []
    all_headers = {"appearance"}

    def recurse(obj, parent_chain=None):
        if parent_chain is None:
            parent_chain = []
        if isinstance(obj, dict):
            if obj.get("conductor") is True:
                props = obj.get("properties", {})
                appearance = obj.get("appearance", {})
                container = parent_chain[-2] if len(parent_chain) >= 2 else ""
                identifier = parent_chain[-1] if len(parent_chain) >= 1 else ""
                row = {"container": container, "identifier": identifier}
                for k, v in props.items():
                    row[k] = v
                    all_headers.add(k)
                row["appearance"] = (
                    json.dumps(
                        appearance, separators=(",", ":"), ensure_ascii=False
                    ).replace('"', "'")
                    if appearance
                    else ""
                )
                rows.append(row)
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    recurse(v, parent_chain + [k])
        elif isinstance(obj, list):
            for item in obj:
                recurse(item, parent_chain)

    recurse(attrs)
    headers = ["container", "identifier"] + sorted(all_headers)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=headers, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    state.set_rev(REVISION)
    state.set_project_type("cable")

    family_dir = os.path.dirname(os.path.abspath(__file__))
    configs = build_configurations()
    print(f"Building {len(configs)} portable power cables in {family_dir}")

    for cfg in configs:
        pn = part_number_from_cfg(cfg)
        print(f"Preparing cable: {pn}")

        part_dir = os.path.join(family_dir, pn)
        os.makedirs(part_dir, exist_ok=True)

        rev_dir = os.path.join(part_dir, f"rev{REVISION}")
        if os.path.exists(rev_dir):
            for item in os.listdir(rev_dir):
                p = os.path.join(rev_dir, item)
                if os.path.isfile(p):
                    os.remove(p)
        else:
            os.makedirs(rev_dir)

        rev_history.part_family_append(
            {
                "project_type": state.project_type,
                "mfg": "",
                "pn": pn,
                "rev": REVISION,
                "desc": description_from_cfg(cfg),
                "status": "",
                "datestarted": DATE_STARTED,
                "library_repo": LIBRARY_REPO,
                "library_subpath": LIBRARY_SUBPATH,
                "revisionupdates": "INITIAL RELEASE",
            },
            os.path.join(part_dir, f"{pn}-revision_history.tsv"),
        )

        attributes = compile_cable_attributes(cfg)
        json_path = os.path.join(rev_dir, "attributes.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(attributes, f, indent=4)
            f.write("\n")

        tsv_path = os.path.join(rev_dir, "conductors.tsv")
        write_conductor_list(attributes, tsv_path)

    csv_path = os.path.join(family_dir, "portable_power_cable.csv")
    write_family_csv(configs, csv_path)

    print(f"Finished building {len(configs)} portable power cables.")
    print(f"Wrote family catalog: {csv_path}")


if __name__ == "__main__":
    main()
