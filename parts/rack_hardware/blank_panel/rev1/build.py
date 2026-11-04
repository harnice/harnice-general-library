import os

signals_list.new()

units = configuration["number_of_rack_units"]
if (
    isinstance(units, bool)
    or not isinstance(units, (int, float))
    or int(units) != units
    or not 1 <= int(units) <= 6
):
    raise ValueError("number_of_rack_units must be a whole number from 1 to 6")
units = int(units)

images_dir = fileio.dirpath("body_images")


# Face pictures for 1U through 6U. Front, vented front, and back.
# The faceplate is 19 inches wide and the rear panel is 17. One rack unit is 1.75 inches.
def generate_face_pictures(folder):
    from PIL import Image, ImageDraw, ImageFont

    os.makedirs(folder, exist_ok=True)
    px_per_in = 96
    panel = (32, 32, 32)
    ink = (208, 208, 208)
    faceplate_width = 19.0
    rear_width = 17.0
    rack_unit = 1.75
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
        raise ValueError("a monospace font was not found, so the blank panel logo could not be drawn")

    logo = "\n".join(line.rstrip() for line in cli.high_contrast_logo)
    # Same mark on every height. About 5 in wide and 0.85 in tall.
    logo_max_w = 5.0 * px_per_in
    logo_max_h = 0.85 * px_per_in

    def logo_ink(font):
        probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        box = probe.multiline_textbbox((0, 0), logo, font=font, spacing=0)
        image = Image.new("RGB", (box[2] - box[0], box[3] - box[1]), panel)
        ImageDraw.Draw(image).multiline_text(
            (-box[0], -box[1]), logo, font=font, fill=ink, spacing=0
        )
        pixels = image.load()
        min_x, min_y = image.size
        max_x, max_y = -1, -1
        for y in range(image.size[1]):
            for x in range(image.size[0]):
                if pixels[x, y] == panel:
                    continue
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
        cropped = image.crop((min_x, min_y, max_x + 1, max_y + 1))
        return cropped

    source = logo_ink(ImageFont.truetype(font_path, 48))
    scale = min(logo_max_w / source.width, logo_max_h / source.height)
    sprite = source.resize(
        (
            max(1, int(round(source.width * scale))),
            max(1, int(round(source.height * scale))),
        ),
        Image.Resampling.LANCZOS,
    )

    def write_face(path, width_in, height_in, with_logo):
        width = max(1, int(round(width_in * px_per_in)))
        height = max(1, int(round(height_in * px_per_in)))
        image = Image.new("RGB", (width, height), panel)
        if with_logo:
            image.paste(sprite, ((width - sprite.width) // 2, (height - sprite.height) // 2))
        image.save(path)

    def write_vented_front(path, width_in, height_in):
        # Circles are 1/8 in, packed on a hex grid, inset from the ears.
        supersample = 4
        width = max(1, int(round(width_in * px_per_in)))
        height = max(1, int(round(height_in * px_per_in)))
        image = Image.new("RGB", (width * supersample, height * supersample), panel)
        draw = ImageDraw.Draw(image)
        hole = 0.125 * px_per_in * supersample
        pitch = 0.16 * px_per_in * supersample
        row_pitch = pitch * (3 ** 0.5) / 2
        margin_x = 1.25 * px_per_in * supersample
        margin_y = 0.2 * px_per_in * supersample
        span_x = image.width - 2 * margin_x
        span_y = image.height - 2 * margin_y
        cols = int((span_x - hole) / pitch) + 1
        rows = int((span_y - hole) / row_pitch) + 1
        if cols >= 1 and rows >= 1:
            grid_w = (cols - 1) * pitch + hole
            grid_h = (rows - 1) * row_pitch + hole
            origin_x = margin_x + (span_x - grid_w) / 2 + hole / 2
            origin_y = margin_y + (span_y - grid_h) / 2 + hole / 2
            radius = hole / 2
            vent = (84, 84, 84)
            # Same centered mark as the plain fronts. Leave the holes out around it.
            logo_x = (width - sprite.width) // 2
            logo_y = (height - sprite.height) // 2
            pad = 0.1 * px_per_in * supersample
            clear_left = logo_x * supersample - pad
            clear_top = logo_y * supersample - pad
            clear_right = (logo_x + sprite.width) * supersample + pad
            clear_bottom = (logo_y + sprite.height) * supersample + pad
            for row in range(rows):
                count = cols if row % 2 == 0 else cols - 1
                shift = 0 if row % 2 == 0 else pitch / 2
                cy = origin_y + row * row_pitch
                for col in range(count):
                    cx = origin_x + shift + col * pitch
                    nearest_x = min(max(cx, clear_left), clear_right)
                    nearest_y = min(max(cy, clear_top), clear_bottom)
                    dx = cx - nearest_x
                    dy = cy - nearest_y
                    if dx * dx + dy * dy <= radius * radius:
                        continue
                    draw.ellipse(
                        (cx - radius, cy - radius, cx + radius, cy + radius),
                        fill=vent,
                    )
        image = image.resize((width, height), Image.Resampling.LANCZOS)
        image.paste(sprite, ((width - sprite.width) // 2, (height - sprite.height) // 2))
        image.save(path)

    for count in range(1, 7):
        height_in = count * rack_unit
        write_face(
            os.path.join(folder, f"front-{count}u.png"),
            faceplate_width,
            height_in,
            True,
        )
        write_vented_front(
            os.path.join(folder, f"front-vented-{count}u.png"),
            faceplate_width,
            height_in,
        )
        write_face(
            os.path.join(folder, f"back-{count}u.png"),
            rear_width,
            height_in,
            False,
        )

# Comment out this call after the face pictures exist.
# generate_face_pictures(images_dir)

# 0.5 inches deep. number_of_rack_units picks the height.
# Vented uses front-vented-Nu.png on the front. The back stays plain.
front_name = f"front-{units}u.png"
if configuration["vented"]:
    front_name = f"front-vented-{units}u.png"
build_utils.run_macro(
    "build_rackmount_physical_model",
    "macros/device_artifacts",
    "https://github.com/harnice/harnice-general-library",
    artifact_id="body-1",
    params={"u": units, "depth": 0.5},
    images={
        "front": os.path.join(images_dir, front_name),
        "back": os.path.join(images_dir, f"back-{units}u.png"),
    },
)
