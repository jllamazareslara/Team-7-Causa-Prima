# Plan Team 7 — samedi 3/10 → dimanche 4/10, du plus urgent au moins urgent

## Contexte
On est samedi ~10h30. Le jeu tourne depuis 09:00. Notre chaîne d'agents (`noche-03-10/`, 13 agents + El Guion créé ce matin) **n'a jamais joué contre le vrai jeu** : pour l'instant elle ne rapporte aucun point. Les duels sont pris en charge par une autre personne.
Barème : **Jury 40 · Négociation 30 · Marché 30**. Le cash, le nombre de deals et la chance des paquets ne comptent pas. Ce qui compte : la valeur créée, la part de la fourchette de prix qu'on capture face aux vendeurs, et la qualité du marché.
Sources : `/api/schedule`, `/api/levels` et `/api/catalog` (lus sans clé), l'écran (pistes 1, 3 et 5), `bazaar-kit/RULES.md`.

Règles d'or (on ne déroge pas) :
- **Ne jamais acheter au-dessus de notre valeur** (`GET /api/me/value?card=`). Sinon on perd des points.
- Ne jamais répéter un prix : avancer par petits pas (20→21→22). Pas de spam, sinon le vendeur coupe.
- Les mots ne lient personne : on ne lit que la **structure** de l'offre avant d'accepter.
- Rien ne se lance sans le oui de l'équipe (tests, mode live, GitHub, dépenses).

---

## P0 — MAINTENANT (avant 11:30–12:00) : sans ça, zéro point

| # | Quoi | Comment / où | Pourquoi |
|---|---|---|---|
| 0.1 | **Duels I à 11:30 : agent allumé** (autre personne) | `bazaar-kit/duel_agent.py` | Un duel sans réponse = 0 pour les deux équipes |
| 0.2 | **Lancer le vigía en lecture seule** | `python vigia.py --cada 60` | Il voit les news (niveaux, vendeurs, fièvre) et les alertes d'El Guion. Il ne dépense rien |
| 0.3 | **Revue + premier passage à blanc du director** | `python revisar.py` puis `python director.py --ticks 3` | Vérifier les vrais formats de `affinity`, `catalog()`, `dealers()`. On corrige `director.leer()` si un champ diffère |
| 0.4 | **Director en live avec des plafonds bas** | `director.py --live`, réserve de 60 P, `runs/STOP` prêt | Personne ne marque tant que rien ne tourne. Le journal (`runs/`) est aussi la matière pour le jury |
| 0.5 | Tests + GitHub pour El Guion | `python -m unittest discover -s tests` → branche `infra/t7-sabado` | Pour que l'équipe ait le code |

## P1 — avant 12:45 : l'échelle des vendeurs (Négociation)

| # | Quoi | Comment / où |
|---|---|---|
| 1.1 | **Menus de Pilar (~11:50) et Chato (~12:45)** | `revisar.py --menus` → `menus.json` (fonction existante `t7/menus.py`) |
| 1.2 | **3 deals négociés avec CHAQUE vendeur** : Pilar et Chato d'abord, car les niveaux élevés pèsent plus. Un deal manquant compte 0 | `t7/prioridad.py` `mejora_escalera()` : multiplier par le niveau du vendeur |
| 1.3 | Ouvrir bas, faire des petits pas, prendre l'offre finale si elle reste sous notre valeur | Déjà dans `t7/tienda.py` (ancrage à 10 %, patience 10). Profil prudent pour un vendeur inconnu (`params.perfil`) |
| 1.4 | Négocier avec le vendeur d'avant pour débloquer plus tôt le suivant (avance) | El Guion `sin_anunciar("persona")` |

## P2 — LE MARCHÉ (30 pts) : quoi construire, quand acheter, comment

