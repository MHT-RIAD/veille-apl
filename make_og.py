#!/usr/bin/env python3
"""Genere docs/og.png : carte de statut partageable (thème clair Swiss)."""
import json
import datetime
from PIL import Image, ImageDraw, ImageFont

DATA_FILE = "docs/data.json"
OUT = "docs/og.png"
W, H = 1200, 630
PAPER = (255, 255, 255)
INK = (17, 19, 21)
RED = (228, 0, 43)
MUTED = (120, 125, 132)
HAIR = (220, 220, 220)


def font(size, bold=False):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else ""),
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif%s.ttf" % ("-Bold" if bold else "")]:
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
    accent = RED if high else INK
    verdict = "Décret probablement publié" if high else "Pas encore publié"

    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=RED)
    d.text((70, 92), "VEILLE · DÉCRET APL ÉTUDIANTS ÉTRANGERS", font=font(24, True), fill=RED)
    d.line([70, 150, W - 70, 150], fill=HAIR, width=1)
    d.text((70, 196), "Le décret est-il sorti ?", font=font(40, True), fill=INK)

    vsize = 86
    while vsize > 32:
        vf = font(vsize, True)
        if d.textlength(verdict, font=vf) <= W - 140:
            break
        vsize -= 2
    d.text((70, 290), verdict, font=font(vsize, True), fill=accent)

    total = len(data.get("alerts", []))
    d.text((70, 440), "%d alertes au total · %d signaux forts" % (total, high), font=font(28), fill=MUTED)
    lc = data.get("last_check")
    when = ""
    if lc:
        try:
            t = datetime.datetime.strptime(lc, "%Y-%m-%dT%H:%M:%SZ")
            when = "Mis à jour le %s" % t.strftime("%d/%m/%Y")
        except Exception:
            when = ""
    d.text((70, 528), when, font=font(24), fill=MUTED)
    d.text((70, 566), "Loi de finances 2026 · art. 179", font=font(22), fill=MUTED)
    img.save(OUT)
    print("OG genere :", OUT)
    make_icons()


def make_icons():
    for size in (192, 512):
        ic = Image.new("RGB", (size, size), RED)
        d = ImageDraw.Draw(ic)
        f = font(int(size * 0.30), True)
        txt = "APL"
        w = d.textlength(txt, font=f)
        d.text(((size - w) / 2, size * 0.34), txt, font=f, fill=(255, 255, 255))
        ic.save("docs/icon-%d.png" % size)
    print("Icones PWA generees.")


if __name__ == "__main__":
    main()
