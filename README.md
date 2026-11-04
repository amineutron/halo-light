# halo-light

[![ci](https://github.com/amineutron/halo-light/actions/workflows/ci.yml/badge.svg)](https://github.com/amineutron/halo-light/actions/workflows/ci.yml)
[![licence MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

Serveur [MCP](https://modelcontextprotocol.io) pour les lumières Philips Hue, écrit à neuf sur l'API locale **CLIP v2** du pont (https, en-tête `hue-application-key`). Un assistant (Claude, Lyra, etc.) peut lire l'état des lumières, des pièces et des scènes, puis les commander **par identifiant ou par nom**.

## Fonctionnalités

- Lumières, pièces, zones et scènes de l'API v2 (`light`, `grouped_light`, `room`, `zone`, `scene`).
- Adressage par identifiant (UUID v2, ou ancien identifiant numérique v1 comme `12`) **ou par nom**.
- Noms insensibles à la casse et aux accents : correspondance exacte d'abord, partielle seulement si elle est unique, sinon une erreur liste les candidats.
- Une scène est activée dans **sa propre pièce** : aucun groupe n'est codé en dur.
- Couleur par nom (`rouge`, `bleu`, `orange`...), hexadécimal (`#ff8800`), RGB ou xy ; température de blanc en Kelvin.
- Erreurs remontées comme erreurs MCP (`isError`) avec un message exploitable par le modèle.
- Annotations MCP sur chaque outil (`readOnlyHint`, `destructiveHint`, `idempotentHint`).
- Extension optionnelle `hue_beat` (synchronisation lumière / musique) via un script externe.

## Installation

Prérequis : Python 3.10 ou plus récent et un pont Hue sur le réseau local.

```bash
git clone https://github.com/amineutron/halo-light.git
cd halo-light
uv sync
```

## Configuration

L'application a besoin de l'adresse du pont (facultative : elle est découverte automatiquement s'il n'y a qu'un pont) et d'une clé d'application.

### Appairage

```bash
uv run halo-light pair            # adresse découverte automatiquement
uv run halo-light pair --host <adresse-du-pont>
```

Appuyez sur le bouton du pont quand la commande le demande. La clé est enregistrée dans `~/.config/halo-light/config.json`, créé en mode **0600** (dossier en 0700). La clé n'est jamais affichée.

`uv run halo-light discover` liste les ponts connus du service de découverte de Philips.

### Variables d'environnement (prioritaires sur le fichier)

| Variable | Rôle |
|---|---|
| `HUE_APP_KEY` | clé d'application |
| `HUE_BRIDGE_IP` | adresse du pont (sinon découverte via `discovery.meethue.com`, puis mDNS si `zeroconf` est installé : `uv sync --extra mdns`) |
| `HUE_BRIDGE_CA_CERT` | fichier PEM pour vérifier le certificat du pont (facultatif) |
| `HALO_LIGHT_CONFIG` | autre chemin pour le fichier de configuration |

Le pont présente un certificat signé par une autorité privée de Signify : par défaut il n'est pas vérifié (réseau local). Pour l'épingler, fournissez l'autorité avec `HUE_BRIDGE_CA_CERT`.

### Brancher le serveur à un client MCP

```json
{
  "mcpServers": {
    "hue": {
      "command": "uv",
      "args": ["--directory", "/chemin/vers/halo-light", "run", "halo-light"],
      "env": { "HUE_APP_KEY": "<cle>" }
    }
  }
}
```

Évitez d'écrire la clé en clair : préférez le fichier en 0600 ou un gestionnaire de secrets.

## Outils exposés

Tous les outils d'action acceptent `light_id` **ou** `light_name` (lumières), `group_id` **ou** `group_name` (pièces et zones). Si les deux sont fournis, l'identifiant l'emporte.

| Outil | Rôle | Nature |
|---|---|---|
| `get_all_lights`, `get_light`, `find_light_by_name` | lire les lumières | lecture seule |
| `get_all_groups`, `get_group` | lire pièces, zones et maison | lecture seule |
| `get_all_scenes` | lire les scènes et leur pièce | lecture seule |
| `turn_on_light`, `turn_off_light` | allumer / éteindre | écriture, idempotent |
| `set_brightness` | luminosité 0-100 (allume ; 0 éteint) | écriture, idempotent |
| `set_color`, `set_color_rgb`, `set_color_xy` | couleur par nom ou hexadécimal / RGB / xy | écriture, idempotent |
| `set_color_temperature` | blanc en Kelvin (2000 à 6500) | écriture, idempotent |
| `set_color_preset` | préréglage nommé : `warm`, `cool`, `daylight`, `concentration`, `relax`, `reading`, `energize`, `red`, `green`, `blue`, `purple`, `orange` | écriture, idempotent |
| `set_light_effect` | effet dynamique : `none`, `candle`, `fire`, `prism`, `sparkle`, `opal`, `glisten`, `underwater`, `cosmos`, `sunbeam`, `enchant` | écriture, idempotent |
| `alert_light` | clignotement d'identification | écriture |
| `turn_on_group`, `turn_off_group` | allumer / éteindre une pièce ou zone | écriture, idempotent |
| `set_group_brightness`, `set_group_color`, `set_group_color_rgb`, `set_group_color_temperature`, `set_group_color_preset` | idem pour un groupe | écriture, idempotent |
| `activate_scene_by_name` | active une scène par nom dans sa pièce (`group_name` pour départager) | écriture, idempotent |
| `set_scene` | active une scène par identifiant | écriture, idempotent |
| `hue_beat_start`, `hue_beat_stop`, `hue_beat_status`, `hue_beat_set` | extension optionnelle | voir ci-dessous |

Aucun outil n'est destructif : les changements d'état sont réversibles et rien n'est supprimé sur le pont.

### Exemples de résolution de noms

- `light_name="cafe"` trouve « Lampe Café » (accents et casse ignorés).
- `light_name="salon"` avec « Salon Plafond » et « Salon Lampadaire » renvoie une erreur qui liste les deux.
- `scene_name="relax"` existant dans deux pièces renvoie `Relax (Salon), Relax (Chambre)` : ajoutez `group_name="chambre"`.

## Extension optionnelle hue_beat

Les outils `hue_beat_*` pilotent un script externe de synchronisation lumière / musique (par exemple via l'Entertainment API). Ce script n'est **pas** fourni ici. Indiquez son chemin :

```bash
export HUE_BEAT_PATH=/chemin/vers/hue_beat.py
```

Contrat attendu du script :

- lancé en arrière-plan avec `python <script> --palette=P [--mode=M] [--bass-only]` ;
- écrit son PID dans `HUE_BEAT_PID_FILE` et un état JSON (`mode`, `palette`, `bpm`...) dans `HUE_BEAT_STATE_FILE` ;
- lit des commandes JSON (`palette`, `mode`, `brightness`, `floor`, `sensitivity`) dans `HUE_BEAT_CTRL_FILE` ;
- s'arrête proprement sur `SIGTERM`.

Les trois fichiers sont par défaut dans le dossier temporaire du système (`hue_beat.pid`, `hue_beat.state.json`, `hue_beat.ctrl`) ; adaptez les variables aux chemins réels du script. Sans `HUE_BEAT_PATH`, ces outils répondent par une erreur claire et le reste du serveur fonctionne normalement. `HUE_BEAT_PYTHON` (facultatif) désigne l'interpréteur qui lance le script, utile quand celui-ci a besoin de paquets (numpy, audio) absents de l'environnement du serveur ; sinon c'est l'interpréteur du serveur. Pendant la synchronisation, le pont peut ignorer les commandes sur les lumières de la zone de divertissement.

## Brancher Lyra

Le script `ironman-hue` (`hue_beat.py`) de Lyra utilise des chemins fixes, définis par les constantes `PID_FILE`, `STATE_FILE` et `CTRL_FILE` en tête du script. Pour que les outils `hue_beat_*` les retrouvent, posez ces variables dans l'environnement du serveur avec les mêmes valeurs :

```bash
export HUE_BEAT_PATH=<chemin du script hue_beat.py>
export HUE_BEAT_PID_FILE=<valeur de PID_FILE>
export HUE_BEAT_STATE_FILE=<valeur de STATE_FILE>
export HUE_BEAT_CTRL_FILE=<valeur de CTRL_FILE>
```

Les valeurs par défaut du serveur (`hue_beat.pid`, etc.) ne correspondent pas à celles du script : sans ces variables, le statut et les réglages ne l'atteignent pas.

La synchronisation en streaming (DTLS) demande en plus un utilisateur « entertainment », sa clé client et la zone de divertissement. Plutôt que de les écrire dans la configuration du client MCP, ajoutez une section `beat` au fichier `~/.config/halo-light/config.json` (mode 0600) ; le serveur les transmet au script sous les noms `HUE_USER`, `HUE_CLIENTKEY` et `HUE_AREA_ID`, sans jamais les afficher :

```json
{
  "bridge_ip": "<adresse-du-pont>",
  "app_key": "<cle>",
  "beat": { "username": "<utilisateur>", "clientkey": "<cle-client>", "area_id": "<zone>" }
}
```

Sans section `beat`, `HUE_USER` reprend la clé d'application. Une variable d'environnement déjà définie l'emporte toujours.

## Développement

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

Les tests s'exécutent contre un faux pont en mémoire (`httpx.MockTransport`, voir `tests/fake_bridge.py`) et ne touchent jamais un vrai pont. Voir [CONTRIBUTING.md](CONTRIBUTING.md).

## Inspiration et remerciements

Ce projet est une réécriture indépendante, inspirée par l'interface du serveur [ThomasRohde/hue-mcp](https://github.com/ThomasRohde/hue-mcp) (licence MIT, © Thomas Rohde), lui-même construit sur la bibliothèque [phue](https://github.com/studioimaginaire/phue) de Nathanael Lecaude. Les noms de la plupart des outils sont conservés pour rester compatibles avec les assistants qui les appellent déjà.

Aucune ligne de code d'implémentation n'est reprise de ces projets : tout est écrit à partir de la documentation officielle de l'API Hue (CLIP v2). Merci à Thomas Rohde pour le point de départ. Contrairement à ces projets, qui reposent sur l'API v1, celui-ci utilise l'API v2 (identifiants UUID, scènes rattachées à leur pièce).

## Différences avec hue-mcp

- API v2 au lieu de v1 (`phue` n'est plus nécessaire) ; `httpx` asynchrone.
- Pas de groupe par défaut codé en dur (l'ancien groupe 81) : un groupe ou une pièce doit être désigné, sauf pour les scènes qui portent leur propre pièce.
- Pas de cache à rafraîchir : l'état est lu en direct (`refresh_lights` n'existe plus).
- Non repris pour l'instant : `create_group`, `quick_scene`, les préréglages de couleur et les effets (`set_light_effect`). `set_color` remplace les préréglages.
- Nouveautés : `set_color`, `set_color_xy`, groupes par nom, appairage et découverte en ligne de commande.

## Licence

[MIT](LICENSE). Les projets dont ce serveur s'inspire sont cités dans [NOTICE](NOTICE).