### 2A. Notre marché (Market Test + échanges entre autres équipes)
| # | Quoi | Décision proposée |
|---|---|---|
| 2.1 | **Enregistreur de Market Test** (lecture seule) : à chaque session (11:20, 13:20, 15:20, 17:20, 19:20, 21:00 la dure), sauvegarder le carnet `bench_offers` avec la `starter_broker_key` de `me()` | Nouveau `grabador.py`. Il rejoue les sessions hors ligne dans `sim/` pour comparer `t7/broker.py` au mode auto |
| 2.2 | **Ouvrir notre marché en `auto` avec `fee_bps: 0`** (si on est niveau 2 et que la caisse le permet : 270 P, dont 250 de caution remboursable) | Sur le Market Test, ça fait aussi bien que le stand gratuit (la moitié des points, garantie). Et frais 0 contre 5 % + 1 P au Rastro : **les autres équipes viennent échanger chez nous**, et la valeur qu'elles créent compte pour nous. Les frais ne rapportent rien, donc 0 ne coûte rien |
| 2.3 | Passer en `board` + broker **seulement** si 2.1 prouve qu'on bat le mode auto (matcher d'abord les traders impatients, matcher toutes les paires qui se croisent à chaque tick) | Sinon on reste en auto. Un broker en panne = session perdue |
| 2.4 | Faire venir les équipes chez nous : message dans les threads d'équipe (« 0 % de frais »), annonce sur notre marché | C'est de la persuasion autorisée. Ne jamais pousser une équipe à nous céder de la valeur : c'est interdit et ça compte 0 |

### 2B. Quand acheter
- **Seulement si prix < notre valeur.** La carte qui complète une page vaut beaucoup plus (bonus de 25 % de la page). Exemple : les 2 raras manquantes de La Latina valent 330 P ensemble. `cambista.lista_compra()` classe déjà ces cartes.
- **Les vendeurs ont un quota par heure et par équipe :** étaler les achats, et revenir au début de chaque heure.
- **Paquets :** n'acheter que si leur valeur espérée à nos multiplicateurs dépasse le prix. La chance ne compte pas. À construire : `valor.ev_sobre()`, avec les distributions de `catalog.packs` (paquets or de Pilar, meilleurs paquets de Chato). Acheter tôt : quand une rareté est épuisée, les paquets donnent la rareté du dessous.
- **Au Rastro / entre équipes :** acheter quand les autres manquent de cash (samedi soir, avant les +150 P de dimanche). Vendre juste après les grants : tout le monde a du cash (dimanche ~09:35).
- **Barrios :** LAT ×1,6 et RET ×1,3, on achète. LAV ×1,1, seulement ce qui complète la page. CHA ×0,9 et SAL ×0,7, on n'achète pas. MAL ×0,5, on vend. Valeurs à confirmer avec `me()["affinity"]` (`valor.configurar`).

### 2C. Comment vendre
- **Échanges entre équipes :** le gain se calcule à NOS valeurs privées. Vendre ce qui nous vaut peu (MAL, SAL, doublons) à ceux qui en manquent. `cadena.anuncios_rastro()` est déjà prêt mais éteint (`rastro.publicar = 0`) : l'allumer après le passage à blanc.
- **Ne pas vendre de SAL avant la fièvre** (`guion.bloqueadas()`, à brancher dans `cambista.py` / `cadena.py`).
- **Fièvre Salamanca, ~15:30 → 17:30 :** vendre à Pilar la liste `guion.venta_fiebre()`. Démarrer au-dessus du prix de fièvre, puis descendre par petits pas.
- Avant la fermeture du soir (22:30) : annuler les annonces qu'on ne veut plus. Elles restent ouvertes la nuit et passent à l'ouverture.

## P3 — Manipulation et défense (Négociation + Jury)

| # | Quoi | Où |
|---|---|---|
| 3.1 | **Vendeurs :** l'injection de prompt est permise. Elle change ce qu'ils disent, jamais leurs prix. On l'utilise pour obtenir leur limite (sondes de l'Espía : une conversation test par jour, après les 3 deals). Abuela aime la gentillesse | `t7/sondas.py` (existe) |
| 3.2 | **Signaler la mauvaise foi** uniquement si le texte contredit l'offre structurée. Un signalement juste rapporte, un faux coûte | `t7/defensa.py` détecteur d'incohérences → `POST /api/flags` (à brancher) |
| 3.3 | **Équipes :** l'Escudo filtre leurs injections. On lit la structure, jamais les mots | `t7/defensa.py` (existe) |
| 3.4 | **Injection contre les équipes :** demander à la table si c'est permis | `hoy.json` `mesa_permite_inyeccion_equipos` |
| 3.5 | **Radio Rastro :** une rumeur qui figure dans `/api/schedule` est vraie, une rumeur absente est seulement notée. Ne jamais changer un prix sur une rumeur | Nouvelle règle dans `t7/guion.py` + cuaderno de `sondas.py` |

