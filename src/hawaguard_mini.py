from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "generated"
OUT.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Box:
    x0: float
    x1: float
    y0: float
    y1: float
    z0: float
    z1: float
    color: tuple[int, int, int] = (17, 116, 139)
    group: str = "body"

    def translated(self, dx: float = 0, dy: float = 0, dz: float = 0) -> "Box":
        return Box(
            self.x0 + dx,
            self.x1 + dx,
            self.y0 + dy,
            self.y1 + dy,
            self.z0 + dz,
            self.z1 + dz,
            self.color,
            self.group,
        )


TEAL = (14, 116, 144)
TEAL_DARK = (9, 78, 101)
GREEN = (34, 197, 94)
GRAY = (71, 85, 105)


def base_boxes() -> list[Box]:
    boxes: list[Box] = []
    # 90 x 64 mm base tray, 2.4 mm walls, 12 mm tall.
    boxes.append(Box(-45, 45, -32, 32, 0, 2.4, TEAL, "base"))
    boxes.append(Box(-45, 45, -32, -29.6, 2.4, 12, TEAL, "base"))
    boxes.append(Box(-45, 45, 29.6, 32, 2.4, 5.4, TEAL, "base"))
    boxes.append(Box(-45, -7, 29.6, 32, 5.4, 12, TEAL, "base"))
    boxes.append(Box(7, 45, 29.6, 32, 5.4, 12, TEAL, "base"))
    boxes.append(Box(-45, -42.6, -29.6, 29.6, 2.4, 12, TEAL, "base"))
    boxes.append(Box(42.6, 45, -29.6, 29.6, 2.4, 12, TEAL, "base"))

    # Low-profile mounting rails: left bay for particulate sensor, right bay for ESP32.
    boxes.extend(
        [
            # 42 x 42 mm left bay for an SPS30-class particulate sensor.
            Box(-38, -35, -22, 22, 2.4, 5.4, TEAL_DARK, "rail"),
            Box(7, 10.4, -22, 22, 2.4, 5.4, TEAL_DARK, "rail"),
            Box(-35, 7, -24, -21, 2.4, 5.0, TEAL_DARK, "stop"),
            Box(-35, 7, 21, 24, 2.4, 5.0, TEAL_DARK, "stop"),
            # 29.2 x 51.5 mm right bay for an ESP32 DevKit-style board.
            Box(8, 10.4, -28, 28, 2.4, 5.4, TEAL_DARK, "rail"),
            Box(39.6, 42, -28, 28, 2.4, 5.4, TEAL_DARK, "rail"),
            Box(10.4, 39.6, -28, -25.75, 2.4, 5.0, TEAL_DARK, "stop"),
            Box(10.4, 39.6, 25.75, 28, 2.4, 5.0, TEAL_DARK, "stop"),
        ]
    )
    return boxes


