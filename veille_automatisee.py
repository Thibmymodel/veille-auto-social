#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script principal pour la veille automatisée des créatrices OnlyFans.
Ce script intègre tous les modules développés et exécute le processus complet
de scraping, sélection et mise à jour du Google Sheet.
"""

import os
import sys
import json
import time
import logging
import datetime
import argparse
import sqlite3
import schedule
import traceback
import random
from typing import Dict, List, Any

# Importer les modules développés
from instagram_scraper import InstagramScraper, extract_instagram_content
from twitter_scraper import TwitterScraper, extract_twitter_content
from threads_scraper import ThreadsScraper, extract_threads_content
from tiktok_scraper import TikTokScraper, extract_tiktok_content, get_tiktok_trending_hashtags, get_tiktok_trending_sounds
from content_selector import ContentSelector, select_content_for_all_models, process_scraped_content, process_trending_content
from google_sheet_integration import GoogleSheetIntegration

# Configuration du logging
logging.basicConfig(
    level=logging.DEBUG,  # Changé de INFO à DEBUG pour plus de détails
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("veille_automatisee.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("veille_automatisee")

# Définition des modèles
MODELS = [
    {
        "name": "Talia",
        "instagram": "talia_srz",
        "twitter": "talia_srz",
        "threads": "talia_srz",
        "tiktok": None,
        "style": "Coquin soft, caption + musique uniquement",
        "avg_views": 4000,
        "preferences": {
            "prefers_speaking": False,
            "prefers_captions": True,
            "prefers_music": True
        },
        "similar_accounts": {
            "instagram": ["annatomex", "jadetora_", "gabigarciareels", "ludivine_dstr", "alexxa.hln"]
        }
    },
    {
        "name": "Léa",
        "instagram": "lea_vlmtt",
        "twitter": "lea_vlmt",
        "threads": "lea_vlmtt",
        "tiktok": None,
        "style": "Coquin souriant, caption + musique uniquement",
        "avg_views": 3000,
        "preferences": {
            "prefers_speaking": False,
            "prefers_captions": True,
            "prefers_music": True
        },
        "similar_accounts": {
            "instagram": ["vanessaparadiise", "miadacostaaa", "lolasoliia", "itsaria_06", "leeaacrl", "lestia_fyw", "nayia_roy", "nayiaroyprivate"]
        }
    },
    {
        "name": "Lizz",
        "instagram": "lizzrmo",
        "twitter": None,
        "threads": "lizz.rmo",
        "tiktok": None,
        "style": "Coquin parlé, facecam avec sous-titres texte",
        "avg_views": 3500,
        "preferences": {
            "prefers_speaking": True,
            "prefers_captions": True,
            "prefers_music": False
        },
        "similar_accounts": {
            "instagram": ["laly_chauvette", "itsjustdidine", "iamlupix", "solenerlt2", "laeyanah", "maylisnbd", "mya_bellony", "kathelyn_klf", "emmaxvibing", "mimibloom_", "linamycrush"]
        }
    }
]

# ID du Google Sheet
SPREADSHEET_ID = "1KhTXJu9BlIfi8D99C_lvxdC77D2X9pOy5JGiKmoLt-k"

# Configuration des quotas
DAILY_QUOTA = {
    "instagram": 50,
    "twitter": 50,
    "threads": 30,
    "tiktok": 30
}

# Chemin de la base de données
DB_PATH = "content_database.db"

def check_dependencies():
    """Vérifie que toutes les dépendances sont installées."""
    try:
        import selenium
        import bs4
        import gspread
        import google.oauth2
        import fake_useragent
        import schedule
        import requests
        import webdriver_manager
        logger.info("Toutes les dépendances sont installées.")
        return True
    except ImportError as e:
        logger.error(f"Dépendance manquante: {str(e)}")
        return False

def install_dependencies():
    """Installe les dépendances nécessaires."""
    import subprocess
    
    dependencies = [
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
    
    logger.info("Installation des dépendances...")
    
    for dep in dependencies:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
            logger.info(f"Dépendance installée: {dep}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur lors de l'installation de {dep}: {str(e)}")
            return False
    
    logger.info("Toutes les dépendances ont été installées.")
    return True

def init_database():
    """Initialise la base de données SQLite."""
    try:
        # Créer une instance du sélecteur de contenu pour initialiser la structure de la base de données
        selector = ContentSelector()
        selector.close()
        
        logger.info("Base de données initialisée avec succès.")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la base de données: {str(e)}")
        return False

def setup_environment():
    """Configure l'environnement d'exécution."""
    # Vérifier et installer les dépendances si nécessaire
    if not check_dependencies():
        if not install_dependencies():
            logger.error("Impossible d'installer toutes les dépendances. Arrêt du programme.")
            return False
    
    # Initialiser la base de données SQLite
    if not init_database():
        logger.error("Impossible d'initialiser la base de données. Arrêt du programme.")
        return False
    
    # Installer ChromeDriver automatiquement
    try:
        import chromedriver_autoinstaller
        chromedriver_autoinstaller.install()
        logger.info("ChromeDriver installé automatiquement.")
    except Exception as e:
        logger.warning(f"Impossible d'installer ChromeDriver automatiquement: {str(e)}")
        logger.warning("Vous devrez peut-être installer ChromeDriver manuellement.")
    
    logger.info("Environnement configuré avec succès.")
    return True

def update_model_preferences():
    """Met à jour les préférences des modèles dans la base de données."""
    try:
        selector = ContentSelector()
        
        for model in MODELS:
            model_name = model["name"]
            preferences = model.get("preferences", {})
            
            # Construire les préférences
            prefers_speaking = preferences.get("prefers_speaking", False)
            prefers_captions = preferences.get("prefers_captions", False)
            prefers_music = preferences.get("prefers_music", False)
            
            # Mettre à jour les préférences dans la base de données
            selector.cursor.execute('''
            UPDATE model_preferences SET 
            prefers_speaking = ?,
            prefers_captions = ?,
            prefers_music = ?
            WHERE model_name = ?
            ''', (
                1 if prefers_speaking else 0,
                1 if prefers_captions else 0,
                1 if prefers_music else 0,
                model_name
            ))
        
        selector.conn.commit()
        selector.close()
        
        logger.info("Préférences des modèles mises à jour avec succès.")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour des préférences des modèles: {str(e)}")
        return False

def update_model_stats():
    """Met à jour les statistiques des modèles dans la base de données."""
    try:
        selector = ContentSelector()
        
        for model in MODELS:
            model_name = model["name"]
            avg_views = model.get("avg_views", 0)
            
            # Mettre à jour les statistiques dans la base de données
            selector.cursor.execute('''
            UPDATE model_stats SET 
            avg_reel_views = ?
            WHERE model_name = ?
            ''', (avg_views, model_name))
        
        selector.conn.commit()
        selector.close()
        
        logger.info("Statistiques des modèles mises à jour avec succès.")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour des statistiques des modèles: {str(e)}")
        return False

def generate_test_data():
    """Génère des données de test et les insère dans la base de données."""
    logger.info("Génération des données de test...")
    selector = ContentSelector()
    now = datetime.datetime.now().isoformat()
    
    test_content = []
    for model in MODELS:
        model_name = model["name"]
        
        # Générer 2 photos
        for i in range(2):
            test_content.append({
                "model_name": model_name,
                "link": f"https://test.com/{model_name.lower()}/photo/{random.randint(1000, 9999)}",
                "content_type": "photo",
                "platform": random.choice(["instagram", "twitter", "threads"]),
                "extraction_date": now,
                "performance_metric": random.uniform(500, 5000),
                "engagement_score": random.uniform(1, 10),
                "is_speaking": False,
                "has_captions": random.choice([True, False]),
                "has_music": random.choice([True, False]),
                "metadata": {"test_data": True, "photo_index": i + 1}
            })
            
        # Générer 1 vidéo
        test_content.append({
            "model_name": model_name,
            "link": f"https://test.com/{model_name.lower()}/video/{random.randint(1000, 9999)}",
            "content_type": "video",
            "platform": random.choice(["twitter", "threads", "tiktok"]),
            "extraction_date": now,
            "performance_metric": random.uniform(1000, 10000),
            "engagement_score": random.uniform(1, 10),
            "is_speaking": model["preferences"].get("prefers_speaking", False),
            "has_captions": model["preferences"].get("prefers_captions", False),
            "has_music": model["preferences"].get("prefers_music", False),
            "metadata": {"test_data": True}
        })
        
        # Générer 1 reel
        test_content.append({
            "model_name": model_name,
            "link": f"https://test.com/{model_name.lower()}/reel/{random.randint(1000, 9999)}",
            "content_type": "reel",
            "platform": "instagram",
            "extraction_date": now,
            "performance_metric": random.uniform(2000, 20000),
            "engagement_score": random.uniform(1, 10),
            "is_speaking": model["preferences"].get("prefers_speaking", False),
            "has_captions": model["preferences"].get("prefers_captions", False),
            "has_music": model["preferences"].get("prefers_music", False),
            "metadata": {"test_data": True}
        })

    # Insérer les données de test dans la base de données
    count = 0
    for content_item in test_content:
        if selector.store_content(content_item):
            count += 1
            
    selector.close()
    logger.info(f"{count} éléments de test générés et stockés dans la base de données.")
    return count > 0

def run_instagram_scraping(model, days_limit=14, max_posts=20):
    """
    Exécute le scraping Instagram pour un modèle donné.
    
    Args:
        model (dict): Informations du modèle
        days_limit (int): Limite en jours pour le contenu récent
        max_posts (int): Nombre maximum de posts à extraire
        
    Returns:
        dict: Résultats du scraping
    """
    if "instagram" not in model or not model["instagram"]:
        logger.warning(f"Pas de compte Instagram défini pour {model['name']}")
        return None
    
    username = model["instagram"]
    logger.info(f"Scraping Instagram pour {model['name']} (@{username})...")
    
    try:
        # Extraire le contenu Instagram du compte principal
        content = extract_instagram_content(username, days_limit, max_posts)
        
        if not content:
            logger.warning(f"Aucun contenu Instagram trouvé pour {model['name']} (@{username})")
            content = []
        
        # Log du nombre de posts bruts collectés
        logger.debug(f"Instagram: {len(content)} posts bruts collectés pour {model['name']} (@{username})")
        
        # Préparer les résultats
        results = {
            "platform": "instagram",
            "username": username,
            "posts": content
        }
        
        # Traiter le contenu extrait
        model_names = [model["name"]]
        count = process_scraped_content(results, model_names)
        
        logger.info(f"Scraping Instagram terminé pour {model['name']} (@{username}): {count} éléments stockés")
        
        # Scraper les comptes similaires
        similar_accounts = model.get("similar_accounts", {}).get("instagram", [])
        
        if similar_accounts:
            logger.info(f"Scraping des comptes Instagram similaires pour {model['name']}...")
            
            for similar_account in similar_accounts:
                try:
                    logger.info(f"Scraping Instagram pour compte similaire: @{similar_account}")
                    
                    # Extraire le contenu Instagram du compte similaire
                    similar_content = extract_instagram_content(similar_account, days_limit, max_posts)
                    
                    if not similar_content:
                        logger.warning(f"Aucun contenu Instagram trouvé pour le compte similaire @{similar_account}")
                        continue
                    
                    # Log du nombre de posts bruts collectés pour le compte similaire
                    logger.debug(f"Instagram (similaire): {len(similar_content)} posts bruts collectés pour @{similar_account}")
                    
                    # Préparer les résultats
                    similar_results = {
                        "platform": "instagram",
                        "username": similar_account,
                        "posts": similar_content
                    }
                    
                    # Traiter le contenu extrait
                    similar_count = process_scraped_content(similar_results, model_names)
                    
                    logger.info(f"Scraping Instagram terminé pour compte similaire @{similar_account}: {similar_count} éléments stockés")
                    
                    # Ajouter le contenu au résultat global
                    if "posts" in results:
                        results["posts"].extend(similar_content)
                    else:
                        results["posts"] = similar_content
                        
                except Exception as e:
                    logger.error(f"Erreur lors du scraping Instagram pour compte similaire @{similar_account}: {str(e)}")
                    logger.error(traceback.format_exc())
        
        return results
    except Exception as e:
        logger.error(f"Erreur lors du scraping Instagram pour {model['name']}: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def run_twitter_scraping(model, days_limit=14, max_posts=20):
    """
    Exécute le scraping Twitter pour un modèle donné.
    
    Args:
        model (dict): Informations du modèle
        days_limit (int): Limite en jours pour le contenu récent
        max_posts (int): Nombre maximum de posts à extraire
        
    Returns:
        dict: Résultats du scraping
    """
    if "twitter" not in model or not model["twitter"]:
        logger.warning(f"Pas de compte Twitter défini pour {model['name']}")
        return None
    
    username = model["twitter"]
    logger.info(f"Scraping Twitter pour {model['name']} (@{username})...")
    
    try:
        # Extraire le contenu Twitter
        content = extract_twitter_content(username, days_limit, max_posts)
        
        if not content:
            logger.warning(f"Aucun contenu Twitter trouvé pour {model['name']} (@{username})")
            content = [] # Initialiser comme liste vide si aucun contenu
        
        # Log du nombre de posts bruts collectés
        logger.debug(f"Twitter: {len(content)} posts bruts collectés pour {model['name']} (@{username})")
        
        # Préparer les résultats
        results = {
            "platform": "twitter",
            "username": username,
            "posts": content
        }
        
        # Traiter le contenu extrait
        model_names = [model["name"]]
        count = process_scraped_content(results, model_names)
        
        logger.info(f"Scraping Twitter terminé pour {model['name']} (@{username}): {count} éléments stockés")
        
        # Scraper les comptes similaires (si applicable)
        # Note: La logique pour les comptes similaires Twitter n'est pas implémentée ici
        
        return results
    except Exception as e:
        logger.error(f"Erreur lors du scraping Twitter pour {model['name']}: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def run_threads_scraping(model, days_limit=14, max_posts=20):
    """
    Exécute le scraping Threads pour un modèle donné.
    
    Args:
        model (dict): Informations du modèle
        days_limit (int): Limite en jours pour le contenu récent
        max_posts (int): Nombre maximum de posts à extraire
        
    Returns:
        dict: Résultats du scraping
    """
    if "threads" not in model or not model["threads"]:
        logger.warning(f"Pas de compte Threads défini pour {model['name']}")
        return None
    
    username = model["threads"]
    logger.info(f"Scraping Threads pour {model['name']} (@{username})...")
    
    try:
        # Extraire le contenu Threads
        content = extract_threads_content(username, days_limit, max_posts)
        
        if not content:
            logger.warning(f"Aucun contenu Threads trouvé pour {model['name']} (@{username})")
            content = [] # Initialiser comme liste vide si aucun contenu
        
        # Log du nombre de posts bruts collectés
        logger.debug(f"Threads: {len(content)} posts bruts collectés pour {model['name']} (@{username})")
        
        # Préparer les résultats
        results = {
            "platform": "threads",
            "username": username,
            "posts": content
        }
        
        # Traiter le contenu extrait
        model_names = [model["name"]]
        count = process_scraped_content(results, model_names)
        
        logger.info(f"Scraping Threads terminé pour {model['name']} (@{username}): {count} éléments stockés")
        
        # Scraper les comptes similaires (si applicable)
        # Note: La logique pour les comptes similaires Threads n'est pas implémentée ici
        
        return results
    except Exception as e:
        logger.error(f"Erreur lors du scraping Threads pour {model['name']}: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def run_tiktok_scraping(model, days_limit=14, max_posts=20):
    """
    Exécute le scraping TikTok pour un modèle donné.
    
    Args:
        model (dict): Informations du modèle
        days_limit (int): Limite en jours pour le contenu récent
        max_posts (int): Nombre maximum de posts à extraire
        
    Returns:
        dict: Résultats du scraping
    """
    if "tiktok" not in model or not model["tiktok"]:
        logger.warning(f"Pas de compte TikTok défini pour {model['name']}")
        return None
    
    username = model["tiktok"]
    logger.info(f"Scraping TikTok pour {model['name']} (@{username})...")
    
    try:
        # Extraire le contenu TikTok
        content = extract_tiktok_content(username, days_limit, max_posts)
        
        if not content:
            logger.warning(f"Aucun contenu TikTok trouvé pour {model['name']} (@{username})")
            content = [] # Initialiser comme liste vide si aucun contenu
        
        # Log du nombre de posts bruts collectés
        logger.debug(f"TikTok: {len(content)} posts bruts collectés pour {model['name']} (@{username})")
        
        # Préparer les résultats
        results = {
            "platform": "tiktok",
            "username": username,
            "posts": content
        }
        
        # Traiter le contenu extrait
        model_names = [model["name"]]
        count = process_scraped_content(results, model_names)
        
        logger.info(f"Scraping TikTok terminé pour {model['name']} (@{username}): {count} éléments stockés")
        
        # Scraper les comptes similaires (si applicable)
        # Note: La logique pour les comptes similaires TikTok n'est pas implémentée ici
        
        return results
    except Exception as e:
        logger.error(f"Erreur lors du scraping TikTok pour {model['name']}: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def run_trending_scraping():
    """Exécute le scraping des tendances."""
    logger.info("Scraping des tendances...")
    
    try:
        # TikTok
        tiktok_hashtags = get_tiktok_trending_hashtags()
        if tiktok_hashtags:
            process_trending_content({
                "platform": "tiktok",
                "content_type": "hashtag",
                "items": tiktok_hashtags
            })
        
        tiktok_sounds = get_tiktok_trending_sounds()
        if tiktok_sounds:
            process_trending_content({
                "platform": "tiktok",
                "content_type": "sound",
                "items": tiktok_sounds
            })
        
        # Ajouter d'autres plateformes si nécessaire
        
        logger.info("Scraping des tendances terminé.")
    except Exception as e:
        logger.error(f"Erreur lors du scraping des tendances: {str(e)}")
        logger.error(traceback.format_exc())

def run_veille_automatisee(test_mode=False):
    """Exécute le processus complet de veille automatisée."""
    logger.info("Démarrage de la veille automatisée...")
    
    # Configurer l'environnement
    if not setup_environment():
        return
    
    # Mettre à jour les préférences et statistiques des modèles
    update_model_preferences()
    update_model_stats()
    
    # Si mode test, générer des données de test
    if test_mode:
        logger.info("Mode test activé. Génération de données fictives.")
        if not generate_test_data():
            logger.error("Échec de la génération des données de test.")
            # Continuer quand même pour tester la sélection et l'intégration GSheet
    else:
        logger.info("Mode normal activé. Scraping des données réelles.")
        # Exécuter le scraping pour chaque modèle
        for model in MODELS:
            run_instagram_scraping(model)
            run_twitter_scraping(model)
            run_threads_scraping(model)
            run_tiktok_scraping(model)
        
        # Exécuter le scraping des tendances
        run_trending_scraping()
    
    # Sélectionner le contenu pour tous les modèles
    model_names = [model["name"] for model in MODELS]
    selected_content = select_content_for_all_models(model_names)
    
    # Mettre à jour le Google Sheet
    try:
        gsheet = GoogleSheetIntegration(SPREADSHEET_ID)
        if gsheet.authenticate():
            for model_name, content in selected_content.items():
                gsheet.update_sheet_for_model(model_name, content)
        else:
            logger.error("Échec de l'authentification Google Sheet. Vérifiez le fichier service_account.json.")
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du Google Sheet: {str(e)}")
        logger.error(traceback.format_exc())
    
    logger.info("Veille automatisée terminée avec succès.")

def main():
    """Fonction principale du script."""
    parser = argparse.ArgumentParser(description="Système de veille automatisée pour créatrices OnlyFans.")
    parser.add_argument("--test", action="store_true", help="Exécute le script en mode test avec des données fictives.")
    parser.add_argument("--scheduled", action="store_true", help="Exécute le script en mode planifié (une fois par jour).")
    args = parser.parse_args()
    
    if args.scheduled:
        logger.info("Mode planifié activé. Exécution quotidienne à 02:00.")
        # Planifier l'exécution quotidienne
        schedule.every().day.at("02:00").do(run_veille_automatisee, test_mode=args.test)
        
        # Exécuter une première fois immédiatement
        run_veille_automatisee(test_mode=args.test)
        
        # Boucle infinie pour maintenir le planning actif
        while True:
            schedule.run_pending()
            time.sleep(60) # Vérifier toutes les minutes
    else:
        # Exécution unique
        run_veille_automatisee(test_mode=args.test)

if __name__ == "__main__":
    main()
