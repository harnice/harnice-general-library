import math
import os

signals_list.new()

# Power inlet. Channel type 18, North American 120VAC 15A, in:
#   signals live, neutral, earth; 110-125 VAC; 15 A; mates with type 17.
# NEMA 5-15P cord plug, same WD-6 poles as the 5-15R receptacle:
#   X  live    narrow blade
#   W  neutral wide blade
#   G  earth   U-ground
NA_120VAC_15A_IN = (18, "https://github.com/harnice/harnice-general-library")
NEMA_5_15P = {
    "live": "X",
    "neutral": "W",
    "earth": "G",
}
for signal, cavity in NEMA_5_15P.items():
    signals_list.append(
        channel_id="in1",
        signal=signal,
        connector_id="J1",
        cavity=cavity,
        channel_type=NA_120VAC_15A_IN,
        device_connector_mpn="NEMA-5-15P",
    )

units = configuration["number_of_rack_units"]
if (
    isinstance(units, bool)
    or not isinstance(units, (int, float))
    or int(units) != units
    or not 1 <= int(units) <= 3
):
    raise ValueError("number_of_rack_units must be a whole number from 1 to 3")
units = int(units)

images_dir = fileio.dirpath("body_images")


# Face pictures for 1U through 3U. The faceplate is 19 inches wide and the
# rear panel is 17. One rack unit is 1.75 inches. Fans fill the 17 inch
# opening between the ears. The count is that width divided by the height.
def generate_face_pictures(folder):
    from PIL import Image, ImageDraw, ImageFont

    os.makedirs(folder, exist_ok=True)
    px_per_in = 96
    panel = (20, 20, 20)
    ink = (187, 187, 187)
    hub = (0, 0, 0)
    font_path = None
    for candidate in (
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ):
        if os.path.isfile(candidate):
            font_path = candidate
            break
    if font_path is None:
        raise ValueError("a monospace font was not found, so the fan letter could not be drawn")
    letter = "\n".join(line.rstrip() for line in cli.favicon)
    font = ImageFont.truetype(font_path, 72)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    box = probe.multiline_textbbox((0, 0), letter, font=font, spacing=0)
    logo = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0))
    ImageDraw.Draw(logo).multiline_text(
        (-box[0], -box[1]), letter, font=font, fill=ink + (255,), spacing=0
    )
    logo = logo.crop(logo.getbbox())
    faceplate_width = 19.0
    rear_width = 17.0
    available_width = 17.0
    rack_unit = 1.75
    supersample = 4
    wire = (214, 216, 220)
    wire_shadow = (90, 92, 96)

    def write_back(path, height_in):
        width = max(1, int(round(rear_width * px_per_in)))
        height = max(1, int(round(height_in * px_per_in)))
        Image.new("RGB", (width, height), panel).save(path)

    def write_front(path, height_in):
        width = max(1, int(round(faceplate_width * px_per_in)))
        height = max(1, int(round(height_in * px_per_in)))
        scale = px_per_in * supersample
        image = Image.new("RGB", (width * supersample, height * supersample), panel)
        draw = ImageDraw.Draw(image)

        def px(inches):
            return inches * scale

        def y_from_bottom(inches):
            return (height_in - inches) * scale

        count = int(available_width / height_in)
        if count < 1:
            count = 1
        cell = available_width / count
        # A little smaller than the height so the corner screws stay on the panel.
        diameter = min(height_in * 0.86, cell * 0.92)
        radius = diameter / 2
        opening_left = (faceplate_width - available_width) / 2

        slot_w = 0.15
        slot_h = 0.36
        rack_units = int(round(height_in / rack_unit))
        for side in (0.40, faceplate_width - 0.40):
            for unit in range(rack_units):
                for offset in (0.40, rack_unit - 0.40):
                    cy = unit * rack_unit + offset
                    box = (
                        px(side - slot_w / 2),
                        y_from_bottom(cy + slot_h / 2),
                        px(side + slot_w / 2),
                        y_from_bottom(cy - slot_h / 2),
                    )
                    draw.rounded_rectangle(box, radius=px(slot_w / 2), fill=(8, 8, 8))

        ring_w = max(2, int(round(0.012 * scale)))
        spoke_w = max(2, int(round(0.016 * scale)))
        rim_w = max(3, int(round(0.028 * scale)))
        screw_r = px(max(0.045, diameter * 0.028))
        centers = []

        for index in range(count):
            cx = px(opening_left + cell * (index + 0.5))
            cy = y_from_bottom(height_in / 2)
            r = px(radius)
            centers.append((opening_left + cell * (index + 0.5), height_in / 2))
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(58, 60, 64))
            blade_r = r * 0.92
            for blade in range(5):
                start = blade * (360 / 5) - 20
                shade = (96, 98, 104) if blade % 2 == 0 else (42, 44, 48)
                draw.pieslice(
                    (cx - blade_r, cy - blade_r, cx + blade_r, cy + blade_r),
                    start=start,
                    end=start + 36,
                    fill=shade,
                )

            for angle_deg in range(0, 360, 45):
                angle = math.radians(angle_deg)
                inner = r * 0.18
                outer = r * 0.98
                x1 = cx + math.cos(angle) * inner
                y1 = cy - math.sin(angle) * inner
                x2 = cx + math.cos(angle) * outer
                y2 = cy - math.sin(angle) * outer
                this_spoke = spoke_w * 2 if angle_deg % 90 != 0 else spoke_w
                draw.line((x1 + 2, y1 + 2, x2 + 2, y2 + 2), fill=wire_shadow, width=this_spoke)
                draw.line((x1, y1, x2, y2), fill=wire, width=this_spoke)

            for ring in range(1, 9):
                rr = r * (0.22 + 0.74 * ring / 8)
                box = (cx - rr, cy - rr, cx + rr, cy + rr)
                shadow = (cx - rr + 2, cy - rr + 2, cx + rr + 2, cy + rr + 2)
                draw.ellipse(shadow, outline=wire_shadow, width=ring_w)
                draw.ellipse(box, outline=wire, width=ring_w)

            draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=wire, width=rim_w)

            corner = r * 0.78
            for sx in (-corner, corner):
                for sy in (-corner, corner):
                    draw.ellipse(
                        (cx + sx - screw_r, cy + sy - screw_r, cx + sx + screw_r, cy + sy + screw_r),
                        fill=(198, 200, 204),
                    )
                    dot = screw_r * 0.28
                    draw.ellipse(
                        (cx + sx - dot, cy + sy - dot, cx + sx + dot, cy + sy + dot),
                        fill=(40, 42, 46),
                    )

        image = image.resize((width, height), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(image)
        # Light gray slash-font h on a black circle in the middle of each fan.
        circle = max(10, int(round(diameter * 0.35 * px_per_in)))
        mark_w = max(8, int(round(circle * 0.86)))
        mark_h = max(4, int(round(logo.height * mark_w / logo.width)))
        if mark_h > circle * 0.78:
            mark_h = int(round(circle * 0.78))
            mark_w = max(4, int(round(logo.width * mark_h / logo.height)))
        mark = logo.resize((mark_w, mark_h), Image.Resampling.LANCZOS)
        # Keep the strokes at #bbbbbb. Scaling the thin lines otherwise fades them.
        solid = Image.new("RGBA", mark.size, (0, 0, 0, 0))
        source = mark.load()
        target = solid.load()
        for y in range(mark.size[1]):
            for x in range(mark.size[0]):
                if source[x, y][3] >= 80:
                    target[x, y] = ink + (255,)
        mark = solid
        for cx_in, cy_in in centers:
            cx = cx_in * px_per_in
            cy = (height_in - cy_in) * px_per_in
            draw.ellipse((cx - circle / 2, cy - circle / 2, cx + circle / 2, cy + circle / 2), fill=hub)
            image.paste(mark, (int(round(cx - mark_w / 2)), int(round(cy - mark_h / 2))), mark)
        image.save(path)

    for count in range(1, 4):
        height_in = count * rack_unit
        write_front(os.path.join(folder, f"front-{count}u.png"), height_in)
        write_back(os.path.join(folder, f"back-{count}u.png"), height_in)


# Comment out this call after the face pictures exist.
# generate_face_pictures(images_dir)

# 0.5 inches deep. number_of_rack_units picks the height and the fan picture.
build_utils.run_macro(
    "build_rackmount_physical_model",
    "macros/device_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="body-1",
    params={"u": units, "depth": 1},
    images={
        "front": os.path.join(images_dir, f"front-{units}u.png"),
        "back": os.path.join(images_dir, f"back-{units}u.png"),
    },
)

# The rack body only writes the F mates. J1 is the power plug on the rear face.
saved = physical_body.load_body()
mates = list(saved["mate_connectors"]) if saved else []
if not any(mate["id"] == "J1" for mate in mates):
    mates.append({
        "id": "J1",
        "location": [0.0, 0.5, units * 1.75 / 2.0],
        "alpha": 0.0,
        "beta": 0.0,
        "gamma": 0.0,
        "source": "gui",
    })
    physical_body.save_mates(mates)
