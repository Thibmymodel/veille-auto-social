#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de déploiement pour le système de veille automatisée des créatrices OnlyFans.
Ce script configure l'environnement de production et met en place le système
pour qu'il s'exécute automatiquement.
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
import shutil
from pathlib import Path

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("deployment.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("deployment")

# Constantes
DEPLOYMENT_DIR = "/opt/veille_automatisee"
SERVICE_NAME = "veille-automatisee"
REQUIRED_FILES = [
    "veille_automatisee.py",
    "instagram_scraper.py",
    "twitter_scraper.py",
    "threads_scraper.py",
    "tiktok_scraper.py",
    "content_selector.py",
    "google_sheet_integration.py"
]
DEPENDENCIES = [
    "selenium",
    "beautifulsoup4",
    "gspread",
    "google-auth",
    "google-auth-oauthlib",
    "google-auth-httplib2",
    "google-api-python-client",
    "fake-useragent",
    "schedule",
    "requests",
    "webdriver-manager",
    "chromedriver-autoinstaller"
]

def check_root():
    """Vérifie si le script est exécuté avec les privilèges root."""
    if os.geteuid() != 0:
        logger.error("Ce script doit être exécuté avec les privilèges root (sudo).")
        return False
    return True

def install_system_dependencies():
    """Installe les dépendances système nécessaires."""
    logger.info("Installation des dépendances système...")
    
    try:
        # Mettre à jour les paquets
        subprocess.check_call(["apt-get", "update"])
        
        # Installer les paquets nécessaires
        packages = [
            "python3",
            "python3-pip",
            "python3-venv",
            "chromium-browser",
            "chromium-chromedriver",
            "unzip",
            "wget"
        ]
        
        subprocess.check_call(["apt-get", "install", "-y"] + packages)
        logger.info("Dépendances système installées avec succès.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Erreur lors de l'installation des dépendances système: {str(e)}")
        return False

def create_virtual_environment():
    """Crée un environnement virtuel Python pour le déploiement."""
    logger.info("Création de l'environnement virtuel...")
    
    venv_path = os.path.join(DEPLOYMENT_DIR, "venv")
    
    try:
        # Créer l'environnement virtuel
        subprocess.check_call([sys.executable, "-m", "venv", venv_path])
        
        # Installer les dépendances Python
        pip_path = os.path.join(venv_path, "bin", "pip")
        subprocess.check_call([pip_path, "install", "--upgrade", "pip"])
        subprocess.check_call([pip_path, "install"] + DEPENDENCIES)
        
        logger.info(f"Environnement virtuel créé avec succès: {venv_path}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Erreur lors de la création de l'environnement virtuel: {str(e)}")
        return False

def copy_files():
    """Copie les fichiers nécessaires vers le répertoire de déploiement."""
    logger.info("Copie des fichiers vers le répertoire de déploiement...")
    
    try:
        # Créer le répertoire de déploiement s'il n'existe pas
        os.makedirs(DEPLOYMENT_DIR, exist_ok=True)
        
        # Copier les fichiers
        for file in REQUIRED_FILES:
            src = os.path.join(os.getcwd(), file)
            dst = os.path.join(DEPLOYMENT_DIR, file)
            
            if os.path.exists(src):
                shutil.copy2(src, dst)
                logger.info(f"Fichier copié: {src} -> {dst}")
            else:
                logger.error(f"Fichier source introuvable: {src}")
                return False
        
        # Créer le répertoire pour les logs
        os.makedirs(os.path.join(DEPLOYMENT_DIR, "logs"), exist_ok=True)
        
        logger.info("Fichiers copiés avec succès.")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la copie des fichiers: {str(e)}")
        return False

def create_service_file():
    """Crée un fichier de service systemd pour l'exécution automatique."""
    logger.info("Création du fichier de service systemd...")
    
    service_content = f"""[Unit]
Description=Service de veille automatisée pour créatrices OnlyFans
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={DEPLOYMENT_DIR}
ExecStart={DEPLOYMENT_DIR}/venv/bin/python3 {DEPLOYMENT_DIR}/veille_automatisee.py --continuous
Restart=always
RestartSec=3600
StandardOutput=append:{DEPLOYMENT_DIR}/logs/service.log
StandardError=append:{DEPLOYMENT_DIR}/logs/service.log

[Install]
WantedBy=multi-user.target
"""
    
    try:
        service_path = f"/etc/systemd/system/{SERVICE_NAME}.service"
        
        with open(service_path, "w") as f:
            f.write(service_content)
        
        logger.info(f"Fichier de service créé: {service_path}")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la création du fichier de service: {str(e)}")
        return False

def enable_service():
    """Active et démarre le service systemd."""
    logger.info("Activation et démarrage du service...")
    
    try:
        # Recharger systemd
        subprocess.check_call(["systemctl", "daemon-reload"])
        
        # Activer le service
        subprocess.check_call(["systemctl", "enable", SERVICE_NAME])
        
        # Démarrer le service
        subprocess.check_call(["systemctl", "start", SERVICE_NAME])
        
        # Vérifier l'état du service
        subprocess.check_call(["systemctl", "status", SERVICE_NAME])
        
        logger.info(f"Service {SERVICE_NAME} activé et démarré avec succès.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Erreur lors de l'activation du service: {str(e)}")
        return False

def create_oauth_setup():
    """Crée un script pour configurer l'authentification OAuth2."""
    logger.info("Création du script de configuration OAuth2...")
    
    oauth_script = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# Constantes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
CLIENT_SECRETS_FILE = 'client_secrets.json'
TOKEN_FILE = 'token.json'

def setup_oauth():
    """Configure l'authentification OAuth2 pour Google Sheets."""
    print("Configuration de l'authentification OAuth2 pour Google Sheets")
    
    # Vérifier si le fichier client_secrets.json existe
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"Erreur: Le fichier {CLIENT_SECRETS_FILE} n'existe pas.")
        print("Veuillez créer ce fichier avec vos identifiants OAuth2 Google.")
        return False
    
    # Créer le flow OAuth2
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES
    )
    
    # Exécuter le flow d'authentification
    creds = flow.run_local_server(port=0)
    
    # Sauvegarder les credentials
    with open(TOKEN_FILE, 'w') as token:
        token.write(creds.to_json())
    
    print(f"Authentification réussie. Token sauvegardé dans {TOKEN_FILE}")
    return True

