# Trollmeme Prospekt

Durchsuchbare GIF-Bibliothek: https://goldkunibert.github.io/trollmeme/

Bild anklicken, dann in Discord mit Strg+V einfügen.

## WhatsApp-Sticker

Im Ordner [`sticker/`](sticker/) liegen alle Bilder als WhatsApp-Sticker-Packs (`.wastickers`), eins oder mehrere pro Kategorie (maximal 30 Sticker pro Pack). Auf der Website steht bei jedem Bild, in welchem Pack es steckt, und im Groß-Dialog gibt es das Pack zum Herunterladen.

1. Die gewünschte `.wastickers`-Datei aufs Handy laden.
2. Mit der App [Sticker Maker](https://stickermakerapp.xyz) öffnen bzw. importieren.
3. In Sticker Maker auf „Zu WhatsApp hinzufügen“ tippen.

Neu erzeugen, z. B. nachdem neue GIFs dazugekommen sind: `python3 sticker/make_stickers.py` (braucht Pillow). Das Skript schreibt auch `sticker/packs.json`, aus der die Website die Pack-Zuordnung liest.
