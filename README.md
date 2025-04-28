# Système de Veille Automatisée pour Créatrices OnlyFans

## Description

Ce système permet d'automatiser la veille de contenu sur les réseaux sociaux pour les créatrices OnlyFans.
Il collecte du contenu depuis Instagram, Twitter, Threads et TikTok, sélectionne les contenus les plus pertinents
selon des critères spécifiques, et met à jour un Google Sheet avec les résultats.

## Contenu de l'archive

Cette archive contient les fichiers suivants :

- `veille_automatisee.py` : Script principal
- `instagram_scraper.py` : Module de scraping Instagram
- `twitter_scraper.py` : Module de scraping Twitter
- `threads_scraper.py` : Module de scraping Threads
- `tiktok_scraper.py` : Module de scraping TikTok
- `content_selector.py` : Module de sélection de contenu
- `google_sheet_integration.py` : Module d'intégration Google Sheets
- `deploy.py` : Script de déploiement
- `documentation.md` : Documentation complète du système
- `README.md` : Ce fichier

## Installation rapide

### Linux

```bash
# Installer les dépendances système
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv chromium-browser chromium-chromedriver

# Cloner le dépôt ou extraire l'archive
cd /chemin/vers/dossier

# Installer les dépendances Python
pip3 install -r requirements.txt

# Configurer l'authentification Google
# (voir la section Configuration ci-dessous)

# Exécuter le système
python3 veille_automatisee.py --continuous
```

### Windows avec WSL

1. Installez WSL si ce n'est pas déjà fait :
   ```
   wsl --install
   ```

2. Ouvrez Ubuntu depuis le menu Démarrer

3. Naviguez vers le dossier contenant les fichiers :
   ```
   cd /mnt/c/Chemin/Vers/Votre/Dossier
   ```

4. Exécutez le script d'installation WSL :
   ```
   bash install_wsl.sh
   ```

5. Suivez les instructions à l'écran

### Déploiement complet

Pour un déploiement complet avec service systemd :

```bash
sudo python3 deploy.py
```

Pour plus d'options de déploiement :

```bash
python3 deploy.py --help
```

## Configuration

### Authentification Google

Avant de pouvoir utiliser le système, vous devez configurer l'authentification pour Google Sheets.
Vous avez deux options :

#### Option 1 : Authentification OAuth2

1. Créez un projet dans la [Console Google Cloud](https://console.cloud.google.com/)
2. Activez l'API Google Sheets et l'API Google Drive
3. Créez des identifiants OAuth2 (type "Application de bureau")
4. Téléchargez le fichier JSON des identifiants et renommez-le en `client_secrets.json`
5. Placez ce fichier dans le même répertoire que les scripts

#### Option 2 : Authentification par compte de service

1. Créez un projet dans la [Console Google Cloud](https://console.cloud.google.com/)
2. Activez l'API Google Sheets et l'API Google Drive
3. Créez un compte de service
4. Téléchargez la clé JSON du compte de service et renommez-la en `service_account.json`
5. Partagez votre Google Sheet avec l'adresse email du compte de service (avec les droits d'édition)
6. Placez ce fichier dans le même répertoire que les scripts

### Configuration des modèles

Les modèles sont configurés dans le fichier `veille_automatisee.py`. Vous pouvez modifier les informations des modèles existants ou ajouter de nouveaux modèles selon vos besoins.

## Utilisation

### Exécution de base

```bash
python3 veille_automatisee.py
```

### Options disponibles

- `--test` : Exécuter en mode test (une seule fois)
- `--continuous` : Exécuter en continu jusqu'à atteindre le quota journalier
- `--schedule` : Planifier l'exécution quotidienne
- `--hour` : Heure d'exécution planifiée (0-23)
- `--minute` : Minute d'exécution planifiée (0-59)
- `--instagram-only` : Exécuter uniquement le scraping Instagram
- `--twitter-only` : Exécuter uniquement le scraping Twitter
- `--threads-only` : Exécuter uniquement le scraping Threads
- `--tiktok-only` : Exécuter uniquement le scraping TikTok
- `--trending-only` : Exécuter uniquement le scraping des tendances
- `--model <nom>` : Exécuter uniquement pour un modèle spécifique

## Documentation complète

Pour une documentation complète, consultez le fichier `documentation.md`.

## Support et contact

Pour toute question ou problème, veuillez contacter l'administrateur système.

---

© 2025 Système de Veille Automatisée pour Créatrices OnlyFans
