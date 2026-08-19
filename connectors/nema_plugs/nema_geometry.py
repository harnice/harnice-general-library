"""WD-6 face geometry and Hubbell Insulgrip envelopes.

PRIMARY SOURCES
---------------
    ANSI/NEMA WD 6-2002, Wiring Devices — Dimensional Specifications
        https://www.nema.org/Standards/view/Wiring-Devices-Dimensional-Specifications
        Mid-range values are used where WD-6 gives a min/max.

        p16   Flanged inlet / connector-body diameters A, B, C
        p24   Fig 5-15
        p25   Fig 5-20
        p27   Fig 5-30
        p28   Fig 5-50
        p29   Fig 6-15
        p30   Fig 6-20
        p32   Fig 6-30
        p34   Fig 7-15
        p35   Fig 7-20
        p37   Fig 7-50
        p42   Fig 10-20
        p43   Fig 10-30
        p49   Fig 14-15
        p50   Fig 14-20
        p51   Fig 14-30
        p52   Fig 14-50
        p54   Fig 15-15
        p66   Fig L5-15
        p67   Fig L5-20
        p68   Fig L5-30

    Hubbell Wiring Device-Kellems catalog (typical nylon cord-cap housing;
    WD-6 does not specify the rear body):
        HBL5266C  5-15P     1.53 in dia × 1.97 in long
        HBL5269C  5-15R     1.53 in dia × 2.78 in long
        HBL2311   L5-20P    2.26 × 2.26 × 2.75 in
        HBL2611   L5-30P    2.26 × 2.26 × 2.75 in
        HBL2411   L14-20P   2.33 × 2.33 × 2.75 in
        HBL9431C  14-30P    4.50 × 2.37 × 3.38 in
        HBL9451C  14-50P    4.50 × 2.38 × 3.38 in

Face coordinates (inches):
    Origin at the mating-face center.
    +Z is WD-6 "up" (ground at the top on the 5-15 / 6-15 figures).
    +Y is right when looking at the plug face (pins toward the viewer).
    Plug blades protrude +X from the face in the STEP envelope.
"""

from __future__ import annotations

import math


def _mid(lo, hi):
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# WD-6 p16 connector-body / inlet groups
# ---------------------------------------------------------------------------

_SMALL = {
    "5-15", "5-20", "6-15", "6-20", "7-15", "14-15", "15-15",
    "L5-15", "L6-15", "L7-15", "L24-20",
}
_MEDIUM = {"7-20", "10-20", "14-20", "15-20"}
_LOCK_20_3W = {
    "L5-20", "L6-20", "L7-20", "L8-20", "L9-20",
}
_LOCK_30_3W = {
    "L5-30", "L6-30", "L7-30", "L8-30", "L9-30", "L24-30", "L25-30",
}
_LOCK_20_45W = {
    "L14-20", "L15-20", "L16-20", "L21-20", "L22-20", "L23-20", "L26-20",
}
_LOCK_30_45W = {
    "L14-30", "L15-30", "L16-30", "L17-30",
    "L21-30", "L22-30", "L23-30", "L26-30",
}

WD6_P16 = {
    "small_straight": {"A": 1.550, "C": 1.531, "B": 0.843},
    "medium_straight": {"A": 2.030, "C": 2.010, "B": 0.875},
    "large_straight": {"A": 2.620, "C": 2.600, "B": 1.406},
    "lock_20_3w": {"A": 1.880, "C": 1.860, "B": 0.921},
    "lock_30_3w": {"A": 1.880, "C": 1.860, "B": 1.000},
    "lock_20_45w": {"A": 2.000, "C": 1.980, "B": 0.921},
    "lock_30_45w": {"A": 2.000, "C": 1.980, "B": 1.000},
}