if __name__ == "__main__":
    setup_oauth()
"""
    
    try:
        oauth_script_path = os.path.join(DEPLOYMENT_DIR, "setup_oauth.py")
        
        with open(oauth_script_path, "w") as f:
            f.write(oauth_script)
        
        # Rendre le script exécutable
        os.chmod(oauth_script_path, 0o755)
        
        logger.info(f"Script de configuration OAuth2 créé: {oauth_script_path}")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la création du script OAuth2: {str(e)}")
        return False

def create_service_account_setup():
    """Crée un script pour configurer l'authentification par compte de service."""
    logger.info("Création du script de configuration du compte de service...")
    
    service_account_script = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import argparse

# Constantes
SERVICE_ACCOUNT_FILE = 'service_account.json'

def setup_service_account(json_file=None, json_content=None):
    """Configure l'authentification par compte de service pour Google Sheets."""
    print("Configuration de l'authentification par compte de service pour Google Sheets")
    
    if json_file:
        # Copier le fichier
        try:
            with open(json_file, 'r') as src:
                content = src.read()
            
            with open(SERVICE_ACCOUNT_FILE, 'w') as dst:
                dst.write(content)
            
            print(f"Fichier de compte de service copié: {json_file} -> {SERVICE_ACCOUNT_FILE}")
            return True
        except Exception as e:
            print(f"Erreur lors de la copie du fichier: {str(e)}")
            return False
    
    elif json_content:
        # Écrire le contenu JSON
        try:
            with open(SERVICE_ACCOUNT_FILE, 'w') as f:
                f.write(json_content)
            
            print(f"Fichier de compte de service créé: {SERVICE_ACCOUNT_FILE}")
            return True
        except Exception as e:
            print(f"Erreur lors de la création du fichier: {str(e)}")
            return False
    
    else:
        print("Erreur: Vous devez spécifier soit un fichier JSON, soit le contenu JSON.")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Configuration du compte de service pour Google Sheets")
    parser.add_argument("--file", help="Chemin vers le fichier JSON du compte de service")
    parser.add_argument("--content", help="Contenu JSON du compte de service")
    
    args = parser.parse_args()
    
    if not args.file and not args.content:
        parser.print_help()
    else:
        setup_service_account(args.file, args.content)
