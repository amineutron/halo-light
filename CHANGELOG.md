# Changelog

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versionnement [SemVer](https://semver.org/lang/fr/).

## [Non publié]

### Ajouté
- Première version : serveur MCP Philips Hue écrit à neuf sur l'API CLIP v2 (https, `httpx` asynchrone).
- Lecture : lumières, pièces, zones, scènes, état courant.
- Commandes de lumières et de groupes (allumer, éteindre, luminosité, couleur par nom, hexadécimal, RGB ou xy, température en Kelvin), par identifiant ou par nom.
- Résolution de noms insensible à la casse et aux accents : exacte d'abord, partielle seulement si unique, erreur listant les candidats sinon.
- Activation d'une scène par nom, appliquée à sa propre pièce (aucun groupe codé en dur).
- Identifiants hérités de l'API v1 (`/lights/12`) acceptés pour la compatibilité.
- Configuration : variables d'environnement prioritaires, fichier JSON créé en mode 0600.
- Commandes `hue-bridge-mcp pair` (appairage par bouton) et `hue-bridge-mcp discover`.
- Extension optionnelle `hue_beat` pilotant un script externe (`HUE_BEAT_PATH`).
- Erreurs remontées comme erreurs MCP (`isError`) ; annotations MCP sur tous les outils.
- Tests `pytest` contre un faux pont (`httpx.MockTransport`) et CI GitHub Actions (ruff + pytest, Python 3.10 à 3.13).