def wd6_group(spec: dict) -> str:
    cid = spec["config"]
    if cid in _SMALL:
        return "small_straight"
    if cid in _MEDIUM:
        return "medium_straight"
    if spec["locking"]:
        n = len(spec["contacts"])
        if cid in _LOCK_20_45W or (n >= 4 and spec["amps"] <= 20):
            return "lock_20_45w"
        if cid in _LOCK_30_45W or n >= 4:
            return "lock_30_45w"
        if spec["amps"] <= 20 or cid in _LOCK_20_3W:
            return "lock_20_3w"
        return "lock_30_3w"
    return "large_straight"


def face_diameter(spec: dict) -> float:
    return WD6_P16[wd6_group(spec)]["C"]


def inlet_recess(spec: dict) -> float:
    return WD6_P16[wd6_group(spec)]["B"]


def housing(spec: dict, gender: str) -> dict:
    """Typical nylon cord-cap body. Length is housing only (no blades)."""
    group = wd6_group(spec)
    face = face_diameter(spec)
    if group == "small_straight":
        body_len = 1.97 if gender == "P" else 2.78
        body_dia = 1.53
    elif group == "medium_straight":
        body_len = 2.20 if gender == "P" else 2.90
        body_dia = 2.01
    elif group == "large_straight":
        body_len = 3.38 if gender == "P" else 3.80
        body_dia = 2.38
    elif group in ("lock_20_3w", "lock_30_3w"):
        body_len = 2.75
        body_dia = 2.26
    else:
        body_len = 2.75
        body_dia = 2.33
    return {
        "length": body_len,
        "diameter": max(body_dia, face),
        "face": face,
        "recess": inlet_recess(spec),
        "face_length": inlet_recess(spec) + 0.015,
    }


def blade_length(spec: dict, name: str) -> float:
    locking = spec["locking"]
    amps = spec["amps"]
    if name == "G" and not locking:
        if amps >= 30:
            return 1.406
        if amps >= 20 and spec["series"] in ("7", "10", "14") and spec["series"] != "5":
            if spec["config"] in ("14-20", "7-20", "10-20"):
                return 0.875
        return 0.843
    if locking:
        if amps <= 15:
            return 0.773 if name == "G" else 0.632
        if amps <= 20:
            return 0.898 if name in ("G", "W") else 0.734
        return 0.976
    if amps >= 30:
        return 1.187 if name != "G" else 1.406
    if amps >= 20:
        return 0.687
    return 0.625


def overall_length(spec: dict, gender: str) -> float:
    house = housing(spec, gender)
    if gender == "P":
        longest = max(blade_length(spec, n) for n in spec["contacts"])
        return house["length"] + longest
    return house["length"]


# ---------------------------------------------------------------------------
# Face-feature constructors (inches, Y/Z in the face plane)
# ---------------------------------------------------------------------------

def _rect(name, y, z, wy, wz, rot=0.0):
    return {
        "kind": "rect",
        "name": name,
        "y": y,
        "z": z,
        "wy": wy,
        "wz": wz,
        "rot": rot,
    }


def _round(name, y, z, dia):
    return {"kind": "round", "name": name, "y": y, "z": z, "dia": dia}


def _ell(name, y, z, wy, wz, tab_y, tab_z, tab_wy, tab_wz):
    return {
        "kind": "L",
        "name": name,
        "y": y,
        "z": z,
        "wy": wy,
        "wz": wz,
        "tab_y": tab_y,
        "tab_z": tab_z,
        "tab_wy": tab_wy,
        "tab_wz": tab_wz,
    }


def _tee(name, y, z, stem_wy, stem_wz, bar_y, bar_z, bar_wy, bar_wz):
    return {
        "kind": "T",
        "name": name,
        "y": y,
        "z": z,
        "wy": stem_wy,
        "wz": stem_wz,
        "tab_y": bar_y,
        "tab_z": bar_z,
        "tab_wy": bar_wy,
        "tab_wz": bar_wz,
    }


def _arc(name, r_inner, thick, a0_deg, a1_deg, hook=False):
    return {
        "kind": "arc",
        "name": name,
        "r_inner": r_inner,
        "thick": thick,
        "a0": a0_deg,
        "a1": a1_deg,
        "hook": hook,
    }


