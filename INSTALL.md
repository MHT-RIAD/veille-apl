# Installation

Mise en ligne en ~15 minutes, sans serveur ni carte bancaire. Le minimum requis :
un compte GitHub et l'application Telegram.

## Prérequis
- Un compte **GitHub** (un repo **public** suffit et donne des minutes Actions illimitées).
- L'application **Telegram**.
- *(Optionnel)* l'app **ntfy**, une clé **Anthropic**, des identifiants **PISTE**.

## Ubuntu — voie rapide (recommandée)

Si vous êtes sur Ubuntu et que git/GitHub vous est inconnu, c'est le chemin le plus
simple : on installe l'outil officiel **GitHub CLI** (`gh`) et on lance un script qui
fait tout (création du repo, push, secrets, lancement, Pages).

```bash
# 1. Installer git et GitHub CLI
sudo apt update
sudo apt install -y git gh

# 2. Se connecter à GitHub (ouvre le navigateur, suivez : GitHub.com → HTTPS → login)
gh auth login

# 3. Récupérer le projet (adaptez le chemin du .zip)
cd ~/Téléchargements
unzip veille-apl.zip
cd veille-apl

# 4. Lancer le déploiement guidé
./setup.sh
```

Le script vous demandera votre `TELEGRAM_TOKEN` et `TELEGRAM_CHAT_ID` (étape 1
ci-dessous pour les obtenir) puis créera le repo, configurera les secrets, lancera la
veille et activera Pages. À la fin il affiche l'URL de votre tableau de bord.

> Pas à l'aise avec le terminal ? Suivez plutôt les étapes 1 à 6 ci-dessous, qui se
> font entièrement via le site github.com.

---

## 1. Créer le bot Telegram
1. Sur Telegram, ouvrir **@BotFather**, envoyer `/newbot`, suivre les étapes.
2. Noter le **token** fourni.
3. Envoyer un message quelconque à votre nouveau bot.
4. Ouvrir dans un navigateur `https://api.telegram.org/bot<TOKEN>/getUpdates` et
   relever la valeur `chat.id` : c'est votre **chat ID**.

## 2. Déposer le projet sur GitHub
1. Créer un repo **public** (ex. `veille-apl`).
2. Décompresser l'archive et pousser **tous les fichiers à la racine** du repo
   (le dossier `docs/`, les `.py`, `topics.json`, `pages.json`, `.github/`, etc.).

## 3. Configurer les secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret** :

| Secret | Obligatoire | Rôle |
|---|---|---|
| `TELEGRAM_TOKEN` | oui | Token du bot. |
| `TELEGRAM_CHAT_ID` | oui | Votre chat ID. |
| `NTFY_TOPIC` | non | Nom de canal ntfy.sh (push téléphone). |
| `ANTHROPIC_API_KEY` | non | Brief quotidien + résumé du texte officiel. |
| `PISTE_CLIENT_ID` / `PISTE_CLIENT_SECRET` | non | Source officielle JORF (Légifrance). |

## 4. Premier lancement
1. Onglet **Actions** → activer les workflows si demandé.
2. Workflow **« Veille decret APL »** → **Run workflow**.
3. Ce premier passage **enregistre l'existant sans envoyer d'alerte** (normal).
   Ensuite, il s'exécute tout seul chaque heure et n'alerte que sur du nouveau.

## 5. Publier le tableau de bord
1. **Settings → Pages → Build and deployment → Source : Deploy from a branch**.
2. Branche **`main`**, dossier **`/docs`**, enregistrer.
3. L'URL `https://<pseudo>.github.io/<repo>/` affiche le dashboard (mise à jour à
   chaque passage de la veille). Sur mobile, « Ajouter à l'écran d'accueil » l'installe en PWA.

## 6. Vérifier que tout fonctionne
- Onglet **Actions** : le run « Veille » est vert, et le run **CI** confirme que les
  17 tests passent.
- Le dashboard se charge et affiche « Aucune publication détectée » (état normal au départ).
- *(Optionnel)* Forcer une alerte de test : ajouter temporairement un mot très courant
  (ex. `france`) dans `groupe_b` d'un sujet, relancer, vérifier la réception Telegram,
  puis retirer le mot.

## Options
### Push téléphone via ntfy.sh (gratuit)
Choisir un nom de canal **difficile à deviner** (ex. `veille-apl-x7f3q2`), le mettre
dans le secret `NTFY_TOPIC`, installer l'app **ntfy** et s'abonner au même canal.
Aucune inscription.

### Brief quotidien + résumé IA
Créer une clé sur la **Console Anthropic** (facturation séparée de Claude Pro ; coût
de quelques centimes/mois ici) et la mettre dans `ANTHROPIC_API_KEY`.

### Source officielle JORF (Légifrance)
1. Compte gratuit sur `https://piste.gouv.fr/registration`.
2. Créer une application → page de consentement → cocher l'API **Légifrance**.
3. Mettre Client ID / Secret dans `PISTE_CLIENT_ID` / `PISTE_CLIENT_SECRET`.
   *(Pièce non testée en conditions réelles : voir la note dans MAINTENANCE.md.)*