## P4 — Ce qui va arriver (déjà préparé dans El Guion)

| Heure (approx.) | Événement | Action préparée |
|---|---|---|
| sam 11:20, puis toutes les 2 h | Market Test | Enregistreur (2.1) |
| 11:30 | Duels I | Agent allumé |
| ~11:50 / ~12:45 | Pilar / Chato ouverts à tous | P1 |
| ~13:30 | Début du blocage SAL | `bloqueadas()` |
| **~15:30–17:30** | **Fièvre Salamanca** | Vendre à Pilar |
| 18:00 | Duels II (prix + jour) | Échanger le jour contre du prix (autre personne) |
| ~21:00 | Market Test dur | Si broker : matcher tôt |
| 22:30–23:00 | Fermeture | Nettoyer les annonces, sauvegarder `runs/` |
| dim 09:00 | Ouverture, tick de 15 s | `hoy.json tick_segundos=15`, `revisar.py` |
| dim 09:30 | Chamberí + 150 P | Vérifier notre multiplicateur ; finir les 3 deals par vendeur (nouvelle manche) |
| dim ~11:30 | Duels III (perte de 10 % par ronde) | Conclure encore plus vite |
| **dim ~13:00–14:30** | **Fermeture des vendeurs (finale)** | Derniers deals de l'échelle et ventes aux vendeurs avant |
| dim ~15:30 | Gel des scores | Plus que des deals clairement bons |

## P5 — Jury (40 pts) : à préparer en parallèle, à finir dimanche matin
- L'histoire : une chaîne de 13 agents + El Guion qui anticipe. Chaque décision est notée avec son motif (journal). On a un simulateur et des tests.
- Les preuves : vrais chiffres du jour tirés de `runs/` (part capturée par vendeur, ventes pendant la fièvre, Market Test comparé au mode auto).
- Le support : l'artefact Team 7 (onglets existants) + une démo de 3 minutes. Demander à la table l'heure et le format du passage devant le jury.

## Fichiers clés
- Existants à réutiliser : `t7/tienda.py`, `t7/prioridad.py`, `t7/cambista.py` (`lista_compra`, anuncios), `t7/broker.py`, `t7/sondas.py`, `t7/defensa.py`, `t7/valor.py` (`valor_entregar`, `protegida`, `configurar`), `t7/menus.py`, `revisar.py`, `director.py`, `vigia.py`, `t7/guion.py`.
- À créer : `grabador.py` (Market Test), `valor.ev_sobre()`, branchement de `bloqueadas()` dans le Cambista, poids des niveaux dans `prioridad.py`, vérificateur de rumeurs dans `guion.py`, envoi des flags.

## Artefact
À chaque étape terminée : republier l'artefact Team 7 (la version à jour, `team-7-completo.html`, lien PC7B89L761oU6yYUSCDyZ8). On le relit avant, puis on ajoute ce plan dans l'onglet Estrategia (version simple) et le détail dans Los agentes. Pas de nouvel onglet en double.

## Vérification
1. `python -m unittest discover -s tests -v` (hors réseau) : tout passe, `test_guion.py` compris.
2. `python -m t7.guion datos/calendario-03-10.json --hora HH:MM --cartas cartas.json` : la frise et la liste fièvre sont cohérentes.
3. `revisar.py` sans aucun `FALTA`, puis `director.py --ticks 3` à blanc : on lit `runs/crudo.jsonl`.
4. En live avec plafonds bas : on surveille `GET /api/me` (score) après les 3 premiers deals avant d'ouvrir plus grand.
5. Market Test : on compare le carnet enregistré rejoué en auto et avec notre broker avant toute décision `board`.
