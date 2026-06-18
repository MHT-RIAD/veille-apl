#!/usr/bin/env python3
"""Genere docs/og.png : carte de statut partageable refletant l'etat de la veille."""
import json
import datetime
from PIL import Image, ImageDraw, ImageFont

DATA_FILE = "docs/data.json"
OUT = "docs/og.png"
W, H = 1200, 630
BG = (15, 22, 38)
SEAL = (212, 169, 79)
HIGH = (255, 93, 93)
TEXT = (232, 236, 245)
MUTED = (139, 150, 173)


def font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif%s.ttf" % ("-Bold" if bold else ""),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else ""),
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def main():
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"alerts": [], "last_check": None}
    high = sum(1 for a in data.get("alerts", []) if a.get("priority") == "high")
    accent = HIGH if high else SEAL
    verdict = "Décret probablement publié" if high else "Pas encore publié"

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=accent)
    d.text((70, 90), "VEILLE · DÉCRET APL ÉTUDIANTS ÉTRANGERS", font=font(26), fill=MUTED)
    d.ellipse([70, 200, 104, 234], fill=accent)
    d.text((120, 196), "Le décret est-il sorti ?", font=font(40, True), fill=TEXT)
    # ajuste la taille du verdict pour tenir dans la largeur
    vsize = 74
    while vsize > 32:
        vf = font(vsize, True)
        if d.textlength(verdict, font=vf) <= W - 140:
            break
        vsize -= 2
    d.text((70, 300), verdict, font=font(vsize, True), fill=accent)
    total = len(data.get("alerts", []))
    d.text((70, 430), "%d alertes au total · %d signaux forts" % (total, high), font=font(30), fill=MUTED)
    lc = data.get("last_check")
    when = ""
    if lc:
        try:
            t = datetime.datetime.strptime(lc, "%Y-%m-%dT%H:%M:%SZ")
            when = "Mis à jour le %s" % t.strftime("%d/%m/%Y")
        except Exception:
            when = ""
    d.text((70, 520), when, font=font(26), fill=MUTED)
    d.text((70, 560), "Loi de finances 2026 · art. 179", font=font(24), fill=MUTED)
    img.save(OUT)
    print("OG genere :", OUT)
    make_icons()


def make_icons():
    for size in (192, 512):
        ic = Image.new("RGB", (size, size), BG)
        d = ImageDraw.Draw(ic)
        r = int(size * 0.16)
        cx, cy = size // 2, int(size * 0.40)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=SEAL)
        f = font(int(size * 0.22), True)
        txt = "APL"
        w = d.textlength(txt, font=f)
        d.text(((size - w) / 2, int(size * 0.60)), txt, font=f, fill=TEXT)
        ic.save("docs/icon-%d.png" % size)
    print("Icones PWA generees.")


if __name__ == "__main__":
    main()
