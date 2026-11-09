#!/usr/bin/env python3
"""Baut WhatsApp-Sticker-Packs (.wastickers) aus den GIFs.

Aufruf aus dem Repo-Hauptordner:

    python3 sticker/make_stickers.py

Pro Kategorie aus data.json entstehen ein oder mehrere Packs mit höchstens
30 Stickern (WhatsApp-Limit). Jede .wastickers-Datei ist ein ZIP mit
title.txt, author.txt, cover.png (96x96) und den Stickern als 512x512-WebP
mit transparentem Rand. Statische Sticker bleiben unter 100 KB.

Benötigt Pillow (pip install pillow).
"""

import io
import json
import math
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageSequence

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sticker"
AUTHOR = "Trollmeme Prospekt"
TITLE_PREFIX = "Trollmeme"

SIZE = 512
MARGIN = 8               # transparenter Rand rund um das Bild
MAX_STATIC = 100_000     # WhatsApp: statische Sticker < 100 KB
MAX_PER_PACK = 30        # WhatsApp: 3 bis 30 Sticker pro Pack
COVER_SIZE = 96
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


def main():
    data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    for old in OUT.glob("*.wastickers"):
        old.unlink()

    total = 0
    for nr, cat in enumerate(data["cats"], 1):
        items = [x for x in data["items"] if x["c"] == cat["slug"]]
        packs = split(items)
        for k, pack in enumerate(packs, 1):
            suffix = f" {k}/{len(packs)}" if len(packs) > 1 else ""
            title = f"{TITLE_PREFIX} {cat['label']}{suffix}"
            name = f"{nr:02d}-{cat['slug']}" + (f"-{k}" if len(packs) > 1 else "")
            target = OUT / f"{name}.wastickers"

            with zipfile.ZipFile(target, "w") as zf:
                write_entry(zf, "title.txt", title)
                write_entry(zf, "author.txt", AUTHOR)
                for j, item in enumerate(pack):
                    with Image.open(gif_path(item)) as im:
                        img = to_square(pick_frame(im))
                    if j == 0:
                        write_entry(zf, "cover.png", encode_cover(img))
                    write_entry(zf, f"{j + 1:02d}.webp", encode_webp(img, MAX_STATIC))

            total += len(pack)
            kb = target.stat().st_size // 1024
            print(f"{target.name}: {title} ({len(pack)} Sticker, {kb} KB)")

    print(f"Fertig: {total} Sticker", file=sys.stderr)


if __name__ == "__main__":
    main()
