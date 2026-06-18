# Architecture & fonctionnement

Documentation technique de référence de la veille. Pour installer, voir
[INSTALL.md](INSTALL.md) ; pour maintenir, voir [MAINTENANCE.md](MAINTENANCE.md).

## Vue d'ensemble

Le système surveille la publication du décret d'application de la loi de finances
2026 (art. 179, modifiant l'art. L.822-2 CCH) supprimant les APL des étudiants
étrangers extra-communautaires non boursiers, ainsi que des sujets liés. Il ne
nécessite **aucun serveur** : tout tourne sur GitHub Actions, et le tableau de bord
est servi en statique par GitHub Pages.

```
            ┌──────────────── GitHub Actions (cron horaire) ────────────────┐
            │                                                                │
  Google News RSS ─┐                                                         │
  API Légifrance ──┼──►  monitor.py  ──►  classe / dédoublonne / score  ──┐  │
  Pages officielles┘         │                                            │  │
            │                ├──► Telegram + ntfy.sh (push)               │  │
            │                ├──► docs/data.json (historique)  ◄──────────┘  │
            │                └──► make_og.py ──► docs/og.png (statut)        │
            │                                                                │
            │   digest.py (cron quotidien) ──► docs/digest.json (brief IA)   │
            └────────────────────────────────────────────────────────────────┘
                                     │
                       GitHub Pages (/docs) sert le dashboard
                       index.html lit data.json / digest.json
```

## Rôle de chaque fichier

| Fichier | Rôle |
|---|---|
| `monitor.py` | Cœur de la veille : collecte, tri, confiance, dédoublonnage, intensification, push, battement de cœur. |
| `legifrance.py` | Source officielle JORF via l'API PISTE (optionnel). |
| `digest.py` | Brief quotidien synthétisé par IA (optionnel). |
| `make_og.py` | Génère l'image de statut partageable et les icônes PWA. |
| `topics.json` | Sujets suivis : requêtes presse + règles de tri par sujet. |
| `pages.json` | Pages officielles surveillées pour détection de changement. |
| `test_monitor.py` | Tests de non-régression (sans réseau). |
| `docs/index.html` | Tableau de bord (lit `data.json` / `digest.json`). |
| `docs/sw.js`, `manifest.webmanifest` | Service worker + manifeste (PWA). |
| `docs/data.json` | Historique des alertes + métadonnées (généré). |
| `seen.json`, `pages_state.json` | État interne (liens vus, empreintes de pages). |
| `.github/workflows/` | `monitor.yml` (horaire), `digest.yml` (quotidien), `ci.yml` (tests). |

## Modèle de tri et de confiance

Pour chaque titre, et pour chaque sujet (`topics.json`), `classify()` applique :

1. **Exclusion** : si le titre contient un terme de `exclusions` → ignoré.
2. **Pertinence** : il faut **au moins un terme de `groupe_a` ET un de `groupe_b`**
   (ex. un terme « logement/APL » **et** un terme « étudiant/étranger »). Sinon ignoré.
3. **Niveau de confiance**, dans cet ordre :
   - **report** — termes de report/négation (`pas encore`, `suspendu`, `reporté`…)
     combinés à un signal : priorité *related*, le verdict ne bascule pas en « publié ».
   - **confirmé** — termes de publication avérée (`paru au Journal officiel`,
     `promulgué`, `entré en vigueur`…) : priorité *high*.
   - **à confirmer (rumeur)** — un signal + un terme conditionnel (`devrait`,
     `attendu`…) : priorité *related*.
   - **probable** — un signal (`décret`, `arrêté`…) sans conditionnel : *high*.
   - **lié** — pertinent mais sans signal : *related*.

La correspondance se fait **par début de mot** (sans accents), ce qui gère les
pluriels (« étranger » → « étrangers ») sans matcher au milieu d'un autre mot
(« taxe » ne déclenche pas sur « syntaxe »).

## Dédoublonnage inter-sources

Chaque alerte reçoit une `tkey` : l'ensemble trié de ses mots significatifs, avec
canonicalisation des synonymes de publication (`paru`/`promulgué`/`parution` →
`publié`). Deux dépêches de la même information — même réordonnées ou reformulées —
partagent la même `tkey`. Conséquence :
- côté `monitor.py` : la 2ᵉ occurrence (sous 48 h) est **enregistrée** mais son
  **ping est supprimé** ;
- côté dashboard : les alertes de même `tkey` sont regroupées en une carte « + N sources ».

## Intensification & battement de cœur

- **Intensification** : pour chaque sujet, si le nombre d'alertes du jour dépasse
  `max(3, 2 × moyenne des 7 jours précédents)`, une alerte spéciale est émise (une
  fois par jour) et une bannière s'affiche. Une montée de volume précède souvent la
  publication.
- **Battement de cœur** : s'il ne s'est rien passé depuis `HEARTBEAT_DAYS` (7 j), un
  message « veille opérationnelle » est envoyé pour distinguer *silence = pas de news*
  de *silence = panne*. (Les pannes de workflow déclenchent une alerte séparée.)

## Schéma de `docs/data.json`

```json
{
  "last_check": "2026-06-18T09:00:00Z",
  "last_alert_at": "…", "last_heartbeat": "…",
  "topics_list": [{"id": "decret-apl", "name": "…"}],
  "spikes": [{"topic": "…", "topic_name": "…", "date": "2026-06-18", "count": 5}],
  "alerts": [{
    "title": "…", "source": "Le Monde", "link": "https://…", "pubDate": "…",
    "priority": "high|related", "label": "…",
    "confidence": "confirme|probable|rumeur|report|lie",
    "matched": ["apl", "decret"], "tkey": "apl decret …",
    "topic": "decret-apl", "topic_name": "…",
    "summary": "…", "found_at": "2026-06-18T09:00:00Z"
  }]
}
```

## Tableau de bord

`index.html` est autonome (aucune dépendance externe hormis les polices Google).
Il lit `data.json` (réseau d'abord, cache en secours via le service worker) et, s'il
existe, `digest.json`. Fonctions : verdict global tenant compte de la confiance,
bande de stats, frise 14 jours, onglets par sujet, recherche + filtres, regroupement
des doublons, outil « Suis-je concerné ? » (100 % local), et **triage** (lu / important
/ archivé) stocké dans le `localStorage` du navigateur. Installable en PWA, avec
notifications locales quand un nouveau signal fort apparaît.

## Tests & CI

`test_monitor.py` couvre le classement (tous les niveaux de confiance, négation,
exclusion), la correspondance par mots entiers, le dédoublonnage (réordonnancement
et synonymes) et l'empreinte de page. La CI (`ci.yml`) compile tout et lance les
tests à chaque push : une modification qui casse une règle est signalée aussitôt.
