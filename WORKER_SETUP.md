# Sessions de veille — mise en place du Worker (gratuit)

Permet de **créer/supprimer un suivi par mots-clés depuis le dashboard**, sans
exposer de secret. Le mot-clé (2 à 3 mots requis) devient un sujet surveillé chaque
heure, avec alertes Telegram. Tout passe par un petit **Cloudflare Worker** qui
détient le token GitHub côté serveur. Plan gratuit largement suffisant
(100 000 requêtes/jour).

## Vue d'ensemble
```
Dashboard (public)  ──mot-clé + phrase secrète──►  Worker Cloudflare
                                                      │ (token GitHub, secret)
                                                      ├─ écrit sessions.json (API GitHub)
                                                      └─ relance monitor.yml
monitor.py lit sessions.json en plus de topics.json → veille + alertes
```

## 1. Créer un token GitHub (fine-grained)
1. GitHub → Settings → Developer settings → **Fine-grained tokens** → Generate new token.
2. **Repository access** : *Only select repositories* → `veille-apl`.
3. **Permissions** → Repository permissions :
   - **Contents** : Read and write
   - **Actions** : Read and write
4. Générer, **copier le token** (`github_pat_…`).

## 2. Créer le Worker
1. Compte gratuit sur **dash.cloudflare.com** → **Workers & Pages** → **Create** → **Create Worker**.
2. Nommez-le (ex. `veille-apl-sessions`), déployez le modèle par défaut.
3. **Edit code** : remplacez tout par le contenu de `worker.js`, puis **Deploy**.
4. Notez l'URL du Worker (ex. `https://veille-apl-sessions.VOTRE-SOUS-DOMAINE.workers.dev`).

## 3. Configurer les variables du Worker
Worker → **Settings → Variables and Secrets** :

| Nom | Type | Valeur |
|---|---|---|
| `GH_TOKEN` | Secret | le token de l'étape 1 |
| `SESSION_SECRET` | Secret | une phrase secrète à vous (celle saisie dans le dashboard) |
| `GH_REPO` | Variable | `MHT-RIAD/veille-apl` |
| `ALLOW_ORIGIN` | Variable | `https://mht-riad.github.io` |

Re-déployez si demandé.

## 4. Brancher le dashboard
Dans `docs/index.html`, renseignez l'URL du Worker :
```js
const SESSIONS_WORKER_URL="https://veille-apl-sessions.VOTRE-SOUS-DOMAINE.workers.dev";
```
Puis commit / push :
```bash
git add docs/index.html
git commit -m "Sessions : URL du Worker"
git pull --rebase
git push
```

## 5. Utilisation
Dashboard → **Sessions de veille** : tapez 2 à 3 mots + votre phrase secrète →
**Ajouter**. Sous ~1 minute (commit + run + reconstruction Pages), un nouvel onglet
apparaît et la veille suit ce sujet. **Supprimer** retire la session.

## Sécurité
- Le token GitHub vit **uniquement dans le Worker** (secret chiffré), jamais dans la page.
- L'URL du Worker est publique mais **verrouillée par `SESSION_SECRET`** : sans la
  bonne phrase, le Worker répond `401` et ne fait rien.
- Le token est **fine-grained**, limité au seul repo et à deux permissions.
- Pour révoquer : supprimez le token sur GitHub et/ou changez `SESSION_SECRET`.

## Dépannage
| Symptôme | Cause | Solution |
|---|---|---|
| « Phrase secrète incorrecte » | `SESSION_SECRET` ≠ saisie | Vérifier le secret du Worker. |
| « Écriture GitHub échouée » 403 | Permissions du token | Contents + Actions en Read/Write. |
| Rien n'apparaît après ajout | Délai Pages | Attendre ~1 min, cliquer Actualiser, `Ctrl+Shift+R`. |
| CORS error (console) | `ALLOW_ORIGIN` | Mettre l'origine exacte de Pages, ou `*` le temps d'un test. |