# 15 A straight-blade stock (WD-6 p24 / p29)
_W15 = _mid(0.240, 0.260)  # 0.250
_T15 = 0.060
_G15 = _mid(0.184, 0.190)  # 0.187
_SLOT_T15 = _mid(0.075, 0.095)
_SLOT_L15 = _mid(0.265, 0.285)

# 30/50 A stock
_T30 = 0.100
_G30 = _mid(0.309, 0.315)
_W30 = _mid(0.490, 0.510)


def _g15(z=0.343):
    return _round("G", 0.0, z, _G15)


def _family_5_15(gender: str):
    cl = -0.125
    g_z = cl + 0.468
    if gender == "R":
        return [
            _rect("X", 0.250, cl, _SLOT_T15, _SLOT_L15),
            _rect("W", -0.250, cl, _SLOT_T15, _SLOT_L15),
            _round("G", 0.0, g_z, _mid(0.205, 0.212)),
        ]
    return [
        _rect("X", 0.250, cl, _T15, _W15),
        _rect("W", -0.250, cl, _T15, _W15),
        _g15(g_z),
    ]


def _family_5_20(gender: str):
    cl = -0.125
    g_z = cl + 0.468
    if gender == "R":
        # T-slot on W so a 5-15P also fits (WD-6 p25).
        return [
            _rect("X", 0.250, cl, _SLOT_T15, _SLOT_L15),
            _tee(
                "W",
                -0.250,
                cl,
                _SLOT_T15,
                _SLOT_L15,
                -0.250,
                cl,
                _SLOT_L15,
                _SLOT_T15,
            ),
            _round("G", 0.0, g_z, _mid(0.205, 0.212)),
        ]
    return [
        _rect("X", 0.250, cl, _T15, _W15),
        _rect("W", -0.250, cl, _W15, _T15),
        _g15(g_z),
    ]


def _family_6_15(gender: str):
    cl = -0.125
    half = 0.718 / 2.0
    g_z = cl + 0.468
    if gender == "R":
        return [
            _rect("X", half, cl, _SLOT_L15, _SLOT_T15),
            _rect("Y", -half, cl, _SLOT_L15, _SLOT_T15),
            _round("G", 0.0, g_z, _mid(0.205, 0.212)),
        ]
    return [
        _rect("X", half, cl, _W15, _T15),
        _rect("Y", -half, cl, _W15, _T15),
        _g15(g_z),
    ]


def _family_6_20(gender: str):
    cl = -0.125
    half = 0.718 / 2.0
    g_z = cl + 0.468
    if gender == "R":
        return [
            _tee(
                "X",
                -half,
                cl,
                _SLOT_T15,
                _SLOT_L15,
                -half,
                cl,
                _SLOT_L15,
                _SLOT_T15,
            ),
            _rect("Y", half, cl, _SLOT_L15, _SLOT_T15),
            _round("G", 0.0, g_z, _mid(0.205, 0.212)),
        ]
    return [
        _rect("X", -half, cl, _T15, _W15),
        _rect("Y", half, cl, _W15, _T15),
        _g15(g_z),
    ]


def _family_7_15(gender: str):
    # WD-6 p34: blades 30° from vertical, CCC 0.540, G at +0.343.
    half = 0.540 / 2.0
    wy, wz = (_SLOT_T15, _SLOT_L15) if gender == "R" else (_T15, _W15)
    g = _round("G", 0.0, 0.343, _mid(0.205, 0.212) if gender == "R" else _G15)
    return [
        _rect("X", half, 0.0, wy, wz, rot=-30.0),
        _rect("W", -half, 0.0, wy, wz, rot=30.0),
        g,
    ]


