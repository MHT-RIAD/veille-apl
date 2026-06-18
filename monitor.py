#!/usr/bin/env python3
"""Veille legislative v3 : multi-sujets, confiance, dedoublonnage, intensification,
push (Telegram + ntfy), battement de coeur, resume du texte officiel.

Sources par sujet (topics.json) : presse (Google News RSS, tri local),
texte officiel (API Legifrance/JORF, optionnel), pages officielles surveillees.
Dependances : bibliotheque standard uniquement.

Variables d'environnement :
  TELEGRAM_TOKEN, TELEGRAM_CHAT_ID     (obligatoires)
  NTFY_TOPIC                           (optionnel : push via ntfy.sh/<topic>)
  PISTE_CLIENT_ID, PISTE_CLIENT_SECRET (optionnel : source officielle JORF)
  ANTHROPIC_API_KEY                    (optionnel : resume du texte officiel)
  FETCH_SUMMARY = "0"                  (optionnel : coupe les resumes de presse)
"""
import os
import re
import time
import json
import html
import hashlib
import functools
import datetime
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

STATE_FILE = "seen.json"
TOPICS_FILE = "topics.json"
PAGES_FILE = "pages.json"
PAGES_STATE = "pages_state.json"
DATA_FILE = "docs/data.json"
MAX_HISTORY = 1500
DEDUP_HOURS = 48
HEARTBEAT_DAYS = 7

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
FETCH_SUMMARY = os.environ.get("FETCH_SUMMARY", "1") != "0"

try:
    import legifrance
except Exception:
    legifrance = None

# Confiance : termes qui confirment une publication vs simples annonces.
CONFIRM_TERMS = ["paru au journal officiel", "publie au journal officiel", "au journal officiel",
                 "est entre en vigueur", "entre en vigueur le", "a ete publie", "a ete promulgue",
                 "decret publie", "decret promulgue", "promulgue", "publication d'un decret",
                 "tout juste promulgue", "parution au journal officiel", "publie au jo", "paru au jo"]
RUMOR_TERMS = ["devrait", "pourrait", "attendu", "prevu", "va etre", "projet de decret",
               "en preparation", "envisage", "bientot", "prochainement", "selon nos informations",
               "se prepare", "a venir"]
# Termes qui indiquent un report/suspension/annulation ou une negation de publication.
POSTPONE_TERMS = ["reporte", "report", "suspendu", "suspension", "abandonne", "retire",
                  "annule", "gele", "moratoire", "pas encore", "ne sera pas", "n'est pas",
                  "ne sont pas", "ne serait pas", "recule"]


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def now_iso():
    return now().strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm(s):
    return strip_accents(s or "").lower()


def contains_any(text, terms):
    return any(term_in(text, t) for t in terms)


@functools.lru_cache(maxsize=8192)
def _term_re(term):
    # debut de mot (pas precede d'alphanum) ; suffixe libre -> gere les pluriels
    return re.compile(r"(?<![a-z0-9])" + re.escape(term))


def term_in(text, term):
    """text est deja normalise (minuscule sans accents)."""
    return _term_re(norm(term)).search(text) is not None


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, obj):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# ---------- Tri + confiance ----------
def matched_terms(title, rules):
    t = norm(title)
    out, seen = [], set()
    for key in ("groupe_a", "groupe_b", "signaux"):
        for term in rules.get(key, []):
            if term_in(t, term) and term not in seen:
                seen.add(term)
                out.append(term)
    return out


def classify(title, rules):
    """Renvoie (alerter, priorite, label, confiance)."""
    t = norm(title)
    if contains_any(t, rules.get("exclusions", [])):
        return False, None, "", ""
    if not (contains_any(t, rules.get("groupe_a", [])) and contains_any(t, rules.get("groupe_b", []))):
        return False, None, "", ""
    has_signal = contains_any(t, rules.get("signaux", []))
    if contains_any(t, POSTPONE_TERMS) and (has_signal or contains_any(t, CONFIRM_TERMS)):
        return True, "related", "Report / suspension ?", "report"
    if contains_any(t, CONFIRM_TERMS):
        return True, "high", "Decret confirme", "confirme"
    if has_signal and contains_any(t, RUMOR_TERMS):
        return True, "related", "Annonce a confirmer", "rumeur"
    if has_signal:
        return True, "high", "Probable decret", "probable"
    return True, "related", "Sujet lie", "lie"