"""
    
    try:
        script_path = os.path.join(DEPLOYMENT_DIR, "setup_service_account.py")
        
        with open(script_path, "w") as f:
            f.write(service_account_script)
        
        # Rendre le script exécutable
        os.chmod(script_path, 0o755)
        
        logger.info(f"Script de configuration du compte de service créé: {script_path}")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la création du script de compte de service: {str(e)}")
        return False

def create_deployment_readme():
    """Crée un fichier README pour le déploiement."""
    logger.info("Création du fichier README pour le déploiement...")
    
    readme_content = """# Système de veille automatisée pour créatrices OnlyFans

## Déploiement

Le système a été déployé avec succès dans le répertoire `/opt/veille_automatisee`.

## Configuration de l'authentification Google

Avant de pouvoir utiliser le système, vous devez configurer l'authentification pour Google Sheets.
Vous avez deux options :

### Option 1 : Authentification OAuth2

1. Créez un projet dans la [Console Google Cloud](https://console.cloud.google.com/)
2. Activez l'API Google Sheets et l'API Google Drive
3. Créez des identifiants OAuth2 (type "Application de bureau")
4. Téléchargez le fichier JSON des identifiants et renommez-le en `client_secrets.json`
5. Placez ce fichier dans le répertoire `/opt/veille_automatisee`
6. Exécutez le script de configuration OAuth2 :
   ```
   cd /opt/veille_automatisee
   ./setup_oauth.py
   ```
7. Suivez les instructions pour vous authentifier

### Option 2 : Authentification par compte de service

1. Créez un projet dans la [Console Google Cloud](https://console.cloud.google.com/)
2. Activez l'API Google Sheets et l'API Google Drive
3. Créez un compte de service
4. Téléchargez la clé JSON du compte de service
5. Partagez votre Google Sheet avec l'adresse email du compte de service (avec les droits d'édition)
6. Utilisez le script de configuration du compte de service :
   ```
   cd /opt/veille_automatisee
   ./setup_service_account.py --file /chemin/vers/votre/fichier.json
   ```

## Gestion du service

Le système s'exécute comme un service systemd nommé `veille-automatisee`.

### Commandes utiles

- Vérifier l'état du service :
  ```
  systemctl status veille-automatisee
  ```

- Démarrer le service :
  ```
  systemctl start veille-automatisee
  ```

- Arrêter le service :
  ```
  systemctl stop veille-automatisee
  ```

- Redémarrer le service :
  ```
  systemctl restart veille-automatisee
  ```

- Consulter les logs du service :
  ```
  journalctl -u veille-automatisee
  ```
  ou
  ```
  cat /opt/veille_automatisee/logs/service.log
  ```

## Fonctionnement

Le système s'exécute en continu jusqu'à atteindre le quota journalier, puis se relance automatiquement chaque jour.

Les logs détaillés sont disponibles dans le répertoire `/opt/veille_automatisee/logs`.

## Dépannage

Si vous rencontrez des problèmes, vérifiez les points suivants :

1. Assurez-vous que l'authentification Google est correctement configurée
2. Vérifiez que le Google Sheet est partagé avec le compte de service (si vous utilisez cette méthode)
3. Consultez les logs pour identifier les erreurs spécifiques
4. Vérifiez que le service est en cours d'exécution

Pour toute assistance supplémentaire, contactez l'administrateur système.
"""
    
    try:
        readme_path = os.path.join(DEPLOYMENT_DIR, "README.md")
        
        with open(readme_path, "w") as f:
            f.write(readme_content)
        
        logger.info(f"Fichier README créé: {readme_path}")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la création du fichier README: {str(e)}")
        return False

def create_railway_deployment_files():
    """Crée les fichiers nécessaires pour le déploiement sur Railway."""
    logger.info("Création des fichiers pour le déploiement sur Railway...")
    
    # Créer le fichier Procfile
    procfile_content = "web: python veille_automatisee.py --continuous"
    
    try:
        procfile_path = os.path.join(DEPLOYMENT_DIR, "Procfile")
        
        with open(procfile_path, "w") as f:
            f.write(procfile_content)
        
        logger.info(f"Fichier Procfile créé: {procfile_path}")
    except Exception as e:
        logger.error(f"Erreur lors de la création du fichier Procfile: {str(e)}")
        return False
    
    # Créer le fichier requirements.txt
    try:
        requirements_path = os.path.join(DEPLOYMENT_DIR, "requirements.txt")
        
        with open(requirements_path, "w") as f:
            f.write("\n".join(DEPENDENCIES))
        
        logger.info(f"Fichier requirements.txt créé: {requirements_path}")
    except Exception as e:
        logger.error(f"Erreur lors de la création du fichier requirements.txt: {str(e)}")
        return False
    
    # Créer le fichier runtime.txt
    try:
        runtime_path = os.path.join(DEPLOYMENT_DIR, "runtime.txt")
        
        with open(runtime_path, "w") as f:
            f.write("python-3.10.12")
        
        logger.info(f"Fichier runtime.txt créé: {runtime_path}")
    except Exception as e:
        logger.error(f"Erreur lors de la création du fichier runtime.txt: {str(e)}")
        return False
    
    # Créer le fichier railway.json
    railway_json_content = """{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python veille_automatisee.py --continuous",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}"""
    
    try:
        railway_json_path = os.path.join(DEPLOYMENT_DIR, "railway.json")
        
        with open(railway_json_path, "w") as f:
            f.write(railway_json_content)
        
        logger.info(f"Fichier railway.json créé: {railway_json_path}")
    except Exception as e:
        logger.error(f"Erreur lors de la création du fichier railway.json: {str(e)}")
        return False
    
    # Créer le fichier README pour Railway
    railway_readme_content = """# Déploiement sur Railway

Ce dossier contient tous les fichiers nécessaires pour déployer le système de veille automatisée sur Railway.

## Étapes de déploiement

1. Créez un compte sur [Railway](https://railway.app/) si vous n'en avez pas déjà un
2. Installez la CLI Railway :
   ```
   npm i -g @railway/cli
   ```
3. Connectez-vous à votre compte Railway :
   ```
   railway login
   ```
4. Initialisez un nouveau projet Railway :
   ```
   railway init
   ```
5. Déployez le projet :
   ```
   railway up
   ```

## Configuration de l'authentification Google

Avant de pouvoir utiliser le système, vous devez configurer l'authentification pour Google Sheets.
Sur Railway, vous devez utiliser l'authentification par compte de service :

1. Créez un projet dans la [Console Google Cloud](https://console.cloud.google.com/)
2. Activez l'API Google Sheets et l'API Google Drive
3. Créez un compte de service
4. Téléchargez la clé JSON du compte de service
5. Partagez votre Google Sheet avec l'adresse email du compte de service (avec les droits d'édition)
6. Ajoutez le contenu du fichier JSON comme variable d'environnement dans Railway :
   ```
   railway variables set GOOGLE_SERVICE_ACCOUNT_JSON='contenu_du_fichier_json'
   ```

## Surveillance et maintenance

Vous pouvez surveiller l'exécution de votre application dans le tableau de bord Railway.
Les logs sont disponibles directement dans l'interface Railway.

Pour mettre à jour votre application, il vous suffit de pousser les modifications vers votre dépôt Git connecté à Railway,
ou d'utiliser à nouveau la commande `railway up`.
"""
    
    try:
        railway_readme_path = os.path.join(DEPLOYMENT_DIR, "RAILWAY_README.md")
        
        with open(railway_readme_path, "w") as f:
            f.write(railway_readme_content)
        
        logger.info(f"Fichier README pour Railway créé: {railway_readme_path}")
    except Exception as e:
        logger.error(f"Erreur lors de la création du fichier README pour Railway: {str(e)}")
        return False
    
    return True

def create_wsl_deployment_files():
    """Crée les fichiers nécessaires pour le déploiement sur WSL."""
    logger.info("Création des fichiers pour le déploiement sur WSL...")
    
    # Créer le script d'installation pour WSL
    wsl_install_script = """#!/bin/bash

# Script d'installation pour WSL
echo "Installation du système de veille automatisée sur WSL..."

# Vérifier si l'utilisateur a les droits sudo
if ! sudo -v; then
    echo "Erreur: Vous devez avoir les droits sudo pour installer le système."
    exit 1
fi

# Mettre à jour les paquets
echo "Mise à jour des paquets..."
sudo apt-get update

# Installer les dépendances système
echo "Installation des dépendances système..."
sudo apt-get install -y python3 python3-pip python3-venv chromium-browser chromium-chromedriver unzip wget

# Créer le répertoire d'installation
INSTALL_DIR="$HOME/veille_automatisee"
echo "Création du répertoire d'installation: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/logs"

# Copier les fichiers
echo "Copie des fichiers..."
cp *.py "$INSTALL_DIR/"

# Créer l'environnement virtuel
echo "Création de l'environnement virtuel..."
python3 -m venv "$INSTALL_DIR/venv"

# Installer les dépendances Python
echo "Installation des dépendances Python..."
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install selenium beautifulsoup4 gspread google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client fake-useragent schedule requests webdriver-manager chromedriver-autoinstaller

# Créer le script de lancement
echo "Création du script de lancement..."
cat > "$INSTALL_DIR/run.sh" << 'EOF'
#!/bin/bash

# Activer l'environnement virtuel
source "$(dirname "$0")/venv/bin/activate"

# Exécuter le script
python "$(dirname "$0")/veille_automatisee.py" "$@"
EOF

# Rendre le script exécutable
chmod +x "$INSTALL_DIR/run.sh"

# Créer le script de configuration OAuth
echo "Création du script de configuration OAuth..."
cat > "$INSTALL_DIR/setup_oauth.sh" << 'EOF'
#!/bin/bash

# Activer l'environnement virtuel
source "$(dirname "$0")/venv/bin/activate"

# Exécuter le script
python - << 'PYTHON_SCRIPT'
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# Constantes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
CLIENT_SECRETS_FILE = 'client_secrets.json'
TOKEN_FILE = 'token.json'

def setup_oauth():
    """Configure l'authentification OAuth2 pour Google Sheets."""
    print("Configuration de l'authentification OAuth2 pour Google Sheets")
    
    # Vérifier si le fichier client_secrets.json existe
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"Erreur: Le fichier {CLIENT_SECRETS_FILE} n'existe pas.")
        print("Veuillez créer ce fichier avec vos identifiants OAuth2 Google.")
        return False
    
    # Créer le flow OAuth2
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES
    )
    
    # Exécuter le flow d'authentification
    creds = flow.run_local_server(port=0)
    
    # Sauvegarder les credentials
    with open(TOKEN_FILE, 'w') as token:
        token.write(creds.to_json())
    
    print(f"Authentification réussie. Token sauvegardé dans {TOKEN_FILE}")
    return True