def _family_7_20(gender: str):
    # WD-6 p35: 30° from horizontal, ±0.325, G at +0.375.
    wy = 0.085 if gender == "R" else 0.075
    wz = 0.410 if gender == "R" else _mid(0.370, 0.385)
    g = _round("G", 0.0, 0.375, 0.232 if gender == "R" else _mid(0.215, 0.221))
    return [
        _rect("X", 0.325, -0.20, wy, wz, rot=-30.0),
        _rect("W", -0.325, -0.20, wy, wz, rot=30.0),
        g,
    ]


def _family_5_30(gender: str):
    # WD-6 p27. Looking at the plug: W (L) left, X right, G top.
    t = 0.172 if gender == "R" else _T30
    h = 0.575 if gender == "R" else (0.281 + 0.777)
    z = 0.5 * (0.281 - 0.777)
    x_y = 0.500 - t / 2.0
    w_y = -(0.500 - t / 2.0)
    foot_w = 0.320
    g = _round("G", 0.0, 0.531, 0.326 if gender == "R" else _G30)
    return [
        _rect("X", x_y, z, t, h),
        _ell(
            "W",
            w_y,
            z,
            t,
            h,
            w_y + (0.08 + foot_w / 2.0),
            z - h / 2.0 + t / 2.0,
            foot_w,
            t,
        ),
        g,
    ]


def _family_5_50(gender: str):
    # WD-6 p28. Power CL at z=-0.812, CCC 1.000, W is L-shaped.
    t = 0.172 if gender == "R" else _T30
    h = 0.575 if gender == "R" else _W30
    z = -0.812
    g = _round("G", 0.0, 0.531, 0.326 if gender == "R" else _G30)
    return [
        _rect("X", -0.500, z, t, h),
        _ell(
            "W",
            0.500,
            z,
            t,
            h,
            0.500 + 0.16,
            z,
            0.32,
            t,
        ),
        g,
    ]


def _family_6_30(gender: str):
    # WD-6 p32. Horizontal hots, CCC 1.000, CL at z=-0.281, G at +0.531.
    t = 0.172 if gender == "R" else _T30
    w = 0.575 if gender == "R" else _W30
    z = -0.281
    g = _round("G", 0.0, 0.531, 0.326 if gender == "R" else _G30)
    return [
        _rect("X", 0.500, z, w, t),
        _rect("Y", -0.500, z, w, t),
        g,
    ]


def _family_6_50(gender: str):
    return _family_6_30(gender)


def _family_7_30(gender: str):
    feats = _family_6_30(gender)
    for f in feats:
        if f["name"] == "Y":
            f["name"] = "W"
    return feats


def _family_7_50(gender: str):
    # WD-6 p37: 30° from vertical, larger 50 A blades.
    t = 0.172 if gender == "R" else _T30
    w = 0.575 if gender == "R" else _W30
    g = _round("G", 0.0, 0.531, 0.326 if gender == "R" else _G30)
    return [
        _rect("X", 0.50, -0.70, t, w, rot=-30.0),
        _rect("W", -0.50, -0.70, t, w, rot=30.0),
        g,
    ]


def _family_10_20(gender: str):
    # WD-6 p42. W top vertical; X/Y 30° from vertical at z=-0.625.
    t = 0.105 if gender == "R" else 0.075
    w = 0.350 if gender == "R" else _mid(0.307, 0.322)
    return [
        _rect("W", 0.0, 0.437, t, w),
        _rect("X", 0.325, -0.625, t, w, rot=-30.0),
        _rect("Y", -0.325, -0.625, t, w, rot=30.0),
    ]


def _family_10_30(gender: str):
    # WD-6 p43. W top L-shaped; X/Y 30° at z=-0.884, CCC 0.920.
    t = 0.172 if gender == "R" else _T30
    w = 0.575 if gender == "R" else _W30
    return [
        _ell("W", 0.0, 0.618, 0.320, t, 0.16, 0.618, 0.32, t),
        _rect("X", -0.460, -0.884, t, w, rot=30.0),
        _rect("Y", 0.460, -0.884, t, w, rot=-30.0),
    ]


def _family_10_50(gender: str):
    return _family_10_30(gender)