_WORD = re.compile(r"[a-z0-9]+")
# Synonymes ramenes a une forme canonique pour mieux regrouper les memes infos.
_SYNO = {"paru": "publie", "parue": "publie", "parus": "publie", "publiee": "publie",
         "publication": "publie", "promulgue": "publie", "promulguee": "publie",
         "parution": "publie", "sorti": "publie", "sortie": "publie"}


def title_key(title):
    """Cle de regroupement : ensemble trie des mots significatifs (insensible a l'ordre,
    synonymes de publication canonicalises)."""
    words = _WORD.findall(norm(title))
    stop = {"le", "la", "les", "des", "de", "du", "un", "une", "et", "a", "au", "aux",
            "pour", "sur", "en", "ce", "qui", "the", "of", "leur", "sa", "son", "ses",
            "est", "sont", "dans", "par", "avec", "ou"}
    sig = sorted(set(_SYNO.get(w, w) for w in words if w not in stop and len(w) > 2))
    return " ".join(sig)


# ---------- HTTP / resume ----------
class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og = None
        self.desc = None

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        d = {k.lower(): (v or "") for k, v in attrs}
        if d.get("property", "").lower() == "og:description" and d.get("content") and not self.og:
            self.og = d["content"]
        elif d.get("name", "").lower() == "description" and d.get("content") and not self.desc:
            self.desc = d["content"]


def _open(req, timeout, retries=2):
    """urlopen avec quelques reessais (erreurs reseau transitoires)."""
    err = None
    for i in range(retries + 1):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except Exception as e:
            err = e
            time.sleep(1.0 * (i + 1))
    raise err


def fetch_html(url, cap=300000, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with _open(req, timeout) as r:
        if "html" not in r.headers.get("Content-Type", "").lower():
            return ""
        return r.read(cap).decode("utf-8", "replace")


def extract_summary(url):
    if not FETCH_SUMMARY or not url:
        return ""
    try:
        p = _MetaParser()
        p.feed(fetch_html(url))
        return html.unescape((p.og or p.desc or "").strip())[:320]
    except Exception as e:
        print("Resume presse indisponible :", e)
        return ""


_TAGS = re.compile(r"(?is)<(script|style|noscript|svg).*?</\1>")
_HTMLTAG = re.compile(r"(?s)<[^>]+>")
_WS = re.compile(r"\s+")
_DIGITS = re.compile(r"\d+")


def page_text(url, cap=600000, timeout=20, start=None, end=None):
    raw = fetch_html(url, cap=cap, timeout=timeout)
    if not raw:
        return ""
    if start and start in raw:
        raw = raw.split(start, 1)[1]
    if end and end in raw:
        raw = raw.split(end, 1)[0]
    text = _TAGS.sub(" ", raw)
    text = _HTMLTAG.sub(" ", text)
    text = html.unescape(text)
    return _WS.sub(" ", text).strip()


def page_fingerprint(url, start=None, end=None):
    """Empreinte stable : region ciblee (optionnelle) + suppression des chiffres."""
    t = page_text(url, start=start, end=end)
    if not t:
        return None
    t = _DIGITS.sub("", t)
    return hashlib.sha256(t.encode("utf-8", "replace")).hexdigest()


def summarize_official(url):
    """Resume IA du texte officiel (optionnel)."""
    if not ANTHROPIC_API_KEY:
        return ""
    try:
        txt = page_text(url, cap=400000, timeout=25)
        if len(txt) < 400:
            return ""
        prompt = ("Resume en francais, 3 phrases sobres, ce que change ce texte officiel "
                  "(qui est concerne, dates cles). Texte :\n\n" + txt[:8000])
        body = json.dumps({"model": "claude-haiku-4-5-20251001", "max_tokens": 400,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
                                     headers={"x-api-key": ANTHROPIC_API_KEY,
                                              "anthropic-version": "2023-06-01",
                                              "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.loads(r.read())
        return "".join(b.get("text", "") for b in d.get("content", [])).strip()[:600]
    except Exception as e:
        print("Resume officiel indisponible :", e)
        return ""


# ---------- Presse RSS ----------
def parse_item(item):
    title = item.findtext("title", "") or ""
    link = item.findtext("link", "") or ""
    pub = item.findtext("pubDate", "") or ""
    src_el = item.find("source")
    source = (src_el.text if src_el is not None and src_el.text else "")
    if source and title.endswith(" - " + source):
        title = title[: -(len(source) + 3)]
    elif " - " in title:
        base, _, tail = title.rpartition(" - ")
        if base and not source:
            source, title = tail, base
    return {"title": html.unescape(title.strip()), "source": html.unescape(source.strip()),
            "link": link, "pubDate": pub}


def fetch_rss(query):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "fr", "gl": "FR", "ceid": "FR:fr"})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with _open(req, 30) as r:
        root = ET.fromstring(r.read())
    return [parse_item(it) for it in root.iter("item")]


# ---------- Notifications ----------
def send_telegram(text):
    try:
        url = "https://api.telegram.org/bot%s/sendMessage" % TELEGRAM_TOKEN
        payload = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID, "text": text,
            "parse_mode": "HTML", "disable_web_page_preview": "true"}).encode()
        urllib.request.urlopen(urllib.request.Request(url, data=payload), timeout=30)
    except Exception as e:
        print("Telegram KO :", e)


