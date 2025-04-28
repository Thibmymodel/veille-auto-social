#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module d'intégration Google Sheet pour la veille automatisée des créatrices OnlyFans.
Ce module contient les fonctions nécessaires pour mettre à jour le Google Sheet
avec le contenu sélectionné pour chaque modèle.
Il est conçu pour lire les credentials depuis les variables d'environnement
SERVICE_ACCOUNT_JSON ou GOOGLE_OAUTH_TOKEN_JSON lorsqu'il est déployé.
"""

import os
import json
import time
import logging
import datetime
from typing import Dict, List, Any, Optional
import gspread
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as UserCredentials # Renommer pour éviter conflit
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("google_sheet_integration.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("google_sheet_integration")

# Constantes pour l'authentification Google
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
SERVICE_ACCOUNT_FILE = 'service_account.json' # Utilisé comme fallback local
TOKEN_FILE = 'token.json' # Utilisé comme fallback local

class GoogleSheetIntegration:
    """Classe pour l'intégration avec Google Sheet."""
    
    def __init__(self, spreadsheet_id: str):
        """
        Initialise l'intégration Google Sheet.
        
        Args:
            spreadsheet_id (str): ID du Google Sheet à mettre à jour
        """
        self.spreadsheet_id = spreadsheet_id
        self.client = None
        self.spreadsheet = None
    
    def authenticate(self):
        """
        Authentifie auprès de l'API Google Sheets en utilisant un compte de service.
        Priorise la variable d'environnement SERVICE_ACCOUNT_JSON.
        
        Returns:
            bool: True si l'authentification a réussi, False sinon
        """
        creds = None
        try:
            service_account_json_str = os.environ.get('SERVICE_ACCOUNT_JSON')
            if service_account_json_str:
                try:
                    logger.info("Utilisation des credentials du compte de service depuis la variable d'environnement SERVICE_ACCOUNT_JSON")
                    service_account_info = json.loads(service_account_json_str)
                    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
                except json.JSONDecodeError:
                    logger.error("Erreur lors du décodage JSON de la variable d'environnement SERVICE_ACCOUNT_JSON")
                    return False
                except Exception as e:
                    logger.error(f"Erreur lors de l'utilisation des credentials depuis SERVICE_ACCOUNT_JSON: {str(e)}")
                    return False
            elif os.path.exists(SERVICE_ACCOUNT_FILE):
                logger.warning(f"Variable d'environnement SERVICE_ACCOUNT_JSON non trouvée. Tentative d'utilisation du fichier local: {SERVICE_ACCOUNT_FILE}")
                creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
            else:
                logger.error(f"Credentials du compte de service non trouvés (ni variable d'environnement SERVICE_ACCOUNT_JSON, ni fichier {SERVICE_ACCOUNT_FILE})")
                return False

            # Créer le client gspread
            self.client = gspread.authorize(creds)
            
            # Ouvrir le Google Sheet
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            
            logger.info(f"Authentification (compte de service) réussie pour le Google Sheet: {self.spreadsheet.title}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'authentification (compte de service): {str(e)}")
            return False
    
    def authenticate_with_oauth(self):
        """
        Authentifie auprès de l'API Google Sheets en utilisant OAuth2.
        Priorise la variable d'environnement GOOGLE_OAUTH_TOKEN_JSON.
        
        Returns:
            bool: True si l'authentification a réussi, False sinon
        """
        creds = None
        try:
            oauth_token_json_str = os.environ.get('GOOGLE_OAUTH_TOKEN_JSON')
            if oauth_token_json_str:
                try:
                    logger.info("Utilisation des credentials OAuth2 depuis la variable d'environnement GOOGLE_OAUTH_TOKEN_JSON")
                    token_data = json.loads(oauth_token_json_str)
                    # Note: Utiliser google.oauth2.credentials.Credentials ici
                    creds = UserCredentials.from_authorized_user_info(token_data, SCOPES)
                except json.JSONDecodeError:
                    logger.error("Erreur lors du décodage JSON de la variable d'environnement GOOGLE_OAUTH_TOKEN_JSON")
                    return False
                except Exception as e:
                    logger.error(f"Erreur lors de l'utilisation des credentials depuis GOOGLE_OAUTH_TOKEN_JSON: {str(e)}")
                    return False
            elif os.path.exists(TOKEN_FILE):
                logger.warning(f"Variable d'environnement GOOGLE_OAUTH_TOKEN_JSON non trouvée. Tentative d'utilisation du fichier local: {TOKEN_FILE}")
                with open(TOKEN_FILE, 'r') as f:
                    token_data = json.load(f)
                creds = UserCredentials.from_authorized_user_info(token_data, SCOPES)
            else:
                logger.error(f"Credentials OAuth2 non trouvés (ni variable d'environnement GOOGLE_OAUTH_TOKEN_JSON, ni fichier {TOKEN_FILE})")
                return False

            # Créer le client gspread
            self.client = gspread.authorize(creds)
            
            # Ouvrir le Google Sheet
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            
            logger.info(f"Authentification OAuth2 réussie pour le Google Sheet: {self.spreadsheet.title}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'authentification OAuth2: {str(e)}")
            return False
    
    def get_or_create_worksheet(self, model_name: str) -> Optional[gspread.Worksheet]:
        """
        Récupère ou crée une feuille de calcul pour un modèle donné.
        
        Args:
            model_name (str): Nom du modèle
            
        Returns:
            gspread.Worksheet: Feuille de calcul pour le modèle, ou None en cas d'erreur
        """
        if not self.spreadsheet:
            logger.error("Spreadsheet non initialisé. Veuillez vous authentifier d'abord.")
            return None
        
        try:
            # Essayer de récupérer la feuille existante
            worksheet = self.spreadsheet.worksheet(model_name)
            logger.info(f"Feuille existante trouvée pour {model_name}")
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            # Créer une nouvelle feuille si elle n'existe pas
            try:
                worksheet = self.spreadsheet.add_worksheet(title=model_name, rows=1000, cols=20)
                
                # Configurer les en-têtes
                headers = [
                    "Date", "Réseau Social", "Lien Photo 1", "Lien Photo 2", 
                    "Lien Vidéo", "Lien Reel Performant"
                ]
                worksheet.update('A1:F1', [headers])
                
                # Formater les en-têtes (gras, centré, etc.)
                worksheet.format('A1:F1', {
                    'textFormat': {'bold': True},
                    'horizontalAlignment': 'CENTER',
                    'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
                })
                
                # Ajuster la largeur des colonnes
                worksheet.columns_auto_resize(0, 6)
                
                logger.info(f"Nouvelle feuille créée pour {model_name}")
                return worksheet
            except Exception as e:
                logger.error(f"Erreur lors de la création de la feuille pour {model_name}: {str(e)}")
                return None
    
    def add_daily_content(self, model_name: str, content: Dict[str, Any]) -> bool:
        """
        Ajoute le contenu quotidien pour un modèle dans sa feuille de calcul.
        
        Args:
            model_name (str): Nom du modèle
            content (dict): Contenu à ajouter (date, liens photos, vidéo, réel)
            
        Returns:
            bool: True si l'ajout a réussi, False sinon
        """
        worksheet = self.get_or_create_worksheet(model_name)
        if not worksheet:
            return False
        
        try:
            # Préparer les données à ajouter
            date = content.get("date", datetime.datetime.now().strftime("%Y-%m-%d"))
            
            # Déterminer le réseau social pour chaque contenu
            photo_sources = []
            for link in content.get("photo_links", []):
                if not link: continue # Ignorer les liens vides
                if "instagram.com" in link:
                    photo_sources.append("Instagram")
                elif "twitter.com" in link or "x.com" in link:
                    photo_sources.append("Twitter")
                elif "threads.net" in link:
                    photo_sources.append("Threads")
                elif "test.com" in link: # Gérer les liens de test
                     photo_sources.append("Test")
                else:
                    photo_sources.append("Autre")
            
            video_source = ""
            video_link = content.get("video_link")
            if video_link:
                if "twitter.com" in video_link or "x.com" in video_link:
                    video_source = "Twitter"
                elif "threads.net" in video_link:
                    video_source = "Threads"
                elif "test.com" in video_link:
                    video_source = "Test"
            
            reel_source = ""
            reel_link = content.get("reel_link")
            if reel_link:
                 if "instagram.com" in reel_link:
                    reel_source = "Instagram"
                 elif "test.com" in reel_link:
                    reel_source = "Test"
            
            # Déterminer le réseau social principal pour cette entrée
            all_sources = photo_sources + ([video_source] if video_source else []) + ([reel_source] if reel_source else [])
            if all_sources:
                # Prioriser les vrais réseaux sur 'Test' ou 'Autre'
                real_sources = [s for s in all_sources if s not in ["Test", "Autre"]]
                if real_sources:
                     main_source = max(set(real_sources), key=real_sources.count)
                elif "Test" in all_sources:
                     main_source = "Test"
                else:
                     main_source = "Autre"
            else:
                main_source = "N/A"
            
            # Préparer la ligne à ajouter
            row_data = [
                date,
                main_source,
                content.get("photo_links", [""])[0] if len(content.get("photo_links", [])) > 0 else "",
                content.get("photo_links", ["", ""])[1] if len(content.get("photo_links", [])) > 1 else "",
                video_link or "",
                reel_link or ""
            ]
            
            # Trouver la première ligne vide
            values = worksheet.get_all_values()
            next_row = len(values) + 1
            
            # Ajouter la ligne
            worksheet.update(f'A{next_row}:F{next_row}', [row_data])
            
            # Formater les liens en bleu et soulignés
            for col_index, link in enumerate(row_data[2:], start=2): # Colonnes C à F (index 2 à 5)
                if link:  # Si la cellule contient un lien
                    cell = gspread.utils.rowcol_to_a1(next_row, col_index + 1)  # +1 car gspread est 1-indexé
                    worksheet.format(cell, {
                        'textFormat': {'foregroundColor': {'red': 0.0, 'green': 0.0, 'blue': 0.8}},
                        # 'textDecoration': {'underline': True} # Décoration retirée pour lisibilité
                    })
            
            logger.info(f"Contenu quotidien ajouté pour {model_name}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout du contenu pour {model_name}: {str(e)}")
            logger.error(traceback.format_exc()) # Ajouter traceback pour plus de détails
            return False
    
    def update_all_models(self, content_data: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
        """
        Met à jour le Google Sheet pour tous les modèles.
        
        Args:
            content_data (dict): Dictionnaire contenant le contenu pour chaque modèle
            
        Returns:
            dict: Résultats de la mise à jour pour chaque modèle
        """
        results = {}
        
        for model_name, content in content_data.items():
            success = self.add_daily_content(model_name, content)
            results[model_name] = success
            
            # Ajouter un délai pour éviter les limitations de l'API
            time.sleep(1.5) # Augmenter légèrement le délai
        
        return results

# Les fonctions suivantes ne sont plus nécessaires si les credentials sont gérés par variables d'environnement
# def create_service_account_file(credentials_json: str) -> bool:
#     """
#     Crée le fichier de compte de service à partir d'une chaîne JSON.
#     (Déprécié en faveur des variables d'environnement)
#     """
#     # ... (code original)

# def create_oauth_token_file(token_json: str) -> bool:
#     """
#     Crée le fichier de token OAuth2 à partir d'une chaîne JSON.
#     (Déprécié en faveur des variables d'environnement)
#     """
#     # ... (code original)

def generate_oauth_url() -> str:
    """
    Génère l'URL pour l'authentification OAuth2 (pour configuration initiale).
    Nécessite un fichier client_secrets.json local (NE PAS COMMITTER).
    
    Returns:
        str: URL d'authentification OAuth2, ou message d'erreur
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        
        CLIENT_SECRETS_FILE = 'client_secrets.json'
        
        if not os.path.exists(CLIENT_SECRETS_FILE):
             logger.error(f"Fichier {CLIENT_SECRETS_FILE} non trouvé. Nécessaire pour générer l'URL OAuth.")
             # Essayer de lire depuis l'environnement si disponible
             client_secrets_json_str = os.environ.get('CLIENT_SECRETS_JSON')
             if client_secrets_json_str:
                 logger.info("Utilisation de CLIENT_SECRETS_JSON depuis l'environnement pour générer l'URL")
                 client_config = json.loads(client_secrets_json_str)
                 flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
             else:
                 return "Erreur: Fichier client_secrets.json non trouvé et variable d'environnement CLIENT_SECRETS_JSON non définie."
        else:
            # Créer le flow OAuth2 depuis le fichier local
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE,
                scopes=SCOPES
            )
        
        # Utiliser la redirection localhost pour obtenir le code plus facilement
        flow.redirect_uri = 'http://localhost:8080/' 
        
        # Générer l'URL d'authentification
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            prompt='consent', # Forcer l'affichage du consentement pour obtenir un refresh_token
            include_granted_scopes='true'
        )
        
        logger.info("URL d'authentification OAuth générée. Veuillez l'ouvrir dans votre navigateur.")
        logger.info("Après autorisation, vous serez redirigé vers localhost. Copiez l'URL complète de redirection.")
        return auth_url
    except Exception as e:
        logger.error(f"Erreur lors de la génération de l'URL OAuth: {str(e)}")
        return f"Erreur: {str(e)}"

def exchange_auth_code_for_token(auth_code: str) -> Optional[str]:
    """
    Échange le code d'autorisation OAuth contre un token (incluant refresh_token).
    Nécessite un fichier client_secrets.json local ou la variable d'env CLIENT_SECRETS_JSON.

    Args:
        auth_code (str): Le code d'autorisation obtenu après redirection.

    Returns:
        str: Le contenu JSON du token, prêt à être mis dans la variable d'env GOOGLE_OAUTH_TOKEN_JSON.
             None en cas d'erreur.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        
        CLIENT_SECRETS_FILE = 'client_secrets.json'
        
        if not os.path.exists(CLIENT_SECRETS_FILE):
             logger.error(f"Fichier {CLIENT_SECRETS_FILE} non trouvé. Nécessaire pour échanger le code.")
             client_secrets_json_str = os.environ.get('CLIENT_SECRETS_JSON')
             if client_secrets_json_str:
                 logger.info("Utilisation de CLIENT_SECRETS_JSON depuis l'environnement pour échanger le code")
                 client_config = json.loads(client_secrets_json_str)
                 flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
             else:
                 logger.error("Fichier client_secrets.json non trouvé et variable d'environnement CLIENT_SECRETS_JSON non définie.")
                 return None
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        
        flow.redirect_uri = 'http://localhost:8080/' # Doit correspondre à la génération de l'URL

        # Échanger le code contre des credentials
        flow.fetch_token(code=auth_code)
        
        # Obtenir les credentials (qui incluent le refresh_token si access_type='offline' et prompt='consent')
        credentials = flow.credentials
        
        # Convertir les credentials en JSON
        token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        token_json = json.dumps(token_data)
        
        logger.info("Token OAuth obtenu avec succès (incluant refresh_token si possible).")
        logger.info("Copiez le JSON suivant dans la variable d'environnement GOOGLE_OAUTH_TOKEN_JSON de Railway:")
        print("---- COPIEZ CE JSON ----")
        print(token_json)
        print("-------------------------")
        
        # Sauvegarder aussi localement pour référence (optionnel)
        # with open(TOKEN_FILE, 'w') as token_f:
        #     token_f.write(token_json)
        # logger.info(f"Token également sauvegardé localement dans {TOKEN_FILE}")
            
        return token_json

    except Exception as e:
        logger.error(f"Erreur lors de l'échange du code d'autorisation: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def main():
    """Fonction principale pour tester l'intégration Google Sheet."""
    # ID du Google Sheet (à remplacer par l'ID réel si différent)
    spreadsheet_id = "1KhTXJu9BlIfi8D99C_lvxdC77D2X9pOy5JGiKmoLt-k"
    
    # Créer l'intégration
    integration = GoogleSheetIntegration(spreadsheet_id)
    
    # --- Choisir la méthode d'authentification --- 
    # 1. Compte de service (recommandé pour les serveurs comme Railway)
    authenticated = integration.authenticate()
    
    # 2. OAuth2 (si compte de service non possible, nécessite configuration initiale)
    # authenticated = integration.authenticate_with_oauth()
    # ---------------------------------------------
    
    if not authenticated:
        logger.error("Échec de l'authentification. Vérifiez les credentials (variables d'environnement ou fichiers locaux).")
        
        # Aide pour configurer OAuth2 si nécessaire
        logger.info("Si vous utilisez OAuth2 et que c'est la première fois, générez l'URL d'authentification.")
        # print("URL OAuth: ", generate_oauth_url())
        # auth_code = input("Entrez le code d'autorisation obtenu après redirection: ")
        # exchange_auth_code_for_token(auth_code)
        return
    
    # Exemple de contenu pour chaque modèle (pour test)
    content_data = {
        "Talia": {
            "date": "2025-04-28",
            "photo_links": [
                "https://test.com/p/ABC123/",
                "https://test.com/talia_srz/status/123456789"
            ],
            "video_link": "https://test.com/talia_srz/status/987654321",
            "reel_link": "https://test.com/reel/DEF456/"
        },
        "Léa": {
            "date": "2025-04-28",
            "photo_links": [
                "https://test.com/p/GHI789/",
                "https://test.com/@lea_vlmtt/post/123456"
            ],
            "video_link": None,
            "reel_link": "https://test.com/reel/JKL012/"
        },
        "Lizz": {
            "date": "2025-04-28",
            "photo_links": [
                "https://test.com/p/MNO345/"
            ],
            "video_link": "https://test.com/@lizz.rmo/post/345678",
            "reel_link": None
        }
    }
    
    # Mettre à jour le Google Sheet pour tous les modèles
    logger.info("Test de mise à jour du Google Sheet avec des données d'exemple...")
    results = integration.update_all_models(content_data)
    
    # Afficher les résultats
    for model_name, success in results.items():
        status = "réussie" if success else "échouée"
        print(f"Mise à jour (test) pour {model_name}: {status}")

if __name__ == "__main__":
    # Décommenter les lignes suivantes pour générer l'URL OAuth ou échanger un code
    # print("URL OAuth: ", generate_oauth_url())
    # auth_code = input("Entrez le code d'autorisation obtenu après redirection (ou l'URL complète): ")
    # # Extraire le code de l'URL si nécessaire (ex: ?code=4/0Af...&scope=...)
    # if 'code=' in auth_code:
    #     import urllib.parse
    #     parsed_url = urllib.parse.urlparse(auth_code)
    #     query_params = urllib.parse.parse_qs(parsed_url.query)
    #     auth_code = query_params.get('code', [None])[0]
    # if auth_code:
    #     exchange_auth_code_for_token(auth_code)
    # else:
    #     print("Code d'autorisation non trouvé.")
    
    # Exécuter le test principal par défaut
    main()

