#!/usr/bin/env python3
"""Brief quotidien : synthese IA des alertes des dernieres 24h.

Optionnel. Actif seulement si ANTHROPIC_API_KEY est defini. Lit docs/data.json,
demande a Claude un resume en francais, l'envoie sur Telegram et l'ecrit dans
docs/digest.json (affiche par le dashboard). Ne modifie jamais data.json.
"""
import os
import json
import html
import datetime
import urllib.request

DATA_FILE = "docs/data.json"
DIGEST_FILE = "docs/digest.json"
WINDOW_HOURS = 24

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


def recent_alerts(data):
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=WINDOW_HOURS)
    out = []
    for a in data.get("alerts", []):
        try:
            t = datetime.datetime.strptime(a["found_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        except Exception:
            continue
        if t >= cutoff:
            out.append(a)
    return out


def claude_digest(alerts):
    lignes = []
    for a in alerts:
        lignes.append("- [%s] %s (%s)%s" % (
            a.get("topic_name", "?"), a.get("title", ""), a.get("source", ""),
            (" — " + a["summary"]) if a.get("summary") else ""))
    prompt = (
        "Tu rediges un brief de veille en francais, ton sobre et factuel. "
        "Voici les articles/textes detectes ces dernieres 24h sur des sujets juridiques suivis. "
        "Fais une synthese de 4 a 6 phrases : ce qui a bouge, le signal le plus important, "
        "et s'il y a un signe de publication d'un decret. Pas de liste, un paragraphe.\n\n"
        + "\n".join(lignes))
    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 600,
        "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read())
    return "".join(b.get("text", "") for b in d.get("content", [])).strip()


def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    import urllib.parse
    url = "https://api.telegram.org/bot%s/sendMessage" % TELEGRAM_TOKEN
    payload = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": "true"}).encode()
    urllib.request.urlopen(urllib.request.Request(url, data=payload), timeout=30)


def main():
    if not ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY absent : brief IA desactive.")
        return
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Pas de data.json.")
        return
    alerts = recent_alerts(data)
    if not alerts:
        print("Aucune alerte sur 24h : pas de brief.")
        return
    try:
        text = claude_digest(alerts)
    except Exception as e:
        print("Brief IA indisponible :", e)
        return
    digest = {"generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "count": len(alerts), "text": text}
    os.makedirs(os.path.dirname(DIGEST_FILE), exist_ok=True)
    with open(DIGEST_FILE, "w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)
    send_telegram("\U0001F4F0 <b>Brief du jour</b> (%d alertes / 24h)\n\n%s" % (len(alerts), html.escape(text)))
    print("Brief genere (%d alertes)." % len(alerts))


if __name__ == "__main__":
    main()
