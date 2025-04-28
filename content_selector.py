#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module d'algorithme de sélection de contenu pour la veille automatisée des créatrices OnlyFans.
Ce module contient les fonctions nécessaires pour sélectionner le contenu le plus pertinent
selon les critères spécifiés pour chaque modèle.
"""

import os
import re
import json
import time
import random
import sqlite3
import logging
import datetime
from collections import defaultdict

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

# Configuration de la base de données SQLite
DB_PATH = "content_database.db"

# Seuils de sélection (ABAISSÉS POUR DIAGNOSTIC)
MIN_ENGAGEMENT_SCORE = 0.01  # Valeur originale probablement plus élevée
MIN_VIEWS = 1  # Valeur originale probablement plus élevée
PERFORMANCE_THRESHOLD = 0.01  # Valeur originale probablement plus élevée

class ContentSelector:
    """Classe pour la sélection de contenu selon les critères spécifiés."""
    
    def __init__(self):
        """Initialise le sélecteur de contenu."""
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        self._ensure_database_structure()
        logger.info(f"ContentSelector initialisé avec seuils bas: MIN_ENGAGEMENT_SCORE={MIN_ENGAGEMENT_SCORE}, MIN_VIEWS={MIN_VIEWS}, PERFORMANCE_THRESHOLD={PERFORMANCE_THRESHOLD}")
    
    def _ensure_database_structure(self):
        """Assure que la structure de la base de données est correcte."""
        # Créer la table extracted_links si elle n'existe pas
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS extracted_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            link TEXT NOT NULL,
            content_type TEXT NOT NULL,
            platform TEXT NOT NULL,
            extraction_date TEXT NOT NULL,
            performance_metric REAL DEFAULT 0,
            engagement_score REAL DEFAULT 0,
            is_speaking INTEGER DEFAULT 0,
            has_captions INTEGER DEFAULT 0,
            has_music INTEGER DEFAULT 0,
            is_used INTEGER DEFAULT 0,
            metadata TEXT,
            UNIQUE(model_name, link)
        )
        ''')
        
        # Créer la table model_stats si elle n'existe pas
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS model_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT UNIQUE NOT NULL,
            avg_reel_views REAL DEFAULT 0,
            avg_video_views REAL DEFAULT 0,
            avg_photo_likes REAL DEFAULT 0,
            avg_engagement_rate REAL DEFAULT 0,
            last_updated TEXT NOT NULL
        )
        ''')
        
        # Créer la table model_preferences si elle n'existe pas
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS model_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT UNIQUE NOT NULL,
            prefers_speaking INTEGER DEFAULT 0,
            prefers_captions INTEGER DEFAULT 0,
            prefers_music INTEGER DEFAULT 0,
            preferred_platforms TEXT DEFAULT 'instagram,twitter,threads,tiktok',
            content_quota TEXT DEFAULT '{"photos": 2, "videos": 1, "reels": 1}'
        )
        ''')
        
        # Créer la table trending_content si elle n'existe pas
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS trending_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            content_type TEXT NOT NULL,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            rank INTEGER NOT NULL,
            extraction_date TEXT NOT NULL,
            metadata TEXT,
            UNIQUE(platform, content_type, name, extraction_date)
        )
        ''')
        
        self.conn.commit()
        
        # Insérer les préférences par défaut pour les modèles si elles n'existent pas
        default_preferences = [
            ("Talia", 0, 0, 1, "instagram,twitter,threads,tiktok", '{"photos": 2, "videos": 1, "reels": 1}'),
            ("Léa", 0, 0, 1, "instagram,twitter,threads,tiktok", '{"photos": 2, "videos": 1, "reels": 1}'),
            ("Lizz", 1, 1, 0, "instagram,twitter,threads,tiktok", '{"photos": 2, "videos": 1, "reels": 1}')
        ]
        
        for pref in default_preferences:
            self.cursor.execute('''
            INSERT OR IGNORE INTO model_preferences 
            (model_name, prefers_speaking, prefers_captions, prefers_music, preferred_platforms, content_quota)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', pref)
        
        # Insérer les statistiques par défaut pour les modèles si elles n'existent pas
        default_stats = [
            ("Talia", 4000, 3000, 500, 3.5, datetime.datetime.now().isoformat()),
            ("Léa", 3000, 2000, 400, 2.8, datetime.datetime.now().isoformat()),
            ("Lizz", 3500, 2500, 450, 3.2, datetime.datetime.now().isoformat())
        ]
        
        for stat in default_stats:
            self.cursor.execute('''
            INSERT OR IGNORE INTO model_stats 
            (model_name, avg_reel_views, avg_video_views, avg_photo_likes, avg_engagement_rate, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', stat)
        
        self.conn.commit()
    
    def close(self):
        """Ferme la connexion à la base de données."""
        if self.conn:
            self.conn.close()
    
    def is_content_already_used(self, model_name, link):
        """Vérifie si un contenu a déjà été utilisé pour un modèle donné."""
        self.cursor.execute(
            "SELECT is_used FROM extracted_links WHERE model_name = ? AND link = ?",
            (model_name, link)
        )
        result = self.cursor.fetchone()
        
        if result:
            return bool(result[0])
        return False
    
    def mark_content_as_used(self, model_name, link):
        """Marque un contenu comme utilisé dans la base de données."""
        try:
            self.cursor.execute(
                "UPDATE extracted_links SET is_used = 1 WHERE model_name = ? AND link = ?",
                (model_name, link)
            )
            self.conn.commit()
            logger.info(f"Contenu marqué comme utilisé pour {model_name}: {link}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors du marquage du contenu comme utilisé: {str(e)}")
            return False
    
    def store_content(self, content_data):
        """
        Stocke le contenu extrait dans la base de données.
        
        Args:
            content_data (dict): Données du contenu à stocker
                {
                    "model_name": str,
                    "link": str,
                    "content_type": str (photo, video, reel),
                    "platform": str (instagram, twitter, threads, tiktok),
                    "extraction_date": str (format ISO),
                    "performance_metric": float,
                    "engagement_score": float,
                    "is_speaking": bool,
                    "has_captions": bool,
                    "has_music": bool,
                    "metadata": dict (données supplémentaires en JSON)
                }
                
        Returns:
            bool: True si le stockage a réussi, False sinon
        """
        try:
            # Convertir les booléens en entiers pour SQLite
            is_speaking = 1 if content_data.get("is_speaking", False) else 0
            has_captions = 1 if content_data.get("has_captions", False) else 0
            has_music = 1 if content_data.get("has_music", False) else 0
            
            # Convertir les métadonnées en JSON
            metadata = json.dumps(content_data.get("metadata", {}))
            
            # Insérer ou mettre à jour le contenu
            self.cursor.execute('''
            INSERT OR REPLACE INTO extracted_links 
            (model_name, link, content_type, platform, extraction_date, performance_metric, 
             engagement_score, is_speaking, has_captions, has_music, is_used, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            ''', (
                content_data["model_name"],
                content_data["link"],
                content_data["content_type"],
                content_data["platform"],
                content_data.get("extraction_date", datetime.datetime.now().isoformat()),
                content_data.get("performance_metric", 0),
                content_data.get("engagement_score", 0),
                is_speaking,
                has_captions,
                has_music,
                metadata
            ))
            
            self.conn.commit()
            logger.info(f"Contenu stocké pour {content_data['model_name']}: {content_data['link']} (type: {content_data['content_type']}, plateforme: {content_data['platform']})")
            return True
        except Exception as e:
            logger.error(f"Erreur lors du stockage du contenu: {str(e)}")
            return False
    
    def store_trending_content(self, trending_data):
        """
        Stocke les contenus tendance dans la base de données.
        
        Args:
            trending_data (dict): Données des contenus tendance
                {
                    "platform": str (instagram, twitter, threads, tiktok),
                    "content_type": str (hashtag, sound, challenge, etc.),
                    "items": [
                        {
                            "name": str,
                            "url": str,
                            "rank": int,
                            "metadata": dict (données supplémentaires)
                        },
                        ...
                    ]
                }
                
        Returns:
            bool: True si le stockage a réussi, False sinon
        """
        try:
            extraction_date = datetime.datetime.now().isoformat()
            platform = trending_data["platform"]
            content_type = trending_data["content_type"]
            
            for item in trending_data["items"]:
                metadata = json.dumps(item.get("metadata", {}))
                
                self.cursor.execute('''
                INSERT OR REPLACE INTO trending_content 
                (platform, content_type, name, url, rank, extraction_date, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    platform,
                    content_type,
                    item["name"],
                    item["url"],
                    item["rank"],
                    extraction_date,
                    metadata
                ))
            
            self.conn.commit()
            logger.info(f"Contenus tendance stockés pour {platform} ({content_type}): {len(trending_data['items'])} éléments")
            return True
        except Exception as e:
            logger.error(f"Erreur lors du stockage des contenus tendance: {str(e)}")
            return False
    
    def update_model_stats(self, model_name, stats_data):
        """
        Met à jour les statistiques d'un modèle.
        
        Args:
            model_name (str): Nom du modèle
            stats_data (dict): Données des statistiques
                {
                    "avg_reel_views": float,
                    "avg_video_views": float,
                    "avg_photo_likes": float,
                    "avg_engagement_rate": float
                }
                
        Returns:
            bool: True si la mise à jour a réussi, False sinon
        """
        try:
            self.cursor.execute('''
            UPDATE model_stats SET 
            avg_reel_views = ?,
            avg_video_views = ?,
            avg_photo_likes = ?,
            avg_engagement_rate = ?,
            last_updated = ?
            WHERE model_name = ?
            ''', (
                stats_data.get("avg_reel_views", 0),
                stats_data.get("avg_video_views", 0),
                stats_data.get("avg_photo_likes", 0),
                stats_data.get("avg_engagement_rate", 0),
                datetime.datetime.now().isoformat(),
                model_name
            ))
            
            self.conn.commit()
            logger.info(f"Statistiques mises à jour pour {model_name}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des statistiques: {str(e)}")
            return False
    
    def get_model_preferences(self, model_name):
        """
        Récupère les préférences d'un modèle.
        
        Args:
            model_name (str): Nom du modèle
            
        Returns:
            dict: Préférences du modèle
        """
        self.cursor.execute(
            """
            SELECT prefers_speaking, prefers_captions, prefers_music, 
                   preferred_platforms, content_quota
            FROM model_preferences 
            WHERE model_name = ?
            """,
            (model_name,)
        )
        
        result = self.cursor.fetchone()
        
        if result:
            return {
                "prefers_speaking": bool(result[0]),
                "prefers_captions": bool(result[1]),
                "prefers_music": bool(result[2]),
                "preferred_platforms": result[3].split(","),
                "content_quota": json.loads(result[4])
            }
        else:
            # Valeurs par défaut
            return {
                "prefers_speaking": False,
                "prefers_captions": False,
                "prefers_music": False,
                "preferred_platforms": ["instagram", "twitter", "threads", "tiktok"],
                "content_quota": {"photos": 2, "videos": 1, "reels": 1}
            }
    
    def get_recent_photos(self, model_name, days_threshold=7, count=2, platforms=None):
        """
        Récupère les photos récentes pour un modèle donné.
        
        Args:
            model_name (str): Nom du modèle
            days_threshold (int): Nombre de jours maximum pour considérer une photo comme récente
            count (int): Nombre de photos à récupérer
            platforms (list): Liste des plateformes à considérer
            
        Returns:
            list: Liste des liens de photos récentes
        """
        # Calculer la date limite
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days_threshold)).isoformat()
        
        # Vérifier le nombre total de photos disponibles pour ce modèle (pour diagnostic)
        self.cursor.execute(
            "SELECT COUNT(*) FROM extracted_links WHERE model_name = ? AND content_type = 'photo'",
            (model_name,)
        )
        total_photos = self.cursor.fetchone()[0]
        logger.debug(f"Total des photos disponibles pour {model_name}: {total_photos}")
        
        # Construire la requête en fonction des plateformes
        query = """
            SELECT link, platform, engagement_score FROM extracted_links 
            WHERE model_name = ? 
            AND content_type = 'photo' 
            AND extraction_date > ? 
            AND is_used = 0
        """
        
        params = [model_name, cutoff_date]
        
        if platforms:
            placeholders = ','.join(['?'] * len(platforms))
            query += f" AND platform IN ({placeholders})"
            params.extend(platforms)
        
        query += " ORDER BY engagement_score DESC, extraction_date DESC LIMIT ?"
        params.append(count)
        
        # Récupérer les photos récentes non utilisées
        self.cursor.execute(query, params)
        
        results = self.cursor.fetchall()
        photo_links = [{"link": row[0], "platform": row[1], "engagement_score": row[2]} for row in results]
        
        logger.info(f"Récupéré {len(photo_links)} photos récentes pour {model_name}")
        
        # Si nous n'avons pas assez de photos récentes, compléter avec des photos plus anciennes
        if len(photo_links) < count:
            remaining = count - len(photo_links)
            logger.debug(f"Besoin de {remaining} photos supplémentaires pour {model_name}, recherche de photos plus anciennes")
            
            # Construire la requête pour les photos plus anciennes
            old_query = """
                SELECT link, platform, engagement_score FROM extracted_links 
                WHERE model_name = ? 
                AND content_type = 'photo' 
                AND is_used = 0
            """
            
            old_params = [model_name]
            
            # Exclure les photos déjà sélectionnées
            if photo_links:
                excluded_links = [photo["link"] for photo in photo_links]
                placeholders = ','.join(['?'] * len(excluded_links))
                old_query += f" AND link NOT IN ({placeholders})"
                old_params.extend(excluded_links)
            
            if platforms:
                placeholders = ','.join(['?'] * len(platforms))
                old_query += f" AND platform IN ({placeholders})"
                old_params.extend(platforms)
            
            old_query += " ORDER BY engagement_score DESC, extraction_date DESC LIMIT ?"
            old_params.append(remaining)
            
            self.cursor.execute(old_query, old_params)
            old_results = self.cursor.fetchall()
            
            for row in old_results:
                photo_links.append({"link": row[0], "platform": row[1], "engagement_score": row[2]})
            
            logger.info(f"Ajouté {len(old_results)} photos plus anciennes pour {model_name}")
        
        # Afficher les scores d'engagement pour diagnostic
        for photo in photo_links:
            logger.debug(f"Photo sélectionnée pour {model_name}: {photo['link']} (score: {photo['engagement_score']})")
        
        return photo_links
    
    def get_best_video(self, model_name, days_threshold=14, platforms=None):
        """
        Récupère la meilleure vidéo pour un modèle donné.
        
        Args:
            model_name (str): Nom du modèle
            days_threshold (int): Nombre de jours maximum pour considérer une vidéo comme récente
            platforms (list): Liste des plateformes à considérer
            
        Returns:
            dict: Informations sur la meilleure vidéo
        """
        # Calculer la date limite
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days_threshold)).isoformat()
        
        # Vérifier le nombre total de vidéos disponibles pour ce modèle (pour diagnostic)
        self.cursor.execute(
            "SELECT COUNT(*) FROM extracted_links WHERE model_name = ? AND content_type = 'video'",
            (model_name,)
        )
        total_videos = self.cursor.fetchone()[0]
        logger.debug(f"Total des vidéos disponibles pour {model_name}: {total_videos}")
        
        # Récupérer les statistiques du modèle
        self.cursor.execute(
            "SELECT avg_video_views FROM model_stats WHERE model_name = ?",
            (model_name,)
        )
        result = self.cursor.fetchone()
        avg_views = result[0] if result else 1000  # Valeur par défaut si aucune statistique
        
        # Calculer le seuil minimum de vues (abaissé pour diagnostic)
        min_views = MIN_VIEWS  # Utilise la constante globale abaissée
        logger.debug(f"Seuil minimum de vues pour {model_name}: {min_views} (moyenne: {avg_views})")
        
        # Construire la requête en fonction des plateformes
        query = """
            SELECT link, platform, performance_metric, engagement_score, is_speaking, has_captions, has_music, metadata 
            FROM extracted_links 
            WHERE model_name = ? 
            AND content_type = 'video' 
            AND extraction_date > ? 
            AND performance_metric >= ?
            AND is_used = 0
        """
        
        params = [model_name, cutoff_date, min_views]
        
        if platforms:
            placeholders = ','.join(['?'] * len(platforms))
            query += f" AND platform IN ({placeholders})"
            params.extend(platforms)
        
        query += " ORDER BY performance_metric DESC, engagement_score DESC LIMIT 1"
        
        self.cursor.execute(query, params)
        result = self.cursor.fetchone()
        
        # Si aucune vidéo ne dépasse le seuil, prendre la plus performante
        if not result:
            logger.debug(f"Aucune vidéo ne dépasse le seuil pour {model_name}, recherche de la plus performante")
            relaxed_query = """
                SELECT link, platform, performance_metric, engagement_score, is_speaking, has_captions, has_music, metadata 
                FROM extracted_links 
                WHERE model_name = ? 
                AND content_type = 'video' 
                AND extraction_date > ? 
                AND is_used = 0
            """
            
            relaxed_params = [model_name, cutoff_date]
            
            if platforms:
                placeholders = ','.join(['?'] * len(platforms))
                relaxed_query += f" AND platform IN ({placeholders})"
                relaxed_params.extend(platforms)
            
            relaxed_query += " ORDER BY performance_metric DESC, engagement_score DESC LIMIT 1"
            
            self.cursor.execute(relaxed_query, relaxed_params)
            result = self.cursor.fetchone()
        
        # Si toujours aucun résultat, essayer avec une date plus ancienne
        if not result:
            logger.debug(f"Aucune vidéo récente pour {model_name}, recherche de vidéos plus anciennes")
            oldest_query = """
                SELECT link, platform, performance_metric, engagement_score, is_speaking, has_captions, has_music, metadata 
                FROM extracted_links 
                WHERE model_name = ? 
                AND content_type = 'video' 
                AND is_used = 0
            """
            
            oldest_params = [model_name]
            
            if platforms:
                placeholders = ','.join(['?'] * len(platforms))
                oldest_query += f" AND platform IN ({placeholders})"
                oldest_params.extend(platforms)
            
            oldest_query += " ORDER BY performance_metric DESC, engagement_score DESC LIMIT 1"
            
            self.cursor.execute(oldest_query, oldest_params)
            result = self.cursor.fetchone()
        
        if result:
            metadata = json.loads(result[7]) if result[7] else {}
            video_info = {
                "link": result[0],
                "platform": result[1],
                "performance_metric": result[2],
                "engagement_score": result[3],
                "is_speaking": bool(result[4]),
                "has_captions": bool(result[5]),
                "has_music": bool(result[6]),
                "metadata": metadata
            }
            logger.info(f"Vidéo performante trouvée pour {model_name}: {result[0]} ({result[1]}, vues: {result[2]})")
            return video_info
        else:
            logger.warning(f"Aucune vidéo trouvée pour {model_name}")
            return None
    
    def get_best_reel(self, model_name, days_threshold=14, platforms=None):
        """
        Récupère le meilleur réel pour un modèle donné.
        
        Args:
            model_name (str): Nom du modèle
            days_threshold (int): Nombre de jours maximum pour considérer un réel comme récent
            platforms (list): Liste des plateformes à considérer
            
        Returns:
            dict: Informations sur le meilleur réel
        """
        # Calculer la date limite
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days_threshold)).isoformat()
        
        # Vérifier le nombre total de réels disponibles pour ce modèle (pour diagnostic)
        self.cursor.execute(
            "SELECT COUNT(*) FROM extracted_links WHERE model_name = ? AND content_type = 'reel'",
            (model_name,)
        )
        total_reels = self.cursor.fetchone()[0]
        logger.debug(f"Total des réels disponibles pour {model_name}: {total_reels}")
        
        # Récupérer les statistiques du modèle
        self.cursor.execute(
            "SELECT avg_reel_views FROM model_stats WHERE model_name = ?",
            (model_name,)
        )
        result = self.cursor.fetchone()
        avg_views = result[0] if result else 3000  # Valeur par défaut si aucune statistique
        
        # Calculer le seuil minimum de vues (abaissé pour diagnostic)
        performance_threshold = PERFORMANCE_THRESHOLD  # Utilise la constante globale abaissée
        min_views = avg_views * performance_threshold
        logger.debug(f"Seuil minimum de vues pour réels de {model_name}: {min_views} (moyenne: {avg_views}, seuil: {performance_threshold})")
        
        # Construire la requête en fonction des plateformes
        query = """
            SELECT link, platform, performance_metric, engagement_score, is_speaking, has_captions, has_music, metadata 
            FROM extracted_links 
            WHERE model_name = ? 
            AND content_type = 'reel' 
            AND extraction_date > ? 
            AND performance_metric >= ?
            AND is_used = 0
        """
        
        params = [model_name, cutoff_date, min_views]
        
        if platforms:
            placeholders = ','.join(['?'] * len(platforms))
            query += f" AND platform IN ({placeholders})"
            params.extend(platforms)
        
        query += " ORDER BY performance_metric DESC, engagement_score DESC LIMIT 1"
        
        self.cursor.execute(query, params)
        result = self.cursor.fetchone()
        
        # Si aucun réel ne dépasse le seuil, prendre le plus performant
        if not result:
            logger.debug(f"Aucun réel ne dépasse le seuil pour {model_name}, recherche du plus performant")
            relaxed_query = """
                SELECT link, platform, performance_metric, engagement_score, is_speaking, has_captions, has_music, metadata 
                FROM extracted_links 
                WHERE model_name = ? 
                AND content_type = 'reel' 
                AND extraction_date > ? 
                AND is_used = 0
            """
            
            relaxed_params = [model_name, cutoff_date]
            
            if platforms:
                placeholders = ','.join(['?'] * len(platforms))
                relaxed_query += f" AND platform IN ({placeholders})"
                relaxed_params.extend(platforms)
            
            relaxed_query += " ORDER BY performance_metric DESC, engagement_score DESC LIMIT 1"
            
            self.cursor.execute(relaxed_query, relaxed_params)
            result = self.cursor.fetchone()
        
        # Si toujours aucun résultat, essayer avec une date plus ancienne
        if not result:
            logger.debug(f"Aucun réel récent pour {model_name}, recherche de réels plus anciens")
            oldest_query = """
                SELECT link, platform, performance_metric, engagement_score, is_speaking, has_captions, has_music, metadata 
                FROM extracted_links 
                WHERE model_name = ? 
                AND content_type = 'reel' 
                AND is_used = 0
            """
            
            oldest_params = [model_name]
            
            if platforms:
                placeholders = ','.join(['?'] * len(platforms))
                oldest_query += f" AND platform IN ({placeholders})"
                oldest_params.extend(platforms)
            
            oldest_query += " ORDER BY performance_metric DESC, engagement_score DESC LIMIT 1"
            
            self.cursor.execute(oldest_query, oldest_params)
            result = self.cursor.fetchone()
        
        if result:
            metadata = json.loads(result[7]) if result[7] else {}
            reel_info = {
                "link": result[0],
                "platform": result[1],
                "performance_metric": result[2],
                "engagement_score": result[3],
                "is_speaking": bool(result[4]),
                "has_captions": bool(result[5]),
                "has_music": bool(result[6]),
                "metadata": metadata
            }
            logger.info(f"Réel performant trouvé pour {model_name}: {result[0]} ({result[1]}, vues: {result[2]})")
            return reel_info
        else:
            logger.warning(f"Aucun réel trouvé pour {model_name}")
            return None
    
    def get_trending_hashtags(self, platform=None, limit=5, max_age_days=1):
        """
        Récupère les hashtags tendance récents.
        
        Args:
            platform (str, optional): Plateforme spécifique (si None, toutes les plateformes)
            limit (int): Nombre maximum de hashtags à récupérer
            max_age_days (int): Âge maximum des données en jours
            
        Returns:
            list: Liste des hashtags tendance
        """
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=max_age_days)).isoformat()
        
        query = """
            SELECT platform, name, url, rank, metadata 
            FROM trending_content 
            WHERE content_type = 'hashtag' 
            AND extraction_date > ?
        """
        
        params = [cutoff_date]
        
        if platform:
            query += " AND platform = ?"
            params.append(platform)
        
        query += " ORDER BY rank ASC LIMIT ?"
        params.append(limit)
        
        self.cursor.execute(query, params)
        results = self.cursor.fetchall()
        
        hashtags = []
        for result in results:
            metadata = json.loads(result[4]) if result[4] else {}
            hashtags.append({
                "platform": result[0],
                "name": result[1],
                "url": result[2],
                "rank": result[3],
                "metadata": metadata
            })
        
        return hashtags
    
    def get_trending_sounds(self, platform=None, limit=5, max_age_days=1):
        """
        Récupère les sons tendance récents.
        
        Args:
            platform (str, optional): Plateforme spécifique (si None, toutes les plateformes)
            limit (int): Nombre maximum de sons à récupérer
            max_age_days (int): Âge maximum des données en jours
            
        Returns:
            list: Liste des sons tendance
        """
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=max_age_days)).isoformat()
        
        query = """
            SELECT platform, name, url, rank, metadata 
            FROM trending_content 
            WHERE content_type = 'sound' 
            AND extraction_date > ?
        """
        
        params = [cutoff_date]
        
        if platform:
            query += " AND platform = ?"
            params.append(platform)
        
        query += " ORDER BY rank ASC LIMIT ?"
        params.append(limit)
        
        self.cursor.execute(query, params)
        results = self.cursor.fetchall()
        
        sounds = []
        for result in results:
            metadata = json.loads(result[4]) if result[4] else {}
            sounds.append({
                "platform": result[0],
                "name": result[1],
                "url": result[2],
                "rank": result[3],
                "metadata": metadata
            })
        
        return sounds
    
    def select_daily_content(self, model_name):
        """
        Sélectionne le contenu quotidien pour un modèle donné selon les critères spécifiés.
        
        Args:
            model_name (str): Nom du modèle
            
        Returns:
            dict: Contenu sélectionné (photos, vidéo, réel, tendances)
        """
        logger.info(f"Sélection du contenu quotidien pour {model_name}")
        
        # Récupérer les préférences du modèle
        preferences = self.get_model_preferences(model_name)
        
        # Déterminer les préférences spécifiques
        speaking_preference = preferences["prefers_speaking"]
        has_captions_preference = preferences["prefers_captions"]
        has_music_preference = preferences["prefers_music"]
        platforms = preferences["preferred_platforms"]
        
        # Récupérer les quotas de contenu
        content_quota = preferences["content_quota"]
        photos_count = content_quota.get("photos", 2)
        
        # Récupérer les photos récentes
        photos = self.get_recent_photos(model_name, days_threshold=7, count=photos_count, platforms=platforms)
        
        # Récupérer la meilleure vidéo
        video = self.get_best_video(model_name, days_threshold=14, platforms=platforms)
        
        # Récupérer le meilleur réel
        reel = self.get_best_reel(model_name, days_threshold=14, platforms=platforms)
        
        # Récupérer les tendances
        hashtags = self.get_trending_hashtags(limit=3)
        sounds = self.get_trending_sounds(limit=3)
        
        # Marquer le contenu comme utilisé
        for photo in photos:
            self.mark_content_as_used(model_name, photo["link"])
        
        if video:
            self.mark_content_as_used(model_name, video["link"])
        
        if reel:
            self.mark_content_as_used(model_name, reel["link"])
        
        # Préparer le résultat
        result = {
            "photos": photos,
            "video": video,
            "reel": reel,
            "trending": {
                "hashtags": hashtags,
                "sounds": sounds
            }
        }
        
        logger.info(f"Contenu sélectionné pour {model_name}: {len(photos)} photos, {1 if video else 0} vidéo, {1 if reel else 0} réel")
        return result

def select_content_for_all_models(model_names):
    """
    Sélectionne le contenu pour tous les modèles spécifiés.
    
    Args:
        model_names (list): Liste des noms de modèles
        
    Returns:
        dict: Contenu sélectionné pour chaque modèle
    """
    selector = ContentSelector()
    results = {}
    
    for model_name in model_names:
        results[model_name] = selector.select_daily_content(model_name)
    
    selector.close()
    return results

def process_scraped_content(scraped_data, model_names):
    """
    Traite le contenu scrapé et le stocke dans la base de données.
    
    Args:
        scraped_data (dict): Données scrapées
            {
                "platform": str,
                "username": str,
                "posts": [
                    {
                        "type": str (photo, video, reel),
                        "url": str,
                        "likes": int,
                        "comments": int,
                        "views": int,
                        "is_speaking": bool,
                        "has_captions": bool,
                        "has_music": bool,
                        "date": str,
                        "metadata": dict
                    },
                    ...
                ]
            }
        model_names (list): Liste des noms de modèles associés à ce contenu
        
    Returns:
        int: Nombre d'éléments stockés
    """
    if not scraped_data or "posts" not in scraped_data or not scraped_data["posts"]:
        logger.warning(f"Aucun contenu à traiter pour {scraped_data.get('username', 'inconnu')} sur {scraped_data.get('platform', 'inconnu')}")
        return 0
    
    platform = scraped_data["platform"]
    username = scraped_data["username"]
    posts = scraped_data["posts"]
    
    logger.info(f"Traitement de {len(posts)} posts pour {username} sur {platform}")
    
    selector = ContentSelector()
    count = 0
    
    for post in posts:
        post_type = post.get("type", "photo")
        content_type = post_type
        
        # Convertir le type si nécessaire
        if post_type == "image":
            content_type = "photo"
        elif post_type == "carousel":
            content_type = "photo"  # Traiter les carrousels comme des photos pour simplifier
        
        # Calculer le score d'engagement
        likes = post.get("likes", 0)
        comments = post.get("comments", 0)
        views = post.get("views", 0)
        
        engagement_score = 0
        performance_metric = 0
        
        if content_type == "photo":
            engagement_score = likes + (comments * 2)  # Les commentaires valent plus que les likes
            performance_metric = likes
        elif content_type in ["video", "reel"]:
            engagement_score = likes + (comments * 2)
            performance_metric = views
        
        # Stocker le contenu pour chaque modèle associé
        for model_name in model_names:
            content_data = {
                "model_name": model_name,
                "link": post["url"],
                "content_type": content_type,
                "platform": platform,
                "extraction_date": post.get("date", datetime.datetime.now().isoformat()),
                "performance_metric": performance_metric,
                "engagement_score": engagement_score,
                "is_speaking": post.get("is_speaking", False),
                "has_captions": post.get("has_captions", False),
                "has_music": post.get("has_music", False),
                "metadata": post.get("metadata", {})
            }
            
            if selector.store_content(content_data):
                count += 1
    
    selector.close()
    logger.info(f"Stocké {count} éléments pour {username} sur {platform}")
    return count

def process_trending_content(trending_data):
    """
    Traite le contenu tendance et le stocke dans la base de données.
    
    Args:
        trending_data (dict): Données tendance
            {
                "platform": str,
                "content_type": str,
                "items": [
                    {
                        "name": str,
                        "url": str,
                        "rank": int,
                        "metadata": dict
                    },
                    ...
                ]
            }
        
    Returns:
        bool: True si le traitement a réussi, False sinon
    """
    if not trending_data or "items" not in trending_data or not trending_data["items"]:
        logger.warning(f"Aucun contenu tendance à traiter pour {trending_data.get('platform', 'inconnu')}")
        return False
    
    selector = ContentSelector()
    result = selector.store_trending_content(trending_data)
    selector.close()
    
    return result

# Fonction principale pour tester le module
if __name__ == "__main__":
    logger.info("Test du module de sélection de contenu")
    
    # Créer une instance du sélecteur de contenu
    selector = ContentSelector()
    
    # Tester la sélection de contenu pour un modèle
    model_name = "Talia"
    content = selector.select_daily_content(model_name)
    
    # Afficher le contenu sélectionné
    logger.info(f"Contenu sélectionné pour {model_name}:")
    logger.info(f"Photos: {len(content['photos'])}")
    logger.info(f"Vidéo: {'Oui' if content['video'] else 'Non'}")
    logger.info(f"Réel: {'Oui' if content['reel'] else 'Non'}")
    
    # Fermer la connexion à la base de données
    selector.close()
    
    logger.info("Test terminé")