def _family_14_15(gender: str):
    # WD-6 p49. X/Y vertical CCC 0.718; W horizontal below; G above.
    half = 0.718 / 2.0
    t = _SLOT_T15 if gender == "R" else _T15
    h = _SLOT_L15 if gender == "R" else _W15
    g = _round("G", 0.0, 0.468, _mid(0.205, 0.212) if gender == "R" else _G15)
    return [
        _rect("X", -half, 0.0, t, h),
        _rect("Y", half, 0.0, t, h),
        _rect("W", 0.0, -0.765, h, t),
        g,
    ]


def _family_14_20(gender: str):
    # WD-6 p50.
    t = 0.105 if gender == "R" else 0.075
    w = 0.350 if gender == "R" else _mid(0.307, 0.322)
    g = _round("G", 0.0, 0.375, _G15 if gender == "P" else _mid(0.205, 0.212))
    return [
        _rect("X", -0.406, 0.0, t, w),
        _rect("Y", 0.406, 0.0, t, w),
        _rect("W", 0.0, -0.406, w, t),
        g,
    ]


def _family_14_30(gender: str):
    # WD-6 p51. Contacts on a 0.687 R cross; W is L-shaped.
    t = 0.172 if gender == "R" else _T30
    h = 0.575 if gender == "R" else _W30
    r = 0.687
    g = _round("G", 0.0, r, 0.326 if gender == "R" else _G30)
    return [
        _rect("X", -r, 0.0, t, h),
        _rect("Y", r, 0.0, t, h),
        _ell("W", 0.0, -r, t, h, -0.16, -r, 0.32, t),
        g,
    ]


def _family_14_50(gender: str):
    # WD-6 p52. Same 0.687 R cross; W is a straight vertical blade;
    # X/Y are horizontal (does not mate with 14-30).
    t = 0.172 if gender == "R" else _T30
    w = _mid(0.309, 0.315)
    r = 0.687
    g = _round("G", 0.0, r, 0.326 if gender == "R" else _G30)
    return [
        _rect("X", -r, 0.0, w, t),
        _rect("Y", r, 0.0, w, t),
        _rect("W", 0.0, -r, t, w),
        g,
    ]


def _family_14_60(gender: str):
    return _family_14_50(gender)


def _family_15_15(gender: str):
    # WD-6 p54. G top; X/Z horizontal at z=0; Y wide horizontal at bottom.
    t = _SLOT_T15 if gender == "R" else _T15
    w = _SLOT_L15 if gender == "R" else _W15
    y_w = 0.734
    g = _round("G", 0.0, 0.297, _mid(0.205, 0.212) if gender == "R" else _G15)
    return [
        _rect("X", -0.437, 0.0, w, t),
        _rect("Z", 0.437, 0.0, w, t),
        _rect("Y", 0.0, -0.394, y_w, t),
        g,
    ]


def _family_15_20(gender: str):
    return _family_15_15(gender)


def _family_15_30(gender: str):
    t = 0.172 if gender == "R" else _T30
    w = 0.50
    g = _round("G", 0.0, 0.531, 0.326 if gender == "R" else _G30)
    return [
        _rect("X", -0.55, 0.0, w, t),
        _rect("Z", 0.55, 0.0, w, t),
        _rect("Y", 0.0, -0.62, 0.90, t),
        g,
    ]


def _family_15_50(gender: str):
    return _family_15_30(gender)


def _family_15_60(gender: str):
    return _family_15_30(gender)


def _family_tt_30(gender: str):
    # Travel Trailer / RV 30 A. WD-6 specific-purpose figure; blades at
    # 45° from vertical and 90° to each other, round ground (Wikipedia
    # NEMA connector + typical TT-30P catalogs). Face uses the 30 A
    # straight-blade C = 2.600 envelope from p16.
    t = 0.172 if gender == "R" else _T30
    w = 0.40
    r = 0.42
    g = _round("G", 0.0, -0.50, 0.326 if gender == "R" else _G30)
    return [
        _rect("X", r * math.cos(math.radians(45)), r * math.sin(math.radians(45)), t, w, rot=-45.0),
        _rect("W", r * math.cos(math.radians(135)), r * math.sin(math.radians(135)), t, w, rot=45.0),
        g,
    ]