def send_ntfy(title, body, priority="default", tags="bell"):
    if not NTFY_TOPIC:
        return
    try:
        req = urllib.request.Request(
            "https://ntfy.sh/" + NTFY_TOPIC, data=body.encode("utf-8"),
            headers={"Title": title.encode("utf-8").decode("latin-1", "ignore"),
                     "Priority": priority, "Tags": tags})
        urllib.request.urlopen(req, timeout=20)
    except Exception as e:
        print("ntfy KO :", e)


EMOJI = {"high": "\U0001F534", "related": "\U0001F7E1"}


def main():
    cfg = load_json(TOPICS_FILE, {"topics": []})
    topics = cfg.get("topics", [])
    pages = load_json(PAGES_FILE, {"pages": []}).get("pages", [])
    topic_by_id = {t["id"]: t for t in topics}

    first_run = not os.path.exists(STATE_FILE)
    seen = set(load_json(STATE_FILE, []))
    pstate = load_json(PAGES_STATE, {})
    data = load_json(DATA_FILE, {"last_check": None, "alerts": [], "spikes": [],
                                 "last_alert_at": None, "last_heartbeat": None})
    data.setdefault("spikes", [])
    data["topics_list"] = [{"id": t["id"], "name": t["name"]} for t in topics]

    # Cles de titre deja vues recemment (anti-doublon inter-sources)
    cutoff = now() - datetime.timedelta(hours=DEDUP_HOURS)
    recent_keys = set()
    for a in data["alerts"]:
        ts = parse_iso(a.get("found_at", ""))
        if ts and ts >= cutoff and a.get("tkey"):
            recent_keys.add(a["tkey"])

    found = []
    for topic in topics:
        rules = topic.get("rules", {})
        for q in topic.get("queries", []):
            try:
                for it in fetch_rss(q):
                    if not it["link"] or it["link"] in seen:
                        continue
                    seen.add(it["link"])
                    ok, pr, lbl, conf = classify(it["title"], rules)
                    if ok:
                        found.append((it, "press", pr, lbl, conf, matched_terms(it["title"], rules), topic))
                    else:
                        print("Ignore [%s] : %s" % (topic["id"], it["title"]))
            except Exception as e:
                print("Erreur RSS [%s] '%s' : %s" % (topic["id"], q, e))
        if legifrance is not None:
            try:
                for it in legifrance.fetch_legifrance(topic.get("legifrance_queries", [])):
                    if it["link"] and it["link"] not in seen:
                        seen.add(it["link"])
                        found.append((it, "official", "high", "Texte officiel \u00b7 JORF", "confirme", [], topic))
            except Exception as e:
                print("Legifrance [%s] indisponible : %s" % (topic["id"], e))

    page_changes = []
    for pg in pages:
        try:
            fp = page_fingerprint(pg["url"], pg.get("start_marker"), pg.get("end_marker"))
            if fp is None:
                continue
            prev = pstate.get(pg["id"])
            pstate[pg["id"]] = fp
            if prev and prev != fp and not first_run:
                topic = topic_by_id.get(pg.get("topic"), {"id": pg.get("topic", "?"), "name": pg.get("name", "Page")})
                it = {"title": "Modification detectee : " + pg["name"], "source": pg["name"],
                      "link": pg["url"], "pubDate": ""}
                page_changes.append((it, "page", "high", "Page modifiee", "confirme", [], topic))
        except Exception as e:
            print("Page '%s' indisponible : %s" % (pg.get("id"), e))

    data["last_check"] = now_iso()

    if first_run:
        save_json(STATE_FILE, sorted(seen))
        save_json(PAGES_STATE, pstate)
        save_json(DATA_FILE, data)
        print("Premiere execution : %d liens + %d pages, aucune alerte." % (len(seen), len(pages)))
        return

    order = [x for x in found if x[1] == "official"] + page_changes + \
            [x for x in found if x[1] == "press"]

    sent = 0
    today = now().date().isoformat()
    for it, kind, pr, lbl, conf, matched, topic in order:
        tkey = title_key(it["title"]) if kind == "press" else (kind + ":" + it["link"])
        is_dup = kind == "press" and tkey in recent_keys
        summary = ""
        if kind == "press":
            summary = extract_summary(it["link"])
        elif kind == "official":
            summary = summarize_official(it["link"])
        record = {
            "title": it["title"], "source": it["source"], "link": it["link"],
            "pubDate": it.get("pubDate", ""), "priority": pr, "label": lbl,
            "confidence": conf, "matched": matched, "tkey": tkey,
            "topic": topic["id"], "topic_name": topic["name"],
            "summary": summary, "found_at": now_iso(),
        }
        data["alerts"].insert(0, record)

        if is_dup:
            print("Doublon (ping supprime) : %s" % it["title"])
            continue
        recent_keys.add(tkey)
        src = (" \u00b7 " + it["source"]) if it["source"] else ""
        body = ("\n\n" + html.escape(summary)) if summary else ""
        msg = "%s <b>%s</b>%s\n<i>%s</i>\n\n%s%s\n<i>%s</i>" % (
            EMOJI[pr], lbl, src, html.escape(topic["name"]),
            html.escape(it["title"]), body, html.escape(it.get("pubDate", "")))
        send_telegram(msg)
        send_ntfy("%s — %s" % (lbl, topic["name"]), it["title"],
                  priority=("high" if pr == "high" else "default"),
                  tags=("rotating_light" if pr == "high" else "bell"))
        sent += 1
        if sent % 5 == 0:
            time.sleep(1)  # throttle Telegram
        print("Alerte [%s/%s/%s] %s : %s" % (topic["id"], pr, conf, it["source"], it["title"]))

    if sent:
        data["last_alert_at"] = now_iso()

    # ---------- Intensification ----------
    for topic in topics:
        tid = topic["id"]
        # comptage par jour sur 8 jours pour ce sujet
        counts = {}
        for a in data["alerts"]:
            if a.get("topic") != tid:
                continue
            ts = parse_iso(a.get("found_at", ""))
            if ts:
                counts[ts.date().isoformat()] = counts.get(ts.date().isoformat(), 0) + 1
        days = [(now().date() - datetime.timedelta(days=i)).isoformat() for i in range(1, 8)]
        avg7 = sum(counts.get(d, 0) for d in days) / 7.0
        tcount = counts.get(today, 0)
        already = any(s for s in data["spikes"] if s.get("topic") == tid and s.get("date") == today)
        if tcount >= max(3, 2 * avg7) and tcount >= 3 and not already:
            data["spikes"].append({"topic": tid, "topic_name": topic["name"],
                                   "date": today, "count": tcount, "at": now_iso()})
            send_telegram("\U0001F4C8 <b>Intensification</b> · %s\n%d alertes aujourd'hui (moy. 7j : %.1f). Publication possiblement imminente." % (
                html.escape(topic["name"]), tcount, avg7))
            send_ntfy("Intensification — " + topic["name"],
                      "%d alertes aujourd'hui (moy 7j %.1f)" % (tcount, avg7),
                      priority="high", tags="chart_with_upwards_trend")

    data["spikes"] = data["spikes"][-50:]

    # ---------- Battement de coeur ----------
    la = parse_iso(data.get("last_alert_at") or "")
    hb = parse_iso(data.get("last_heartbeat") or "")
    silent = (la is None) or ((now() - la).days >= HEARTBEAT_DAYS)
    hb_due = (hb is None) or ((now() - hb).days >= HEARTBEAT_DAYS)
    if not sent and silent and hb_due:
        data["last_heartbeat"] = now_iso()
        send_telegram("\U0001F7E2 Veille operationnelle. Aucune nouveaute depuis %d jours." % HEARTBEAT_DAYS)

    data["alerts"] = data["alerts"][:MAX_HISTORY]
    save_json(STATE_FILE, sorted(seen))
    save_json(PAGES_STATE, pstate)
    save_json(DATA_FILE, data)
    print("Termine : %d alertes envoyees, %d pages modifiees." % (sent, len(page_changes)))


if __name__ == "__main__":
    main()
