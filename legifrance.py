#!/usr/bin/env python3
"""Source officielle : interroge le fond JORF de l'API Legifrance (via PISTE).

Optionnel. Actif seulement si PISTE_CLIENT_ID et PISTE_CLIENT_SECRET sont definis.
En cas d'absence d'identifiants ou d'erreur, renvoie [] sans planter.

Mise en place :
  1. Compte gratuit sur https://piste.gouv.fr/registration
  2. Cree une application, page de consentement -> coche l'API "Legifrance"
  3. Recupere Client ID + Secret (OAuth) -> secrets PISTE_CLIENT_ID / PISTE_CLIENT_SECRET
  4. (option) PISTE_SANDBOX=1 pour l'environnement de test.
Doc / Swagger : https://piste.gouv.fr/api-dila-legifrance/
"""
import os
import json
import urllib.parse
import urllib.request


def _endpoints():
    if os.environ.get("PISTE_SANDBOX") == "1":
        return ("https://sandbox-oauth.piste.gouv.fr/api/oauth/token",
                "https://sandbox-api.piste.gouv.fr/dila/legifrance/lf-engine-app")
    return ("https://oauth.piste.gouv.fr/api/oauth/token",
            "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app")


def _get_token(token_url, cid, secret):
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials", "client_id": cid,
        "client_secret": secret, "scope": "openid"}).encode()
    req = urllib.request.Request(token_url, data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["access_token"]


def _search(api_url, token, query):
    payload = {
        "recherche": {
            "champs": [{
                "typeChamp": "ALL",
                "criteres": [{"typeRecherche": "TOUS_LES_MOTS_DANS_UN_CHAMP",
                              "valeur": query, "operateur": "ET"}],
                "operateur": "ET"}],
            "pageNumber": 1, "pageSize": 10, "operateur": "ET",
            "sort": "SIGNATURE_DATE_DESC", "typePagination": "DEFAUT"},
        "fond": "JORF"}
    req = urllib.request.Request(
        api_url + "/search", data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read())


def _parse_results(raw):
    items = []
    for res in (raw.get("results") or []):
        title, tid, date = None, None, None
        titles = res.get("titles") or res.get("title")
        if isinstance(titles, list) and titles:
            title = titles[0].get("title") or titles[0].get("titre")
            tid = titles[0].get("id") or titles[0].get("cid")
        elif isinstance(titles, str):
            title = titles
        title = title or res.get("title") or res.get("titre")
        tid = tid or res.get("id") or res.get("cid")
        date = res.get("datePublication") or res.get("date") or res.get("dateSignature")
        if not title:
            continue
        link = ("https://www.legifrance.gouv.fr/jorf/id/" + tid) if tid else "https://www.legifrance.gouv.fr/"
        items.append({"title": title.strip(), "source": "Legifrance (JORF)",
                      "link": link, "pubDate": str(date) if date else ""})
    return items


def fetch_legifrance(queries):
    """queries : liste de chaines. Renvoie une liste d'items officiels. Jamais d'exception."""
    cid = os.environ.get("PISTE_CLIENT_ID")
    secret = os.environ.get("PISTE_CLIENT_SECRET")
    if not cid or not secret or not queries:
        return []
    token_url, api_url = _endpoints()
    try:
        token = _get_token(token_url, cid, secret)
    except Exception as e:
        print("Legifrance : token indisponible :", e)
        return []
    out, seen = [], set()
    for q in queries:
        try:
            for it in _parse_results(_search(api_url, token, q)):
                if it["link"] not in seen:
                    seen.add(it["link"])
                    out.append(it)
        except Exception as e:
            print("Legifrance : erreur '%s' : %s" % (q, e))
    return out