if __name__ == "__main__":
    setup_oauth()
PYTHON_SCRIPT
EOF

# Rendre le script exécutable
chmod +x "$INSTALL_DIR/setup_oauth.sh"

# Créer le script de configuration du compte de service
echo "Création du script de configuration du compte de service..."
cat > "$INSTALL_DIR/setup_service_account.sh" << 'EOF'
#!/bin/bash

# Activer l'environnement virtuel
source "$(dirname "$0")/venv/bin/activate"

# Vérifier les arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <chemin_vers_fichier_json>"
    exit 1
fi

# Copier le fichier JSON
cp "$1" "$(dirname "$0")/service_account.json"
echo "Fichier de compte de service copié: $1 -> $(dirname "$0")/service_account.json"
EOF

# Rendre le script exécutable
chmod +x "$INSTALL_DIR/setup_service_account.sh"

# Créer le fichier README
echo "Création du fichier README..."
cat > "$INSTALL_DIR/README.md" << 'EOF'
# Système de veille automatisée pour créatrices OnlyFans (WSL)

## Installation

Le système a été installé avec succès dans le répertoire `~/veille_automatisee`.

## Configuration de l'authentification Google

Avant de pouvoir utiliser le système, vous devez configurer l'authentification pour Google Sheets.
Vous avez deux options :

