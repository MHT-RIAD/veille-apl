# Maintenance

Comment faire vivre la veille au quotidien : la calibrer, l'ajuster, la dépanner,
et savoir quoi faire quand le décret paraît.

## La boucle de calibration (les premiers jours)
Laisser tourner 24–48 h, puis regarder le dashboard et Telegram. La règle :
- **Trop d'alertes inutiles sur un sujet** → ajouter le terme gênant dans
  `exclusions` du sujet, dans `topics.json`.
- **Un article pertinent manque** → ajouter un mot-clé dans `groupe_a` / `groupe_b`,
  ou une requête dans `queries`.
- **Un faux « confirmé »** → ajuster `CONFIRM_TERMS` / `POSTPONE_TERMS` dans
  `monitor.py`, **et ajouter un test** correspondant.
- **Faux positif sur une page surveillée** → renseigner `start_marker` / `end_marker`
  dans `pages.json` pour ne suivre qu'une région.

Après chaque changement : `python -m unittest` en local (ou laisser la CI le faire).

## Tâches courantes

### Ajouter / modifier un sujet
Éditer `topics.json`. Un sujet = `id`, `name`, `queries` (presse), `rules`
(`groupe_a` + `groupe_b` requis, `signaux`, `exclusions`) et `legifrance_queries`.
**Important** : après ajout d'un sujet, le nouvel onglet apparaîtra automatiquement
sur le dashboard dès le prochain passage de la veille (le `topics_list` de
`data.json` est régénéré à chaque run).

### Ajouter une page officielle à surveiller
Ajouter une entrée dans `pages.json` : `id`, `name`, `url`, `topic`, et
éventuellement `start_marker` / `end_marker` (chaînes HTML bornant la zone utile).

### Régler la sensibilité
Constantes en haut de `monitor.py` : `DEDUP_HOURS` (fenêtre anti-doublon),
`HEARTBEAT_DAYS` (battement de cœur), `MAX_HISTORY` (taille de l'historique).

### Lancer les tests
`python -m unittest -v` (aucun réseau requis). À faire avant tout commit qui touche
le tri ou le dédoublonnage.

### Mettre à jour
Modifier les fichiers, committer, pousser. Les workflows planifiés s'exécutent sur la
branche par défaut ; la CI valide le push.

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| Aucune alerte ne part | 1er run (seeding) | Normal : seul le 2ᵉ passage alerte. |
| « ⚠️ workflow a échoué » sur Telegram | Erreur d'exécution | Voir les logs dans l'onglet Actions. |
| Pas de message Telegram | Secrets manquants/erronés | Vérifier `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID`. |
| Le dashboard ne se met pas à jour | Pages mal configuré | Settings → Pages → `main` /docs ; vider le cache. |
| Trop de pings identiques | Synonyme non couvert | Étendre `_SYNO` dans `monitor.py`. |
| Page surveillée alerte sans cesse | Contenu dynamique | Ajouter `start_marker`/`end_marker` dans `pages.json`. |
| Le JORF ne remonte rien | Payload API à ajuster | Voir la note Légifrance ci-dessous. |

## Coûts
- Veille + Telegram + dashboard : **gratuit** (Actions illimité sur repo public, Pages, ntfy).
- Brief + résumé IA : **clé Anthropic**, facturée à l'usage (modèle Haiku, quelques
  centimes/mois ici). Non couvert par un abonnement Claude Pro.

## Sécurité
- Garder le repo **public sans jamais committer de secret** : tokens et clés vivent
  **uniquement** dans les *Secrets* GitHub, jamais dans les fichiers.
- Pour **renouveler** un secret compromis : régénérer le token côté service
  (BotFather / Console Anthropic / PISTE) puis mettre à jour le secret GitHub.
- `NTFY_TOPIC` doit rester difficile à deviner : c'est lui qui protège le canal.

## Note Légifrance (PISTE)
C'est la seule pièce non testée en conditions réelles (nécessite vos identifiants).
Si aucun texte officiel ne remonte une fois branchée, ajuster dans `legifrance.py` :
`typeRecherche` (`TOUS_LES_MOTS_DANS_UN_CHAMP`, `UN_DES_MOTS`, `EXPRESSION_EXACTE`),
le `fond` (`JORF`), ou les `LEGIFRANCE_QUERIES`, en se référant au Swagger PISTE
(`https://piste.gouv.fr/api-dila-legifrance/`).

## Cycle de vie : quand le décret paraît
1. Vous recevez une alerte **confirmé** (et probablement une **intensification**).
2. **Vérifier la source officielle** : Légifrance / Journal officiel (lien en pied du dashboard).
3. Le décret précisera les modalités (boursiers, durée de résidence, dossiers en cours).
   Mettre à jour l'outil « Suis-je concerné ? » dans `index.html` si les critères changent.
4. **Après le 1er juillet 2026**, deux options : archiver le repo (désactiver les
   workflows planifiés), ou **repositionner la veille** sur un autre sujet en
   réécrivant `topics.json` (l'infrastructure est générique).
