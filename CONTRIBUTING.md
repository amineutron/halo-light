# Contribuer

Merci de votre intérêt. Quelques règles simples :

1. Installer l'environnement : `uv sync`.
2. Avant chaque commit : `uv run ruff check .`, `uv run ruff format --check .` et `uv run pytest`.
3. Tout bug corrigé s'accompagne d'un test de régression, écrit avant le correctif.
4. Les tests n'utilisent jamais un vrai pont : on passe par `tests/fake_bridge.py` (`httpx.MockTransport`).
5. Messages de commit en anglais, format conventionnel (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
6. Aucun secret, adresse IP privée ni chemin personnel dans le dépôt ; la configuration passe par l'environnement ou un fichier en mode 0600.
7. Code et commits en anglais, documentation utilisateur en français.
8. Ne copiez pas de code depuis d'autres projets sans en vérifier la licence ; appuyez-vous sur la documentation officielle de l'API Hue.