### Option 1 : Authentification OAuth2

1. Créez un projet dans la [Console Google Cloud](https://console.cloud.google.com/)
2. Activez l'API Google Sheets et l'API Google Drive
3. Créez des identifiants OAuth2 (type "Application de bureau")
4. Téléchargez le fichier JSON des identifiants et renommez-le en `client_secrets.json`
5. Placez ce fichier dans le répertoire `~/veille_automatisee`
6. Exécutez le script de configuration OAuth2 :
   ```
   cd ~/veille_automatisee
   ./setup_oauth.sh
   ```
7. Suivez les instructions pour vous authentifier

### Option 2 : Authentification par compte de service

1. Créez un projet dans la [Console Google Cloud](https://console.cloud.google.com/)
2. Activez l'API Google Sheets et l'API Google Drive
3. Créez un compte de service
4. Téléchargez la clé JSON du compte de service
5. Partagez votre Google Sheet avec l'adresse email du compte de service (avec les droits d'édition)
6. Utilisez le script de configuration du compte de service :
   ```
   cd ~/veille_automatisee
   ./setup_service_account.sh /chemin/vers/votre/fichier.json
   ```

## Utilisation

Pour exécuter le système, utilisez le script de lancement :

```
cd ~/veille_automatisee
./run.sh --continuous
```

Options disponibles :
- `--test` : Exécuter en mode test (une seule fois)
- `--continuous` : Exécuter en continu jusqu'à atteindre le quota journalier
- `--instagram-only` : Exécuter uniquement le scraping Instagram
- `--twitter-only` : Exécuter uniquement le scraping Twitter
- `--threads-only` : Exécuter uniquement le scraping Threads
- `--tiktok-only` : Exécuter uniquement le scraping TikTok
- `--trending-only` : Exécuter uniquement le scraping des tendances
- `--model <nom>` : Exécuter uniquement pour un modèle spécifique

## Exécution en arrière-plan

Pour exécuter le système en arrière-plan, vous pouvez utiliser `nohup` :

```
cd ~/veille_automatisee
nohup ./run.sh --continuous > logs/nohup.log 2>&1 &
```

Pour vérifier si le processus est en cours d'exécution :

```
ps aux | grep veille_automatisee
```

Pour arrêter le processus :

```
pkill -f veille_automatisee
```

## Logs

Les logs sont disponibles dans le répertoire `~/veille_automatisee/logs`.

## Dépannage

Si vous rencontrez des problèmes, vérifiez les points suivants :

1. Assurez-vous que l'authentification Google est correctement configurée
2. Vérifiez que le Google Sheet est partagé avec le compte de service (si vous utilisez cette méthode)
3. Consultez les logs pour identifier les erreurs spécifiques
4. Vérifiez que le processus est en cours d'exécution
EOF

echo "Installation terminée avec succès!"
echo "Le système est installé dans $INSTALL_DIR"
echo "Consultez le fichier README.md dans $INSTALL_DIR pour plus d'informations"
"""
    
    try:
        wsl_script_path = os.path.join(DEPLOYMENT_DIR, "install_wsl.sh")
        
        with open(wsl_script_path, "w") as f:
            f.write(wsl_install_script)
        
        # Rendre le script exécutable
        os.chmod(wsl_script_path, 0o755)
        
        logger.info(f"Script d'installation pour WSL créé: {wsl_script_path}")
    except Exception as e:
        logger.error(f"Erreur lors de la création du script d'installation pour WSL: {str(e)}")
        return False
    
    # Créer le fichier README pour WSL
    wsl_readme_content = """# Installation sur Windows avec WSL

Ce dossier contient les fichiers nécessaires pour installer le système de veille automatisée sur Windows avec WSL (Windows Subsystem for Linux).

## Prérequis

1. Windows 10 version 2004 ou ultérieure (Build 19041 ou ultérieur) ou Windows 11
2. WSL 2 installé

## Installation de WSL

Si vous n'avez pas encore installé WSL, suivez ces étapes :

1. Ouvrez PowerShell en tant qu'administrateur
2. Exécutez la commande suivante :
   ```
   wsl --install
   ```
3. Redémarrez votre ordinateur
4. Une fois le redémarrage terminé, Ubuntu sera automatiquement installé et configuré
5. Créez un nom d'utilisateur et un mot de passe lorsque vous y êtes invité

## Installation du système de veille automatisée

1. Ouvrez Ubuntu depuis le menu Démarrer
2. Naviguez vers le répertoire où vous avez téléchargé les fichiers du système :
   ```
   cd /mnt/c/Chemin/Vers/Votre/Dossier
   ```
3. Exécutez le script d'installation :
   ```
   bash install_wsl.sh
   ```
4. Suivez les instructions à l'écran

## Configuration de l'authentification Google

Après l'installation, vous devez configurer l'authentification pour Google Sheets.
Consultez le fichier README.md dans le répertoire d'installation pour les instructions détaillées.

## Utilisation

Pour exécuter le système, utilisez le script de lancement :

```
cd ~/veille_automatisee
./run.sh --continuous
```

Pour plus d'informations, consultez le fichier README.md dans le répertoire d'installation.

## Résolution des problèmes courants

### Erreur lors de l'authentification OAuth

Si vous rencontrez une erreur lors de la configuration de l'écran de consentement OAuth dans Google Cloud, où l'interface affiche 'Vous ne pouvez pas créer d'écran de consentement OAuth pour ce projet', essayez les solutions suivantes :

1. Vérifiez que vous êtes connecté avec le compte propriétaire du projet
2. Créez un nouveau projet Google Cloud avec les permissions appropriées
3. Assurez-vous que les API Google Sheets et Google Drive sont activées

### Erreur 403 lors de l'authentification GitHub

Si vous rencontrez une erreur 403 'Permission denied' lors de l'authentification GitHub dans WSL, le problème est généralement lié à l'utilisation d'un mot de passe au lieu d'un token d'accès personnel. La solution consiste à :

1. Créer un token d'accès personnel sur GitHub.com en allant dans Settings > Developer settings > Personal access tokens > Generate new token
2. Sélectionner au minimum les permissions 'repo'
3. Copier le token généré
4. Utiliser ce token comme mot de passe lors de l'authentification Git
5. Si l'erreur persiste, essayer d'utiliser SSH au lieu de HTTPS pour la connexion au dépôt GitHub
"""
    
    try:
        wsl_readme_path = os.path.join(DEPLOYMENT_DIR, "WSL_README.md")
        
        with open(wsl_readme_path, "w") as f:
            f.write(wsl_readme_content)
        
        logger.info(f"Fichier README pour WSL créé: {wsl_readme_path}")
    except Exception as e:
        logger.error(f"Erreur lors de la création du fichier README pour WSL: {str(e)}")
        return False
    
    return True

def deploy():
    """Exécute le processus complet de déploiement."""
    logger.info("Début du déploiement...")
    
    # Vérifier les privilèges root
    if not check_root():
        return False
    
    # Installer les dépendances système
    if not install_system_dependencies():
        return False
    
    # Copier les fichiers
    if not copy_files():
        return False
    
    # Créer l'environnement virtuel
    if not create_virtual_environment():
        return False
    
    # Créer les scripts de configuration d'authentification
    if not create_oauth_setup():
        return False
    
    if not create_service_account_setup():
        return False
    
    # Créer le fichier de service systemd
    if not create_service_file():
        return False
    
    # Activer et démarrer le service
    if not enable_service():
        return False
    
    # Créer le fichier README
    if not create_deployment_readme():
        return False
    
    # Créer les fichiers pour le déploiement sur Railway
    if not create_railway_deployment_files():
        return False
    
    # Créer les fichiers pour le déploiement sur WSL
    if not create_wsl_deployment_files():
        return False
    
    logger.info("Déploiement terminé avec succès!")
    logger.info(f"Le système est déployé dans {DEPLOYMENT_DIR}")
    logger.info(f"Le service systemd {SERVICE_NAME} est activé et démarré")
    logger.info(f"Consultez le fichier README.md dans {DEPLOYMENT_DIR} pour plus d'informations")
    logger.info(f"Pour le déploiement sur Railway, consultez le fichier RAILWAY_README.md")
    logger.info(f"Pour l'installation sur WSL, consultez le fichier WSL_README.md")
    
    return True

def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(description="Déploiement du système de veille automatisée")
    parser.add_argument("--no-service", action="store_true", help="Ne pas créer ni démarrer le service systemd")
    parser.add_argument("--railway-only", action="store_true", help="Créer uniquement les fichiers pour Railway")
    parser.add_argument("--wsl-only", action="store_true", help="Créer uniquement les fichiers pour WSL")
    
    args = parser.parse_args()
    
    if args.railway_only:
        logger.info("Mode Railway uniquement: création des fichiers pour Railway")
        
        # Créer le répertoire de déploiement s'il n'existe pas
        os.makedirs(DEPLOYMENT_DIR, exist_ok=True)
        
        # Copier les fichiers
        if not copy_files():
            return
        
        # Créer les fichiers pour le déploiement sur Railway
        if not create_railway_deployment_files():
            return
        
        logger.info("Fichiers pour Railway créés avec succès!")
        logger.info(f"Consultez le fichier RAILWAY_README.md dans {DEPLOYMENT_DIR} pour plus d'informations")
        return
    
    if args.wsl_only:
        logger.info("Mode WSL uniquement: création des fichiers pour WSL")
        
        # Créer le répertoire de déploiement s'il n'existe pas
        os.makedirs(DEPLOYMENT_DIR, exist_ok=True)
        
        # Copier les fichiers
        if not copy_files():
            return
        
        # Créer les fichiers pour le déploiement sur WSL
        if not create_wsl_deployment_files():
            return
        
        logger.info("Fichiers pour WSL créés avec succès!")
        logger.info(f"Consultez le fichier WSL_README.md dans {DEPLOYMENT_DIR} pour plus d'informations")
        return
    
    if args.no_service:
        logger.info("Mode sans service: le service systemd ne sera pas créé ni démarré")
        
        # Vérifier les privilèges root
        if not check_root():
            return
        
        # Installer les dépendances système
        if not install_system_dependencies():
            return
        
        # Copier les fichiers
        if not copy_files():
            return
        
        # Créer l'environnement virtuel
        if not create_virtual_environment():
            return
        
        # Créer les scripts de configuration d'authentification
        if not create_oauth_setup():
            return
        
        if not create_service_account_setup():
            return
        
        # Créer le fichier README
        if not create_deployment_readme():
            return
        
        # Créer les fichiers pour le déploiement sur Railway
        if not create_railway_deployment_files():
            return
        
        # Créer les fichiers pour le déploiement sur WSL
        if not create_wsl_deployment_files():
            return
        
        logger.info("Déploiement sans service terminé avec succès!")
        logger.info(f"Le système est déployé dans {DEPLOYMENT_DIR}")
        logger.info(f"Consultez le fichier README.md dans {DEPLOYMENT_DIR} pour plus d'informations")
        logger.info(f"Pour le déploiement sur Railway, consultez le fichier RAILWAY_README.md")
        logger.info(f"Pour l'installation sur WSL, consultez le fichier WSL_README.md")
    else:
        # Mode par défaut: déploiement complet
        deploy()

if __name__ == "__main__":
    main()