# Locking series clocking so L5 / L6 / L7 … faces are not interchangeable.
# Offsets are relative to the extracted L5 figure of the same amp class.
_LOCK_ROT = {
    "5": 0,
    "6": 40,
    "7": 80,
    "8": 15,
    "9": 55,
    "14": 10,
    "15": 50,
    "16": 90,
    "17": 25,
    "21": 0,
    "22": 35,
    "23": 70,
    "24": 20,
    "25": 60,
    "26": 5,
}


def _rotate_arc(feat, deg):
    out = dict(feat)
    out["a0"] = feat["a0"] + deg
    out["a1"] = feat["a1"] + deg
    return out


def _lock_3w(amps: int, series: str, names):
    """L5-15 p66, L5-20 p67, L5-30 p68; other series are clocked copies."""
    rot = _LOCK_ROT.get(series, 0)
    if amps <= 15:
        r, thick, span = 0.343, 0.070, 28.0
        # G at bottom (270°); W +126° CCW; X +236° CCW (WD-6 p66).
        centers = {"G": 270.0, "W": 36.0, "X": 146.0, "Y": 146.0}
    elif amps <= 20:
        r, thick, span = 0.437, 0.065, 27.0
        # G at top; 120° spacing (WD-6 p67).
        centers = {"G": 90.0, "W": 330.0, "X": 210.0, "Y": 210.0}
    else:
        r, thick, span = 0.500, 0.070, 30.0
        # WD-6 p68: W–G 100°, W–hot 215°.
        centers = {"G": 90.0, "W": 190.0, "X": 45.0, "Y": 45.0}
    feats = []
    for name in names:
        a = centers.get(name, 90.0)
        feats.append(
            _rotate_arc(
                _arc(name, r, thick, a - span / 2.0, a + span / 2.0, hook=(name == "G")),
                rot,
            )
        )
    return feats


def _lock_4w(amps: int, series: str):
    rot = _LOCK_ROT.get(series, 0)
    r = 0.437 if amps <= 20 else 0.500
    thick = 0.065
    span = 24.0
    angles = {"X": 45.0, "Y": 135.0, "W": 225.0, "Z": 225.0, "G": 315.0}
    return [
        _rotate_arc(
            _arc(name, r, thick, a - span / 2.0, a + span / 2.0, hook=(name == "G")),
            rot,
        )
        for name, a in angles.items()
    ]


def _lock_5w(amps: int, series: str):
    rot = _LOCK_ROT.get(series, 0)
    r = 0.437 if amps <= 20 else 0.500
    thick = 0.065
    span = 22.0
    feats = [_round("G", 0.0, 0.0, 0.187)]
    for name, a in (("X", 45.0), ("Y", 135.0), ("Z", 225.0), ("W", 315.0)):
        feats.append(
            _rotate_arc(_arc(name, r, thick, a - span / 2.0, a + span / 2.0), rot)
        )
    return feats


_STRAIGHT = {
    ("5", 15): _family_5_15,
    ("5", 20): _family_5_20,
    ("5", 30): _family_5_30,
    ("5", 50): _family_5_50,
    ("6", 15): _family_6_15,
    ("6", 20): _family_6_20,
    ("6", 30): _family_6_30,
    ("6", 50): _family_6_50,
    ("7", 15): _family_7_15,
    ("7", 20): _family_7_20,
    ("7", 30): _family_7_30,
    ("7", 50): _family_7_50,
    ("10", 20): _family_10_20,
    ("10", 30): _family_10_30,
    ("10", 50): _family_10_50,
    ("14", 15): _family_14_15,
    ("14", 20): _family_14_20,
    ("14", 30): _family_14_30,
    ("14", 50): _family_14_50,
    ("14", 60): _family_14_60,
    ("15", 15): _family_15_15,
    ("15", 20): _family_15_20,
    ("15", 30): _family_15_30,
    ("15", 50): _family_15_50,
    ("15", 60): _family_15_60,
    ("TT", 30): _family_tt_30,
}


