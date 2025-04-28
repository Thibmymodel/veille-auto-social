#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module pour la sélection de contenu pertinent basé sur l'engagement et les préférences.
"""

import sqlite3
import logging
import datetime
import json
import traceback
from typing import List, Dict, Any, Tuple

# Configuration du logging
logging.basicConfig(
    level=logging.DEBUG,  # Changé de INFO à DEBUG pour plus de détails
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("content_selector.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("content_selector")

# Constantes pour les seuils de sélection (abaissés pour le diagnostic)
MIN_ENGAGEMENT_SCORE = 0.01  # Seuil minimum de score d'engagement
MIN_VIEWS = 1              # Seuil minimum de vues pour les vidéos/reels
PERFORMANCE_THRESHOLD = 0.01 # Seuil de performance par rapport à la moyenne (ex: 1.5 = 50% au-dessus)
RECENCY_DAYS_LIMIT = 14    # Limite en jours pour considérer un contenu comme récent

# Chemin de la base de données
DB_PATH = "content_database.db"

class ContentSelector:
    """Classe pour gérer la base de données et la sélection de contenu."""
    
    def __init__(self, db_path=DB_PATH):
        """Initialise la connexion à la base de données et crée les tables si nécessaire."""
        try:
            self.conn = sqlite3.connect(db_path)
            self.cursor = self.conn.cursor()
            self._create_tables()
            logger.info(f"Connecté à la base de données: {db_path}")
        except sqlite3.Error as e:
            logger.error(f"Erreur de connexion à la base de données: {e}")
            raise

    def _create_tables(self):
        """Crée les tables nécessaires dans la base de données si elles n'existent pas."""
        try:
            # Table pour stocker le contenu extrait
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                link TEXT UNIQUE NOT NULL,
                content_type TEXT NOT NULL, -- 'photo', 'video', 'reel', 'tweet', 'thread', 'tiktok'
                platform TEXT NOT NULL, -- 'instagram', 'twitter', 'threads', 'tiktok'
                extraction_date TEXT NOT NULL,
                performance_metric REAL, -- Vues, Likes, etc.
                engagement_score REAL, -- Score calculé
                is_speaking INTEGER, -- 0 ou 1
                has_captions INTEGER, -- 0 ou 1
                has_music INTEGER, -- 0 ou 1
                metadata TEXT, -- JSON pour infos supplémentaires (hashtags, sons, etc.)
                selected INTEGER DEFAULT 0, -- 0: non sélectionné, 1: sélectionné
                selection_date TEXT
            )
            ''')
            
            # Table pour stocker les préférences des modèles
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_preferences (
                model_name TEXT PRIMARY KEY,
                prefers_speaking INTEGER DEFAULT 0,
                prefers_captions INTEGER DEFAULT 0,
                prefers_music INTEGER DEFAULT 0
            )
            ''')
            
            # Table pour stocker les statistiques des modèles (ex: vues moyennes)
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_stats (
                model_name TEXT PRIMARY KEY,
                avg_reel_views REAL DEFAULT 0
            )
            ''')
            
            # Table pour stocker les tendances
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                content_type TEXT NOT NULL, -- 'hashtag', 'sound'
                item TEXT NOT NULL,
                rank INTEGER,
                extraction_date TEXT NOT NULL
            )
            ''')
            
            # Ajouter les modèles aux tables de préférences et statistiques s'ils n'existent pas
            # (Utilisé principalement pour l'initialisation)
            from veille_automatisee import MODELS # Import local pour éviter dépendance circulaire
            for model in MODELS:
                self.cursor.execute("INSERT OR IGNORE INTO model_preferences (model_name) VALUES (?)", (model['name'],))
                self.cursor.execute("INSERT OR IGNORE INTO model_stats (model_name) VALUES (?)", (model['name'],))
            
            self.conn.commit()
            logger.debug("Tables de la base de données vérifiées/créées.")
        except sqlite3.Error as e:
            logger.error(f"Erreur lors de la création des tables: {e}")
            self.conn.rollback()
            raise
        except Exception as e:
            logger.error(f"Erreur inattendue lors de l'initialisation des tables: {e}")
            logger.error(traceback.format_exc())
            self.conn.rollback()
            raise

    def store_content(self, content_item: Dict[str, Any]) -> bool:
        """
        Stocke un élément de contenu dans la base de données.
        
        Args:
            content_item (dict): Dictionnaire contenant les informations du contenu.
                                 Doit inclure 'model_name', 'link', 'content_type', 'platform',
                                 'extraction_date', et optionnellement d'autres champs.
                                 
        Returns:
            bool: True si l'insertion a réussi, False sinon.
        """
        required_keys = ['model_name', 'link', 'content_type', 'platform', 'extraction_date']
        if not all(key in content_item for key in required_keys):
            logger.warning(f"Données de contenu incomplètes, ignoré: {content_item.get('link', 'Lien manquant')}")
            return False
            
        link = content_item['link']
        logger.debug(f"Tentative de stockage du contenu: {link}")
        
        try:
            # Vérifier si le contenu existe déjà
            self.cursor.execute("SELECT id FROM content WHERE link = ?", (link,))
            existing = self.cursor.fetchone()
            
            if existing:
                logger.debug(f"Contenu déjà existant, mise à jour: {link}")
                # Mettre à jour les métriques si nécessaire (exemple)
                update_query = "UPDATE content SET extraction_date = ?, performance_metric = ?, engagement_score = ? WHERE link = ?"
                params = (
                    content_item.get('extraction_date', datetime.datetime.now().isoformat()),
                    content_item.get('performance_metric'),
                    content_item.get('engagement_score'),
                    link
                )
                self.cursor.execute(update_query, params)
            else:
                logger.debug(f"Nouveau contenu, insertion: {link}")
                # Insérer le nouveau contenu
                insert_query = '''
                INSERT INTO content (
                    model_name, link, content_type, platform, extraction_date, 
                    performance_metric, engagement_score, is_speaking, has_captions, 
                    has_music, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
                params = (
                    content_item['model_name'],
                    link,
                    content_item['content_type'],
                    content_item['platform'],
                    content_item.get('extraction_date', datetime.datetime.now().isoformat()),
                    content_item.get('performance_metric'),
                    content_item.get('engagement_score'),
                    1 if content_item.get('is_speaking') else 0,
                    1 if content_item.get('has_captions') else 0,
                    1 if content_item.get('has_music') else 0,
                    json.dumps(content_item.get('metadata', {}))
                )
                self.cursor.execute(insert_query, params)
                
            self.conn.commit()
            logger.debug(f"Contenu stocké/mis à jour avec succès: {link}")
            return True
            
        except sqlite3.IntegrityError:
            logger.warning(f"Erreur d'intégrité (probablement lien dupliqué non détecté initialement): {link}")
            self.conn.rollback()
            return False
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors du stockage du contenu {link}: {e}")
            self.conn.rollback()
            return False
        except Exception as e:
            logger.error(f"Erreur inattendue lors du stockage du contenu {link}: {e}")
            logger.error(traceback.format_exc())
            self.conn.rollback()
            return False

    def store_trend(self, trend_item: Dict[str, Any]) -> bool:
        """
        Stocke un élément de tendance dans la base de données.
        
        Args:
            trend_item (dict): Dictionnaire contenant les informations de la tendance.
                               Doit inclure 'platform', 'content_type', 'item', 'extraction_date'.
                               
        Returns:
            bool: True si l'insertion a réussi, False sinon.
        """
        required_keys = ['platform', 'content_type', 'item', 'extraction_date']
        if not all(key in trend_item for key in required_keys):
            logger.warning(f"Données de tendance incomplètes, ignoré: {trend_item}")
            return False
            
        item = trend_item['item']
        platform = trend_item['platform']
        content_type = trend_item['content_type']
        extraction_date = trend_item.get('extraction_date', datetime.datetime.now().isoformat())
        rank = trend_item.get('rank')
        
        logger.debug(f"Tentative de stockage de la tendance: {platform} - {content_type} - {item}")
        
        try:
            # Vérifier si la tendance existe déjà pour cette date (simpliste, pourrait être amélioré)
            self.cursor.execute("SELECT id FROM trends WHERE platform = ? AND content_type = ? AND item = ? AND date(extraction_date) = date(?) ", 
                              (platform, content_type, item, extraction_date))
            existing = self.cursor.fetchone()
            
            if existing:
                logger.debug(f"Tendance déjà existante pour aujourd'hui: {item}")
                # Optionnel: Mettre à jour le rang si nécessaire
                if rank is not None:
                    self.cursor.execute("UPDATE trends SET rank = ? WHERE id = ?", (rank, existing[0]))
            else:
                logger.debug(f"Nouvelle tendance, insertion: {item}")
                insert_query = '''
                INSERT INTO trends (platform, content_type, item, rank, extraction_date)
                VALUES (?, ?, ?, ?, ?)
                '''
                params = (platform, content_type, item, rank, extraction_date)
                self.cursor.execute(insert_query, params)
                
            self.conn.commit()
            logger.debug(f"Tendance stockée/mise à jour avec succès: {item}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors du stockage de la tendance {item}: {e}")
            self.conn.rollback()
            return False
        except Exception as e:
            logger.error(f"Erreur inattendue lors du stockage de la tendance {item}: {e}")
            logger.error(traceback.format_exc())
            self.conn.rollback()
            return False

    def _get_model_preferences(self, model_name: str) -> Dict[str, bool]:
        """Récupère les préférences d'un modèle depuis la base de données."""
        try:
            self.cursor.execute("SELECT prefers_speaking, prefers_captions, prefers_music FROM model_preferences WHERE model_name = ?", (model_name,))
            result = self.cursor.fetchone()
            if result:
                return {
                    "prefers_speaking": bool(result[0]),
                    "prefers_captions": bool(result[1]),
                    "prefers_music": bool(result[2])
                }
            else:
                logger.warning(f"Préférences non trouvées pour le modèle: {model_name}")
                return {}
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors de la récupération des préférences pour {model_name}: {e}")
            return {}

    def _get_model_stats(self, model_name: str) -> Dict[str, float]:
        """Récupère les statistiques d'un modèle depuis la base de données."""
        try:
            self.cursor.execute("SELECT avg_reel_views FROM model_stats WHERE model_name = ?", (model_name,))
            result = self.cursor.fetchone()
            if result:
                return {"avg_reel_views": result[0] if result[0] is not None else 0}
            else:
                logger.warning(f"Statistiques non trouvées pour le modèle: {model_name}")
                return {"avg_reel_views": 0}
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors de la récupération des statistiques pour {model_name}: {e}")
            return {"avg_reel_views": 0}

    def select_content_for_model(self, model_name: str) -> List[Dict[str, Any]]:
        """
        Sélectionne le contenu pertinent pour un modèle spécifique.
        
        Args:
            model_name (str): Nom du modèle.
            
        Returns:
            list: Liste des dictionnaires de contenu sélectionné.
        """
        logger.info(f"Sélection du contenu pour le modèle: {model_name}")
        
        preferences = self._get_model_preferences(model_name)
        stats = self._get_model_stats(model_name)
        avg_reel_views = stats.get("avg_reel_views", 0)
        
        selected_content = []
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=RECENCY_DAYS_LIMIT)).isoformat()
        
        try:
            # Récupérer le contenu non sélectionné et récent pour ce modèle
            query = '''
            SELECT id, link, content_type, platform, performance_metric, engagement_score, 
                   is_speaking, has_captions, has_music, metadata
            FROM content 
            WHERE model_name = ? AND selected = 0 AND extraction_date >= ?
            '''
            self.cursor.execute(query, (model_name, cutoff_date))
            potential_content = self.cursor.fetchall()
            
            logger.debug(f"{len(potential_content)} éléments de contenu potentiels trouvés pour {model_name}")
            
            for item in potential_content:
                content_id, link, content_type, platform, performance, score, is_speaking, has_captions, has_music, metadata_json = item
                metadata = json.loads(metadata_json) if metadata_json else {}
                
                logger.debug(f"Évaluation du contenu: {link} (Type: {content_type}, Score: {score}, Perf: {performance})")
                
                # 1. Vérifier le score d'engagement minimum
                if score is None or score < MIN_ENGAGEMENT_SCORE:
                    logger.debug(f"  Rejeté: Score d'engagement ({score}) < {MIN_ENGAGEMENT_SCORE}")
                    continue
                    
                # 2. Vérifier les vues minimales pour vidéos/reels
                if content_type in ['video', 'reel'] and (performance is None or performance < MIN_VIEWS):
                    logger.debug(f"  Rejeté: Vues ({performance}) < {MIN_VIEWS}")
                    continue
                    
                # 3. Vérifier la performance relative pour les reels (si applicable)
                if content_type == 'reel' and avg_reel_views > 0 and performance is not None:
                    relative_performance = performance / avg_reel_views
                    if relative_performance < PERFORMANCE_THRESHOLD:
                        logger.debug(f"  Rejeté: Performance relative du reel ({relative_performance:.2f}) < {PERFORMANCE_THRESHOLD}")
                        continue
                    else:
                        logger.debug(f"  Performance relative du reel: {relative_performance:.2f} (Seuil: {PERFORMANCE_THRESHOLD})")
                
                # 4. Vérifier la correspondance avec les préférences du modèle
                preference_match = True
                if preferences:
                    # Si le modèle préfère parler et que le contenu ne parle pas
                    if preferences.get('prefers_speaking') and not is_speaking:
                        preference_match = False
                        logger.debug("  Rejeté: Le modèle préfère parler, ce contenu ne parle pas.")
                    # Si le modèle préfère les sous-titres et que le contenu n'en a pas
                    elif preferences.get('prefers_captions') and not has_captions:
                        preference_match = False
                        logger.debug("  Rejeté: Le modèle préfère les sous-titres, ce contenu n'en a pas.")
                    # Si le modèle préfère la musique et que le contenu n'en a pas
                    elif preferences.get('prefers_music') and not has_music:
                        preference_match = False
                        logger.debug("  Rejeté: Le modèle préfère la musique, ce contenu n'en a pas.")
                    # Si le modèle NE préfère PAS parler et que le contenu parle
                    elif not preferences.get('prefers_speaking') and is_speaking:
                        preference_match = False
                        logger.debug("  Rejeté: Le modèle ne préfère pas parler, ce contenu parle.")
                    # Si le modèle NE préfère PAS la musique et que le contenu en a
                    elif not preferences.get('prefers_music') and has_music:
                        preference_match = False
                        logger.debug("  Rejeté: Le modèle ne préfère pas la musique, ce contenu en a.")
                        
                if not preference_match:
                    continue
                    
                # Si toutes les conditions sont remplies, sélectionner le contenu
                logger.info(f"Contenu sélectionné pour {model_name}: {link}")
                selected_content.append({
                    "id": content_id,
                    "link": link,
                    "content_type": content_type,
                    "platform": platform,
                    "performance_metric": performance,
                    "engagement_score": score,
                    "is_speaking": bool(is_speaking),
                    "has_captions": bool(has_captions),
                    "has_music": bool(has_music),
                    "metadata": metadata
                })
                
                # Marquer comme sélectionné dans la base de données
                try:
                    self.cursor.execute("UPDATE content SET selected = 1, selection_date = ? WHERE id = ?", 
                                      (datetime.datetime.now().isoformat(), content_id))
                    self.conn.commit()
                    logger.debug(f"Contenu marqué comme sélectionné dans la DB: {link}")
                except sqlite3.Error as e:
                    logger.error(f"Erreur SQLite lors du marquage du contenu {link} comme sélectionné: {e}")
                    self.conn.rollback()
            
            logger.info(f"{len(selected_content)} éléments sélectionnés pour {model_name}")
            return selected_content
            
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors de la sélection du contenu pour {model_name}: {e}")
            return []
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la sélection du contenu pour {model_name}: {e}")
            logger.error(traceback.format_exc())
            return []

    def close(self):
        """Ferme la connexion à la base de données."""
        if self.conn:
            self.conn.close()
            logger.info("Connexion à la base de données fermée.")

# Fonctions utilitaires pour interagir avec la classe ContentSelector

def process_scraped_content(scraped_data: Dict[str, Any], model_names: List[str]) -> int:
    """
    Traite les données scrapées et les stocke dans la base de données.
    
    Args:
        scraped_data (dict): Données brutes du scraper (doit contenir 'platform', 'username', 'posts').
        model_names (list): Liste des noms de modèles associés à ces données.
        
    Returns:
        int: Nombre d'éléments de contenu stockés avec succès.
    """
    if not scraped_data or 'posts' not in scraped_data or not scraped_data['posts']:
        logger.debug("Aucune donnée scrapée à traiter.")
        return 0
        
    platform = scraped_data.get('platform', 'inconnu')
    username = scraped_data.get('username', 'inconnu')
    posts = scraped_data['posts']
    count = 0
    
    logger.debug(f"Traitement de {len(posts)} posts scrapés de {platform} pour {username} (Modèles: {', '.join(model_names)})")
    
    selector = None
    try:
        selector = ContentSelector()
        for post in posts:
            # Adapter les données du post au format attendu par store_content
            content_item = {
                "link": post.get('link'),
                "content_type": post.get('type', 'inconnu'),
                "platform": platform,
                "extraction_date": post.get('timestamp', datetime.datetime.now().isoformat()),
                "performance_metric": post.get('views') or post.get('likes'), # Priorité aux vues
                "engagement_score": post.get('engagement_score'), # Assumer que le scraper le calcule
                "is_speaking": post.get('is_speaking'),
                "has_captions": post.get('has_captions'),
                "has_music": post.get('has_music'),
                "metadata": post.get('metadata', {})
            }
            
            # Associer à tous les modèles concernés
            for model_name in model_names:
                content_item["model_name"] = model_name
                if selector.store_content(content_item):
                    count += 1
                    # On ne compte qu'une fois même si stocké pour plusieurs modèles
                    # (car store_content gère l'unicité par lien)
                    break # Sortir de la boucle des modèles une fois stocké
                    
    except Exception as e:
        logger.error(f"Erreur lors du traitement des données scrapées pour {username}: {e}")
        logger.error(traceback.format_exc())
    finally:
        if selector:
            selector.close()
            
    logger.debug(f"{count} éléments de contenu traités et potentiellement stockés pour {username}")
    return count

def process_trending_content(trending_data: Dict[str, Any]) -> int:
    """
    Traite les données de tendances et les stocke dans la base de données.
    
    Args:
        trending_data (dict): Données brutes des tendances (doit contenir 'platform', 'content_type', 'items').
        
    Returns:
        int: Nombre d'éléments de tendance stockés avec succès.
    """
    if not trending_data or 'items' not in trending_data or not trending_data['items']:
        logger.debug("Aucune donnée de tendance à traiter.")
        return 0
        
    platform = trending_data.get('platform', 'inconnu')
    content_type = trending_data.get('content_type', 'inconnu')
    items = trending_data['items']
    count = 0
    now = datetime.datetime.now().isoformat()
    
    logger.debug(f"Traitement de {len(items)} tendances de type '{content_type}' pour {platform}")
    
    selector = None
    try:
        selector = ContentSelector()
        for i, item_data in enumerate(items):
            # Adapter les données au format attendu par store_trend
            trend_item = {
                "platform": platform,
                "content_type": content_type,
                "item": item_data.get('name') if isinstance(item_data, dict) else item_data, # Nom du hashtag/son
                "rank": item_data.get('rank', i + 1) if isinstance(item_data, dict) else i + 1,
                "extraction_date": now
            }
            if selector.store_trend(trend_item):
                count += 1
                
    except Exception as e:
        logger.error(f"Erreur lors du traitement des données de tendance pour {platform}: {e}")
        logger.error(traceback.format_exc())
    finally:
        if selector:
            selector.close()
            
    logger.debug(f"{count} éléments de tendance traités et potentiellement stockés pour {platform}")
    return count

def select_content_for_all_models(model_names: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Sélectionne le contenu pertinent pour une liste de modèles.
    
    Args:
        model_names (list): Liste des noms de modèles.
        
    Returns:
        dict: Dictionnaire avec les noms de modèles comme clés et les listes de contenu sélectionné comme valeurs.
    """
    all_selected_content = {}
    selector = None
    try:
        selector = ContentSelector()
        for model_name in model_names:
            selected = selector.select_content_for_model(model_name)
            all_selected_content[model_name] = selected
    except Exception as e:
        logger.error(f"Erreur lors de la sélection du contenu pour tous les modèles: {e}")
        logger.error(traceback.format_exc())
    finally:
        if selector:
            selector.close()
            
    return all_selected_content

# Exemple d'utilisation (peut être exécuté pour tester le module)
if __name__ == '__main__':
    logger.info("Test du module ContentSelector...")
    
    # Initialiser
    try:
        selector = ContentSelector()
        logger.info("Initialisation réussie.")
        
        # Exemple de stockage
        test_item = {
            "model_name": "TestModel",
            "link": "https://example.com/testpost123",
            "content_type": "photo",
            "platform": "instagram",
            "extraction_date": datetime.datetime.now().isoformat(),
            "performance_metric": 1500,
            "engagement_score": 5.5,
            "is_speaking": False,
            "has_captions": True,
            "has_music": True,
            "metadata": {"tags": ["test", "example"]}
        }
        if selector.store_content(test_item):
            logger.info("Stockage de l'élément de test réussi.")
        else:
            logger.warning("Échec du stockage de l'élément de test.")
            
        # Exemple de sélection (nécessite des données et préférences configurées)
        # selected = selector.select_content_for_model("Talia")
        # logger.info(f"Contenu sélectionné pour Talia: {len(selected)} éléments")
        
        # Fermer la connexion
        selector.close()
        
    except Exception as e:
        logger.error(f"Erreur lors du test du module ContentSelector: {e}")
        logger.error(traceback.format_exc())

