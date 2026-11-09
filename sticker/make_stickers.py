#!/usr/bin/env python3
"""Baut WhatsApp-Sticker-Packs (.wastickers) aus den GIFs.

Aufruf aus dem Repo-Hauptordner:

    python3 sticker/make_stickers.py

Pro Kategorie aus data.json entstehen ein oder mehrere Packs mit höchstens
30 Stickern (WhatsApp-Limit). Jede .wastickers-Datei ist ein ZIP mit
title.txt, author.txt, cover.png (96x96, Text-Icon
"Memes <Kategorie>" plus ggf. "1/3") und den Stickern als 512x512-WebP
mit transparentem Rand. Statische Sticker bleiben unter 100 KB.

Benötigt Pillow (pip install pillow).
"""

import io
import json
import math
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sticker"
AUTHOR = "Trollmeme Prospekt"
TITLE_PREFIX = "Memes"

SIZE = 512
MARGIN = 8               # transparenter Rand rund um das Bild
MAX_STATIC = 100_000     # WhatsApp: statische Sticker < 100 KB
MAX_PER_PACK = 30        # WhatsApp: 3 bis 30 Sticker pro Pack
COVER_SIZE = 96
COVER_SCALE = 4          # Icon groß zeichnen und dann verkleinern (glattere Schrift)
COVER_COLORS = ["#e63946", "#f4a261", "#2a9d8f", "#457b9d", "#8e44ad", "#d35400",
                "#16a085", "#c0392b", "#27ae60", "#2c3e50", "#b8860b", "#555555"]
FONTS = [
    "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
MAX_COVER = 50_000
ZIP_TIME = (2020, 1, 1, 0, 0, 0)  # feste Zeit, damit Neu-Erzeugen keine Diffs macht


def gif_path(item):
    return ROOT / "gifs" / (item.get("p") or item["c"]) / f"{item['n']}.gif"


def to_square(frame):
    """Skaliert ein Bild in ein 512x512-Feld und zentriert es auf transparentem Grund."""
    frame = frame.convert("RGBA")
    box = SIZE - 2 * MARGIN
    scale = min(box / frame.width, box / frame.height)
    w, h = max(1, round(frame.width * scale)), max(1, round(frame.height * scale))
    frame = frame.resize((w, h), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(frame, ((SIZE - w) // 2, (SIZE - h) // 2), frame)
    return canvas


def pick_frame(im):
    """Erstes Bild, bei animierten GIFs das Bild aus der Mitte (zeigt meist mehr)."""
    n = getattr(im, "n_frames", 1)
    im.seek(n // 2 if n > 1 else 0)
    return im.copy()


def encode_webp(img, limit):
    for quality in range(92, 9, -6):
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=quality, method=6)
        if buf.tell() < limit:
            return buf.getvalue()
    raise ValueError("Sticker bleibt über dem Größenlimit")


def find_font():
    for path in FONTS:
        if Path(path).exists():
            return path
    raise FileNotFoundError("Keine fette Schrift gefunden, bitte FONTS ergänzen")


def wrap(draw, words, font, width):
    lines = []
    for word in words:
        if lines and draw.textlength(f"{lines[-1]} {word}", font=font) <= width:
            lines[-1] += f" {word}"
        else:
            lines.append(word)
    return lines


def make_cover(label, part, color):
    """Text-Icon: "Memes", Kategoriename und ggf. "1/3" auf farbigem Grund."""
    s = COVER_SIZE * COVER_SCALE
    pad = round(s * 0.08)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, s - 1, s - 1), radius=round(s * 0.2), fill=color)
    font_path = find_font()

    small = ImageFont.truetype(font_path, round(s * 0.17))
    top = pad
    bottom = s - pad
    draw.text((s / 2, top), "Memes", font=small, fill="white", anchor="mt")
    top += round(s * 0.24)
    if part:
        draw.text((s / 2, bottom), part, font=small, fill="white", anchor="mb")
        bottom -= round(s * 0.24)

    # größte Schrift, bei der der Kategoriename in den Platz dazwischen passt
    words = label.split()
    for size in range(round(s * 0.22), 8, -2):
        font = ImageFont.truetype(font_path, size)
        lines = wrap(draw, words, font, s - 2 * pad)
        line_h = round(size * 1.1)
        fits = all(draw.textlength(l, font=font) <= s - 2 * pad for l in lines)
        if fits and line_h * len(lines) <= bottom - top:
            break
    y = (top + bottom - line_h * len(lines)) / 2
    for line in lines:
        draw.text((s / 2, y + line_h / 2), line, font=font, fill="white", anchor="mm")
        y += line_h
    return img


def encode_cover(img):
    cover = img.resize((COVER_SIZE, COVER_SIZE), Image.LANCZOS)
    buf = io.BytesIO()
    cover.save(buf, "PNG", optimize=True)
    if buf.tell() >= MAX_COVER:
        buf = io.BytesIO()
        cover.quantize(128).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def write_entry(zf, name, data):
    info = zipfile.ZipInfo(name, ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(info, data)


def split(items):
    """Teilt eine Liste gleichmäßig in Stücke von höchstens MAX_PER_PACK."""
    parts = math.ceil(len(items) / MAX_PER_PACK)
    size = math.ceil(len(items) / parts)
    return [items[k:k + size] for k in range(0, len(items), size)]


def plan(data):
    """Legt fest, welches Bild in welchem Pack landet."""
    packs = []
    for nr, cat in enumerate(data["cats"], 1):
        parts = split([x for x in data["items"] if x["c"] == cat["slug"]])
        for k, items in enumerate(parts, 1):
            part = f"{k}/{len(parts)}" if len(parts) > 1 else ""
            name = f"{nr:02d}-{cat['slug']}" + (f"-{k}" if len(parts) > 1 else "")
            packs.append({
                "title": f"{TITLE_PREFIX} {cat['label']} {part}".strip(),
                "file": f"{name}.wastickers",
                "label": cat["label"],
                "part": part,
                "color": COVER_COLORS[(nr - 1) % len(COVER_COLORS)],
                "items": items,
            })
    return packs


def write_index(packs):
    """packs.json für die Website: Liste der Packs und Bild-ID -> Pack-Nummer."""
    index = {
        "packs": [{"t": p["title"], "f": p["file"]} for p in packs],
        "items": {str(x["i"]): n for n, p in enumerate(packs) for x in p["items"]},
    }
    text = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    (OUT / "packs.json").write_text(text + "\n", encoding="utf-8")


def main():
    data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    packs = plan(data)
    write_index(packs)
    for old in OUT.glob("*.wastickers"):
        old.unlink()

    total = 0
    for p in packs:
        target = OUT / p["file"]
        with zipfile.ZipFile(target, "w") as zf:
            write_entry(zf, "title.txt", p["title"])
            write_entry(zf, "author.txt", AUTHOR)
            cover = make_cover(p["label"], p["part"], p["color"])
            write_entry(zf, "cover.png", encode_cover(cover))
            for j, item in enumerate(p["items"]):
                with Image.open(gif_path(item)) as im:
                    img = to_square(pick_frame(im))
                write_entry(zf, f"{j + 1:02d}.webp", encode_webp(img, MAX_STATIC))

        total += len(p["items"])
        kb = target.stat().st_size // 1024
        print(f"{target.name}: {p['title']} ({len(p['items'])} Sticker, {kb} KB)")

    print(f"Fertig: {total} Sticker", file=sys.stderr)


if __name__ == "__main__":
    main()