def lid_boxes() -> list[Box]:
    boxes: list[Box] = []
    x0, x1 = -47.8, 47.8
    y0, y1 = -34.8, 34.8
    ix0, ix1 = -45.4, 45.4
    iy0, iy1 = -32.4, 32.4
    roof0, roof1 = 31.6, 34.0

    # Roof with a true 29 x 15 mm OLED opening centered at (20, -12).
    wx0, wx1 = 5.5, 34.5
    wy0, wy1 = -19.5, -4.5
    boxes.extend(
        [
            Box(x0, wx0, y0, y1, roof0, roof1, TEAL, "lid"),
            Box(wx1, x1, y0, y1, roof0, roof1, TEAL, "lid"),
            Box(wx0, wx1, y0, wy0, roof0, roof1, TEAL, "lid"),
            Box(wx0, wx1, wy1, y1, roof0, roof1, TEAL, "lid"),
        ]
    )

    # Front wall and cable-relief back wall.
    boxes.append(Box(x0, x1, y0, iy0, 0, roof0, TEAL, "lid"))
    boxes.append(Box(x0, x1, iy1, y1, 7, roof0, TEAL, "lid"))
    boxes.append(Box(x0, -7, iy1, y1, 0, 7, TEAL, "lid"))
    boxes.append(Box(7, x1, iy1, y1, 0, 7, TEAL, "lid"))

    # Side walls use alternating structural slats to create cross-flow ventilation.
    z_bands = [(0, 7), (28.2, roof0)]
    z = 7.0
    while z < 27.0:
        z_bands.append((z, min(z + 2.8, 28.2)))
        z += 4.8
    for za, zb in z_bands:
        boxes.append(Box(x0, ix0, iy0, iy1, za, zb, TEAL, "lid"))
        boxes.append(Box(ix1, x1, iy0, iy1, za, zb, TEAL, "lid"))

    # OLED bezel and a raised H mark (HawaGuard) on the top face.
    bezel_h = 1.2
    boxes.extend(
        [
            Box(wx0 - 1.5, wx1 + 1.5, wy0 - 1.5, wy0, roof1, roof1 + bezel_h, GREEN, "accent"),
            Box(wx0 - 1.5, wx1 + 1.5, wy1, wy1 + 1.5, roof1, roof1 + bezel_h, GREEN, "accent"),
            Box(wx0 - 1.5, wx0, wy0, wy1, roof1, roof1 + bezel_h, GREEN, "accent"),
            Box(wx1, wx1 + 1.5, wy0, wy1, roof1, roof1 + bezel_h, GREEN, "accent"),
            Box(-31, -27.5, -19, -5, roof1, roof1 + 1.0, GREEN, "accent"),
            Box(-21.5, -18, -19, -5, roof1, roof1 + 1.0, GREEN, "accent"),
            Box(-27.5, -21.5, -13.5, -10.5, roof1, roof1 + 1.0, GREEN, "accent"),
        ]
    )

    # Four short friction ribs; nominal 0.35 mm engagement with the base tray.
    boxes.extend(
        [
            Box(-45.4, -45.05, -22, -10, 1.0, 6.0, TEAL_DARK, "rib"),
            Box(-45.4, -45.05, 10, 22, 1.0, 6.0, TEAL_DARK, "rib"),
            Box(45.05, 45.4, -22, -10, 1.0, 6.0, TEAL_DARK, "rib"),
            Box(45.05, 45.4, 10, 22, 1.0, 6.0, TEAL_DARK, "rib"),
        ]
    )
    return boxes


def _box_boundaries(boxes: list[Box]) -> tuple[list[float], list[float], list[float]]:
    xs = sorted({v for b in boxes for v in (b.x0, b.x1)})
    ys = sorted({v for b in boxes for v in (b.y0, b.y1)})
    zs = sorted({v for b in boxes for v in (b.z0, b.z1)})
    return xs, ys, zs