def face_features(spec: dict, gender: str) -> list[dict]:
    series = spec["series"]
    amps = spec["amps"]
    names = spec["contacts"]
    if spec["locking"]:
        n = len(names)
        if n <= 3:
            return _lock_3w(amps, series, names)
        if n == 4:
            feats = _lock_4w(amps, series)
            wanted = set(names)
            return [f for f in feats if f["name"] in wanted]
        return _lock_5w(amps, series)
    builder = _STRAIGHT.get((series, amps), _family_5_15)
    feats = builder(gender)
    wanted = set(names)
    return [f for f in feats if f["name"] in wanted]


def _rotate_point(y, z, cy, cz, deg):
    rad = math.radians(deg)
    c, s = math.cos(rad), math.sin(rad)
    dy, dz = y - cy, z - cz
    return (cy + dy * c - dz * s, cz + dy * s + dz * c)


def _rect_corners(y, z, wy, wz, rot=0.0):
    hy, hz = wy / 2.0, wz / 2.0
    pts = [
        (y - hy, z - hz),
        (y + hy, z - hz),
        (y + hy, z + hz),
        (y - hy, z + hz),
    ]
    if rot:
        pts = [_rotate_point(py, pz, y, z, rot) for py, pz in pts]
    return pts


def feature_polygons_yz(feat: dict, n=12):
    """One or more closed YZ polygons in inches (simple, for STEP/SVG)."""
    kind = feat["kind"]
    if kind == "rect":
        return [_rect_corners(feat["y"], feat["z"], feat["wy"], feat["wz"], feat.get("rot", 0.0))]
    if kind == "round":
        r = feat["dia"] / 2.0
        y, z = feat["y"], feat["z"]
        return [[
            (
                y + r * math.cos(2.0 * math.pi * i / n),
                z + r * math.sin(2.0 * math.pi * i / n),
            )
            for i in range(n)
        ]]
    if kind in ("L", "T"):
        return [
            _rect_corners(feat["y"], feat["z"], feat["wy"], feat["wz"]),
            _rect_corners(feat["tab_y"], feat["tab_z"], feat["tab_wy"], feat["tab_wz"]),
        ]
    if kind == "arc":
        a0 = math.radians(feat["a0"])
        a1 = math.radians(feat["a1"])
        ri, ro = feat["r_inner"], feat["r_inner"] + feat["thick"]
        pts = []
        for i in range(n + 1):
            t = a0 + (a1 - a0) * i / n
            pts.append((ro * math.cos(t), ro * math.sin(t)))
        for i in range(n + 1):
            t = a1 - (a1 - a0) * i / n
            pts.append((ri * math.cos(t), ri * math.sin(t)))
        if feat.get("hook"):
            mid = 0.5 * (a0 + a1)
            hook_r = max(0.06, ri * 0.40)
            hw = feat["thick"] * 0.55
            tip_y = hook_r * math.cos(mid)
            tip_z = hook_r * math.sin(mid)
            # Extra inward rectangle, returned as a second poly.
            return [pts, _rect_corners(tip_y, tip_z, hw * 2.0, hw * 2.0)]
        return [pts]
    raise ValueError(feat)


def feature_label_yz(feat: dict):
    """Approximate label point just outside the feature."""
    kind = feat["kind"]
    if kind == "arc":
        mid = math.radians(0.5 * (feat["a0"] + feat["a1"]))
        r = feat["r_inner"] + feat["thick"] + 0.14
        return (r * math.cos(mid), r * math.sin(mid))
    if kind == "round":
        return (feat["y"], feat["z"] + feat["dia"] / 2.0 + 0.14)
    return (feat["y"], feat["z"] + max(feat.get("wz", 0.1), 0.12) / 2.0 + 0.12)
