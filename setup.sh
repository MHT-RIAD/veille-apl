#!/usr/bin/env bash
# Déploiement guidé de la veille sur GitHub (Ubuntu/Linux/macOS).
# Prérequis : git + gh (GitHub CLI) installés, et "gh auth login" déjà fait.
# Usage : ./setup.sh
set -euo pipefail

say(){ printf "\n\033[1;36m%s\033[0m\n" "$1"; }
ask(){ local p="$1" d="${2:-}"; local r; read -rp "$p${d:+ [$d]}: " r; echo "${r:-$d}"; }

say "Vérification des outils…"
command -v git >/dev/null || { echo "git manquant : sudo apt install -y git"; exit 1; }
command -v gh  >/dev/null || { echo "gh manquant : voir INSTALL.md (section Ubuntu)"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Pas connecté : lance d'abord  gh auth login"; exit 1; }

# Identité git si absente
git config --global user.name  >/dev/null 2>&1 || git config --global user.name  "$(ask 'Votre nom (pour les commits)')"
git config --global user.email >/dev/null 2>&1 || git config --global user.email "$(ask 'Votre email GitHub')"

REPO=$(ask "Nom du repo à créer" "veille-apl")

say "Initialisation du dépôt local…"
git init -q
git add .
git commit -qm "Veille décret APL — version initiale" || true
git branch -M main

say "Création du repo GitHub (public) et push…"
gh repo create "$REPO" --public --source=. --remote=origin --push

SLUG=$(gh repo view --json nameWithOwner -q .nameWithOwner)
OWNER=${SLUG%%/*}

say "Configuration des secrets (laisser vide pour ignorer un secret optionnel)…"
set_secret(){ # nom  invite  [silencieux]
  local name="$1" prompt="$2" silent="${3:-}" val
  if [ "$silent" = "s" ]; then read -rsp "$prompt: " val; echo; else read -rp "$prompt: " val; fi
  [ -n "$val" ] && printf '%s' "$val" | gh secret set "$name" && echo "  ✓ $name défini"
}
set_secret TELEGRAM_TOKEN    "TELEGRAM_TOKEN (obligatoire)" s
set_secret TELEGRAM_CHAT_ID  "TELEGRAM_CHAT_ID (obligatoire)"
set_secret NTFY_TOPIC        "NTFY_TOPIC (optionnel)"
set_secret ANTHROPIC_API_KEY "ANTHROPIC_API_KEY (optionnel)" s
set_secret PISTE_CLIENT_ID   "PISTE_CLIENT_ID (optionnel)"
set_secret PISTE_CLIENT_SECRET "PISTE_CLIENT_SECRET (optionnel)" s

say "Premier lancement de la veille (seeding, sans alerte)…"
gh workflow run monitor.yml || echo "  (lance-le à la main : onglet Actions → Run workflow)"

say "Activation de GitHub Pages (branche main, dossier /docs)…"
if gh api -X POST "repos/$SLUG/pages" -f "source[branch]=main" -f "source[path]=/docs" >/dev/null 2>&1; then
  echo "  ✓ Pages activé"
else
  echo "  ⚠ Activation auto échouée (droits ?). À faire à la main :"
  echo "    Settings → Pages → Deploy from a branch → main → /docs"
fi

say "Terminé !"
echo "Repo      : https://github.com/$SLUG"
echo "Dashboard : https://$OWNER.github.io/$REPO/  (en ligne après ~1 min)"
echo "Vérifie l'onglet Actions : le run « Veille » et la CI doivent être verts."