def union_surface_triangles(boxes: list[Box]) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Return the exact boundary of an axis-aligned union of boxes."""
    xs, ys, zs = _box_boundaries(boxes)
    xi = {value: i for i, value in enumerate(xs)}
    yi = {value: i for i, value in enumerate(ys)}
    zi = {value: i for i, value in enumerate(zs)}
    occ = np.zeros((len(xs) - 1, len(ys) - 1, len(zs) - 1), dtype=bool)
    for b in boxes:
        occ[xi[b.x0] : xi[b.x1], yi[b.y0] : yi[b.y1], zi[b.z0] : zi[b.z1]] = True

    triangles: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []

    def quad(a, b, c, d):
        triangles.append((np.array(a, float), np.array(b, float), np.array(c, float)))
        triangles.append((np.array(a, float), np.array(c, float), np.array(d, float)))

    nx, ny, nz = occ.shape
    for i, j, k in zip(*np.nonzero(occ)):
        xa, xb = xs[i], xs[i + 1]
        ya, yb = ys[j], ys[j + 1]
        za, zb = zs[k], zs[k + 1]
        if i == 0 or not occ[i - 1, j, k]:
            quad((xa, ya, za), (xa, ya, zb), (xa, yb, zb), (xa, yb, za))
        if i == nx - 1 or not occ[i + 1, j, k]:
            quad((xb, ya, za), (xb, yb, za), (xb, yb, zb), (xb, ya, zb))
        if j == 0 or not occ[i, j - 1, k]:
            quad((xa, ya, za), (xb, ya, za), (xb, ya, zb), (xa, ya, zb))
        if j == ny - 1 or not occ[i, j + 1, k]:
            quad((xa, yb, za), (xa, yb, zb), (xb, yb, zb), (xb, yb, za))
        if k == 0 or not occ[i, j, k - 1]:
            quad((xa, ya, za), (xa, yb, za), (xb, yb, za), (xb, ya, za))
        if k == nz - 1 or not occ[i, j, k + 1]:
            quad((xa, ya, zb), (xb, ya, zb), (xb, yb, zb), (xa, yb, zb))
    return triangles


def write_binary_stl(path: Path, triangles, transform=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = b"HawaGuard Mini - original parametric design".ljust(80, b" ")
    with path.open("wb") as fh:
        fh.write(header)
        fh.write(struct.pack("<I", len(triangles)))
        for a, b, c in triangles:
            if transform:
                a, b, c = transform(a), transform(b), transform(c)
            n = np.cross(b - a, c - a)
            norm = np.linalg.norm(n)
            if norm:
                n = n / norm
            fh.write(struct.pack("<12fH", *(n.tolist() + a.tolist() + b.tolist() + c.tolist()), 0))


def manifold_edge_report(triangles) -> tuple[int, int]:
    """Return (unique_edges, non_manifold_edges) using exact generated coordinates."""
    edge_counts: dict[tuple[tuple[float, ...], tuple[float, ...]], int] = {}
    for tri in triangles:
        vertices = [tuple(np.round(v, 5)) for v in tri]
        for a, b in ((vertices[0], vertices[1]), (vertices[1], vertices[2]), (vertices[2], vertices[0])):
            edge = tuple(sorted((a, b)))
            edge_counts[edge] = edge_counts.get(edge, 0) + 1
    bad = sum(1 for count in edge_counts.values() if count != 2)
    return len(edge_counts), bad


def _rotation_matrix(rx_deg=-62, rz_deg=-42):
    rx, rz = math.radians(rx_deg), math.radians(rz_deg)
    mx = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
    mz = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]])
    return mx @ mz


def _face_quads(b: Box):
    x0, x1, y0, y1, z0, z1 = b.x0, b.x1, b.y0, b.y1, b.z0, b.z1
    return [
        ([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], (-1, 0, 0)),
        ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
        ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
        ([(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)], (0, 1, 0)),
        ([(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)], (0, 0, -1)),
        ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
    ]


def _font(name: str, size: int):
    choices = {
        "regular": ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"],
        "semibold": ["C:/Windows/Fonts/seguisb.ttf", "C:/Windows/Fonts/arialbd.ttf"],
        "bold": ["C:/Windows/Fonts/seguisb.ttf", "C:/Windows/Fonts/arialbd.ttf"],
    }
    for candidate in choices[name]:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def render_isometric(boxes: list[Box], path: Path, title: str, subtitle: str, labels: list[tuple[str, tuple[int, int]]]):
    width, height, ss = 1600, 1000, 2
    w, h = width * ss, height * ss
    bg_top = np.array([247, 250, 252], dtype=float)
    bg_bottom = np.array([226, 242, 246], dtype=float)
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    for yy in range(h):
        t = yy / max(h - 1, 1)
        canvas[yy, :, :] = (bg_top * (1 - t) + bg_bottom * t).astype(np.uint8)
    img = Image.fromarray(canvas, "RGB")
    draw = ImageDraw.Draw(img, "RGBA")

    # Ground shadow and a soft halo behind the product.
    draw.ellipse((300 * ss, 710 * ss, 1320 * ss, 930 * ss), fill=(15, 23, 42, 28))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow, "RGBA")
    sdraw.ellipse((390 * ss, 730 * ss, 1250 * ss, 900 * ss), fill=(15, 23, 42, 58))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28 * ss))
    img = Image.alpha_composite(img.convert("RGBA"), shadow)
    draw = ImageDraw.Draw(img, "RGBA")

    rot = _rotation_matrix()
    all_vertices = np.array([[b.x0, b.y0, b.z0] for b in boxes] + [[b.x1, b.y1, b.z1] for b in boxes])
    rotated = all_vertices @ rot.T
    minx, miny = rotated[:, 0].min(), rotated[:, 1].min()
    maxx, maxy = rotated[:, 0].max(), rotated[:, 1].max()
    scale = min(780 * ss / (maxx - minx), 560 * ss / (maxy - miny))
    center = np.array([(minx + maxx) / 2, (miny + maxy) / 2])
    # Keep the product below the title band and give it a deliberate right bias.
    screen_center = np.array([960 * ss, 390 * ss])

    faces = []
    light = np.array([-0.35, -0.25, 0.9])
    light /= np.linalg.norm(light)
    for b in boxes:
        for points, normal in _face_quads(b):
            pts3 = np.array(points, float) @ rot.T
            n = np.array(normal, float) @ rot.T
            if n[2] <= 0.02:
                continue
            pts2 = (pts3[:, :2] - center) * scale + screen_center
            depth = pts3[:, 2].mean()
            brightness = 0.64 + 0.36 * max(0.0, float(np.dot(n, light)))
            color = tuple(min(255, int(c * brightness + 14)) for c in b.color)
            faces.append((depth, pts2, color, b.group))
    faces.sort(key=lambda item: item[0])
    for _, pts2, color, group in faces:
        poly = [(int(x), int(h - y)) for x, y in pts2]
        edge_alpha = 85 if group not in {"accent"} else 105
        draw.polygon(poly, fill=color + (255,), outline=(6, 52, 68, edge_alpha))

    # Title block.
    draw.text((92 * ss, 80 * ss), "HAWAGUARD MINI", font=_font("bold", 50 * ss), fill=(9, 78, 101, 255))
    draw.text((95 * ss, 146 * ss), title, font=_font("semibold", 23 * ss), fill=(30, 41, 59, 235))
    draw.text((95 * ss, 186 * ss), subtitle, font=_font("regular", 20 * ss), fill=(71, 85, 105, 235))
    draw.rounded_rectangle((95 * ss, 235 * ss, 438 * ss, 283 * ss), radius=18 * ss, fill=(34, 197, 94, 32), outline=(34, 197, 94, 190), width=2 * ss)
    draw.text((120 * ss, 246 * ss), "PROTOTYPE-READY CAD DESIGN", font=_font("semibold", 15 * ss), fill=(21, 128, 61, 255))

    for text, (x, y) in labels:
        x, y = x * ss, y * ss
        tw = draw.textbbox((0, 0), text, font=_font("semibold", 16 * ss))[2]
        draw.rounded_rectangle((x, y, x + tw + 30 * ss, y + 42 * ss), radius=13 * ss, fill=(255, 255, 255, 226), outline=(14, 116, 144, 105), width=2 * ss)
        draw.text((x + 15 * ss, y + 10 * ss), text, font=_font("semibold", 16 * ss), fill=(15, 80, 101, 255))

    draw.text((95 * ss, 928 * ss), "Prepared for Waqas Khan  |  AI-assisted CAD concept  |  September 2026", font=_font("regular", 16 * ss), fill=(71, 85, 105, 230))
    img = img.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    img.save(path, quality=95)


def render_dimension_sheet(base: list[Box], lid: list[Box], path: Path):
    width, height = 1600, 1000
    img = Image.new("RGB", (width, height), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    navy, teal, muted, green = (15, 23, 42), (14, 116, 144), (71, 85, 105), (34, 197, 94)
    draw.text((80, 58), "HAWAGUARD MINI - DIMENSIONED DESIGN", font=_font("bold", 43), fill=navy)
    draw.text((82, 118), "Two-part, support-free enclosure for a low-cost ESP32 air-quality monitor", font=_font("regular", 22), fill=muted)

    panels = [(80, 205, 760, 790), (840, 205, 1520, 790)]
    for panel in panels:
        draw.rounded_rectangle(panel, radius=24, fill=(255, 255, 255), outline=(203, 213, 225), width=2)

    # Top view - lid footprint and screen opening.
    draw.text((120, 245), "TOP VIEW / LID", font=_font("semibold", 23), fill=teal)
    sx, sy, sc = 180, 370, 5.05
    ow, od = 95.6 * sc, 69.6 * sc
    draw.rounded_rectangle((sx, sy, sx + ow, sy + od), radius=18, fill=(226, 242, 246), outline=teal, width=4)
    wx = sx + (47.8 + 5.5) * sc
    wy = sy + (34.8 - 19.5) * sc
    draw.rectangle((wx, wy, wx + 29 * sc, wy + 15 * sc), fill=(248, 250, 252), outline=green, width=4)
    draw.text((wx + 8, wy + 24), "OLED", font=_font("semibold", 16), fill=(21, 128, 61))
    draw.line((sx, sy + od + 55, sx + ow, sy + od + 55), fill=navy, width=2)
    draw.line((sx, sy + od + 42, sx, sy + od + 68), fill=navy, width=2)
    draw.line((sx + ow, sy + od + 42, sx + ow, sy + od + 68), fill=navy, width=2)
    draw.text((sx + ow / 2 - 45, sy + od + 68), "95.6 mm", font=_font("semibold", 18), fill=navy)
    draw.line((sx - 58, sy, sx - 58, sy + od), fill=navy, width=2)
    draw.line((sx - 70, sy, sx - 45, sy), fill=navy, width=2)
    draw.line((sx - 70, sy + od, sx - 45, sy + od), fill=navy, width=2)
    draw.text((sx - 120, sy + od / 2 - 10), "69.6 mm", font=_font("semibold", 18), fill=navy)

    # Front view - assembled height and vents.
    draw.text((880, 245), "FRONT / ASSEMBLED", font=_font("semibold", 23), fill=teal)
    fx, fy, fsc = 930, 365, 5.0
    fw, fh = 95.6 * fsc, 42 * fsc
    draw.rounded_rectangle((fx, fy, fx + fw, fy + fh), radius=15, fill=(226, 242, 246), outline=teal, width=4)
    draw.rectangle((fx + 10, fy + fh - 62, fx + fw - 10, fy + fh), fill=(207, 250, 232), outline=green, width=3)
    for yy in range(0, 5):
        y = fy + 45 + yy * 26
        draw.line((fx + 18, y, fx + 108, y), fill=teal, width=7)
        draw.line((fx + fw - 108, y, fx + fw - 18, y), fill=teal, width=7)
    draw.line((fx + fw + 58, fy, fx + fw + 58, fy + fh), fill=navy, width=2)
    draw.line((fx + fw + 45, fy, fx + fw + 70, fy), fill=navy, width=2)
    draw.line((fx + fw + 45, fy + fh, fx + fw + 70, fy + fh), fill=navy, width=2)
    draw.text((fx + fw + 78, fy + fh / 2 - 10), "42 mm", font=_font("semibold", 18), fill=navy)

    # Bottom spec strip.
    specs = [
        ("2 PARTS", "Base tray + vented lid"),
        ("2.4 MM", "Wall thickness"),
        ("0.35 MM", "Friction-rib engagement"),
        ("NO SUPPORTS", "Both parts print flat"),
    ]
    x = 80
    for label, detail in specs:
        draw.rounded_rectangle((x, 835, x + 350, 940), radius=18, fill=(255, 255, 255), outline=(203, 213, 225), width=2)
        draw.text((x + 22, 856), label, font=_font("bold", 23), fill=teal)
        draw.text((x + 22, 895), detail, font=_font("regular", 17), fill=muted)
        x += 375
    img.save(path, quality=95)


def main():
    base = base_boxes()
    lid = lid_boxes()
    base_triangles = union_surface_triangles(base)
    lid_triangles = union_surface_triangles(lid)
    base_edges, base_bad = manifold_edge_report(base_triangles)
    lid_edges, lid_bad = manifold_edge_report(lid_triangles)
    if base_bad or lid_bad:
        raise RuntimeError(f"STL manifold check failed: base={base_bad}, lid={lid_bad}")
    write_binary_stl(OUT / "HawaGuard_Mini_Base.stl", base_triangles)
    write_binary_stl(OUT / "HawaGuard_Mini_Lid.stl", lid_triangles, transform=lambda p: np.array([p[0], p[1], 35.2 - p[2]]))

    assembled = base + [b.translated(dz=8) for b in lid]
    exploded = base + [b.translated(dz=31) for b in lid]
    render_isometric(
        assembled,
        OUT / "HawaGuard_Mini_Hero.png",
        "3D-printed classroom air-quality sensor enclosure",
        "A compact shell for ESP32, particulate, temperature and humidity sensing",
        [("Cross-flow vents", (1190, 380)), ("OLED window", (1190, 442)), ("Tool-free fit", (1190, 504))],
    )
    render_isometric(
        exploded,
        OUT / "HawaGuard_Mini_Exploded.png",
        "Exploded assembly view",
        "Two printable parts, internal module rails and a rear USB cable relief",
        [("Vented lid", (1190, 370)), ("Mounting rails", (1190, 432)), ("Base tray", (1190, 494))],
    )
    render_dimension_sheet(base, lid, OUT / "HawaGuard_Mini_Dimensions.png")
    with Image.open(OUT / "HawaGuard_Mini_Hero.png") as source:
        source.crop((450, 285, 1510, 930)).save(OUT / "HawaGuard_Mini_Product.png")
    with Image.open(OUT / "HawaGuard_Mini_Exploded.png") as source:
        source.crop((500, 245, 1480, 930)).save(OUT / "HawaGuard_Mini_Exploded_Crop.png")

    (OUT / "PRINT_AND_ASSEMBLY_NOTES.txt").write_text(
        """HAWAGUARD MINI - PRINT AND ASSEMBLY NOTES

Prepared for: Waqas Khan (AI-assisted CAD workflow)
Status: Original CAD concept generated September 2026; not yet physically printed or validated.

PURPOSE
A compact two-part enclosure for a classroom air-quality monitor based on an ESP32, a compact particulate sensor, a temperature/humidity sensor, and a 0.96-inch OLED display.

PRINT PROFILE
- Material: PETG recommended; PLA suitable for indoor demonstration.
- Nozzle: 0.4 mm
- Layer height: 0.20 mm
- Perimeters: 3
- Infill: 15-20% gyroid
- Supports: none
- Base orientation: floor on build plate
- Lid orientation: display face on build plate (already oriented in STL)

DESIGN DETAILS
- Overall assembled size: approximately 95.6 x 69.6 x 42 mm
- Nominal wall thickness: 2.4 mm
- Cross-flow side ventilation for particulate sampling
- 29 x 15 mm OLED opening with raised protective bezel
- Rear 14 mm USB cable relief
- Friction-fit ribs with nominal 0.35 mm engagement
- Internal mounting rails allow adhesive tape, clips, or small prototype boards

VALIDATION PLAN
1. Slice both STLs and inspect wall continuity.
2. Print a fit coupon or the first 8 mm of both parts.
3. Adjust global XY compensation if the lid is too tight or loose.
4. Assemble electronics and verify unobstructed airflow.
5. Compare sensor readings with a reference monitor and document results.
""",
        encoding="utf-8",
    )

    print(
        f"Generated {len(base_triangles):,} base triangles / {base_edges:,} manifold edges "
        f"and {len(lid_triangles):,} lid triangles / {lid_edges:,} manifold edges"
    )
    for item in sorted(OUT.iterdir()):
        print(f"{item.name}: {item.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
