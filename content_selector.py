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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("content_selector.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("content_selector")

# Configuration de la base de données SQLite
DB_PATH = "content_database.db"

class ContentSelector:
    """Classe pour la sélection de contenu selon les critères spécifiés."""
    
    def __init__(self):
        """Initialise le sélecteur de contenu."""
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        self._ensure_database_structure()
    
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
            logger.info(f"Contenu stocké pour {content_data['model_name']}: {content_data['link']}")
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
            
            # Filtrer par plateformes si spécifié
            if platforms:
                placeholders = ','.join(['?'] * len(platforms))
                old_query += f" AND platform IN ({placeholders})"
                old_params.extend(platforms)
            
            old_query += " ORDER BY engagement_score DESC, extraction_date DESC LIMIT ?"
            old_params.append(remaining)
            
            self.cursor.execute(old_query, old_params)
            
            additional_results = self.cursor.fetchall()
            additional_links = [{"link": row[0], "platform": row[1], "engagement_score": row[2]} for row in additional_results]
            photo_links.extend(additional_links)
            
            logger.info(f"Complété avec {len(additional_links)} photos plus anciennes pour {model_name}")
        
        return photo_links
    
    def get_recent_video(self, model_name, days_threshold=30, speaking_preference=None, has_captions_preference=None, has_music_preference=None, platforms=None):
        """
        Récupère une vidéo récente pour un modèle donné.
        
        Args:
            model_name (str): Nom du modèle
            days_threshold (int): Nombre de jours maximum pour considérer une vidéo comme récente
            speaking_preference (bool, optional): Préférence pour les vidéos où la modèle parle
            has_captions_preference (bool, optional): Préférence pour les vidéos avec sous-titres
            has_music_preference (bool, optional): Préférence pour les vidéos avec musique
            platforms (list): Liste des plateformes à considérer
            
        Returns:
            dict: Informations sur la vidéo récente
        """
        # Calculer la date limite
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days_threshold)).isoformat()
        
        # Construire la requête en fonction des préférences
        query = """
            SELECT link, platform, engagement_score, is_speaking, has_captions, has_music, metadata 
            FROM extracted_links 
            WHERE model_name = ? 
            AND content_type = 'video' 
            AND extraction_date > ? 
            AND is_used = 0
        """
        
        params = [model_name, cutoff_date]
        
        # Ajouter les conditions de préférence si spécifiées
        conditions = []
        if speaking_preference is not None:
            conditions.append("is_speaking = ?")
            params.append(1 if speaking_preference else 0)
        
        if has_captions_preference is not None:
            conditions.append("has_captions = ?")
            params.append(1 if has_captions_preference else 0)
        
        if has_music_preference is not None:
            conditions.append("has_music = ?")
            params.append(1 if has_music_preference else 0)
        
        if platforms:
            placeholders = ','.join(['?'] * len(platforms))
            conditions.append(f"platform IN ({placeholders})")
            params.extend(platforms)
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        query += " ORDER BY engagement_score DESC, extraction_date DESC LIMIT 1"
        
        self.cursor.execute(query, params)
        result = self.cursor.fetchone()
        
        # Si aucun résultat avec les préférences, essayer sans préférences
        if not result:
            relaxed_query = """
                SELECT link, platform, engagement_score, is_speaking, has_captions, has_music, metadata 
                FROM extracted_links 
                WHERE model_name = ? 
                AND content_type = 'video' 
                AND extraction_date > ? 
                AND is_used = 0
            """
            
            relaxed_params = [model_name, cutoff_date]
            
            # Ajouter seulement le filtre de plateforme si spécifié
            if platforms:
                placeholders = ','.join(['?'] * len(platforms))
                relaxed_query += f" AND platform IN ({placeholders})"
                relaxed_params.extend(platforms)
            
            relaxed_query += " ORDER BY engagement_score DESC, extraction_date DESC LIMIT 1"
            
            self.cursor.execute(relaxed_query, relaxed_params)
            result = self.cursor.fetchone()
        
        # Si toujours aucun résultat, essayer avec une date plus ancienne
        if not result:
            oldest_query = """
                SELECT link, platform, engagement_score, is_speaking, has_captions, has_music, metadata 
                FROM extracted_links 
                WHERE model_name = ? 
                AND content_type = 'video' 
                AND is_used = 0
            """
            
            oldest_params = [model_name]
            
            # Ajouter seulement le filtre de plateforme si spécifié
            if platforms:
                placeholders = ','.join(['?'] * len(platforms))
                oldest_query += f" AND platform IN ({placeholders})"
                oldest_params.extend(platforms)
            
            oldest_query += " ORDER BY engagement_score DESC, extraction_date DESC LIMIT 1"
            
            self.cursor.execute(oldest_query, oldest_params)
            result = self.cursor.fetchone()
        
        if result:
            metadata = json.loads(result[6]) if result[6] else {}
            video_info = {
                "link": result[0],
                "platform": result[1],
                "engagement_score": result[2],
                "is_speaking": bool(result[3]),
                "has_captions": bool(result[4]),
                "has_music": bool(result[5]),
                "metadata": metadata
            }
            logger.info(f"Vidéo récente trouvée pour {model_name}: {result[0]} ({result[1]})")
            return video_info
        else:
            logger.warning(f"Aucune vidéo trouvée pour {model_name}")
            return None
    
    def get_performant_reel(self, model_name, days_threshold=14, performance_threshold=2.0, platforms=None):
        """
        Récupère un réel performant pour un modèle donné.
        
        Args:
            model_name (str): Nom du modèle
            days_threshold (int): Nombre de jours maximum pour considérer un réel comme récent
            performance_threshold (float): Seuil de performance (ratio vues/moyenne)
            platforms (list): Liste des plateformes à considérer
            
        Returns:
            dict: Informations sur le réel performant
        """
        # Calculer la date limite
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days_threshold)).isoformat()
        
        # Récupérer la moyenne des vues pour ce modèle
        self.cursor.execute(
            "SELECT avg_reel_views FROM model_stats WHERE model_name = ?",
            (model_name,)
        )
        result = self.cursor.fetchone()
        
        if result:
            avg_views = result[0]
        else:
            # Valeurs par défaut selon les spécifications
            default_values = {
                "talia": 4000,
                "léa": 3000,
                "lizz": 3500
            }
            avg_views = default_values.get(model_name.lower(), 3000)
        
        # Calculer le seuil de vues minimum
        min_views = avg_views * performance_threshold
        
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
            logger.info(f"Réel performant trouvé pour {model_name}: {result[0]} ({result[1]})")
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
        content_quota = preferences["content_quota"]
        
        # Sélectionner les photos récentes
        photo_count = content_quota.get("photos", 2)
        photo_links = self.get_recent_photos(model_name, days_threshold=7, count=photo_count, platforms=platforms)
        
        # Sélectionner la vidéo récente
        video_info = self.get_recent_video(
            model_name, 
            days_threshold=30, 
            speaking_preference=speaking_preference,
            has_captions_preference=has_captions_preference,
            has_music_preference=has_music_preference,
            platforms=platforms
        )
        
        # Sélectionner le réel performant
        reel_info = self.get_performant_reel(model_name, days_threshold=14, performance_threshold=2.0, platforms=platforms)
        
        # Récupérer les hashtags tendance
        trending_hashtags = self.get_trending_hashtags(limit=5)
        
        # Récupérer les sons tendance
        trending_sounds = self.get_trending_sounds(limit=5)
        
        # Marquer le contenu comme utilisé
        for photo in photo_links:
            self.mark_content_as_used(model_name, photo["link"])
        
        if video_info:
            self.mark_content_as_used(model_name, video_info["link"])
        
        if reel_info:
            self.mark_content_as_used(model_name, reel_info["link"])
        
        # Préparer le résultat
        result = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "photos": photo_links,
            "video": video_info,
            "reel": reel_info,
            "trending": {
                "hashtags": trending_hashtags,
                "sounds": trending_sounds
            }
        }
        
        logger.info(f"Contenu sélectionné pour {model_name}: {len(photo_links)} photos, " + 
                   f"{'1 vidéo' if video_info else '0 vidéo'}, " + 
                   f"{'1 réel' if reel_info else '0 réel'}")
        return result

def select_content_for_all_models(models):
    """
    Sélectionne le contenu quotidien pour tous les modèles.
    
    Args:
        models (list): Liste des noms des modèles
        
    Returns:
        dict: Contenu sélectionné pour chaque modèle
    """
    selector = ContentSelector()
    results = {}
    
    try:
        for model_name in models:
            results[model_name] = selector.select_daily_content(model_name)
    finally:
        selector.close()
    
    return results

def process_scraped_content(content_data, model_names):
    """
    Traite le contenu extrait par les scrapers et le stocke dans la base de données.
    
    Args:
        content_data (dict): Données du contenu extrait par les scrapers
            {
                "platform": str,
                "username": str,
                "posts": [
                    {
                        "type": str,
                        "url": str,
                        "media_url": str,
                        "date": str,
                        "text": str,
                        "likes": int,
                        "engagement_score": float,
                        "is_speaking": bool,
                        "has_captions": bool,
                        "has_music": bool,
                        ...
                    },
                    ...
                ]
            }
        model_names (list): Liste des noms des modèles pour lesquels stocker le contenu
        
    Returns:
        int: Nombre d'éléments stockés
    """
    selector = ContentSelector()
    count = 0
    
    try:
        platform = content_data["platform"]
        username = content_data["username"]
        
        for post in content_data["posts"]:
            # Déterminer le type de contenu
            content_type = post["type"]
            if content_type == "reel" or (platform == "instagram" and content_type == "video" and "reel" in post["url"]):
                content_type = "reel"
            
            # Calculer la performance metric pour les réels
            performance_metric = 0
            if content_type == "reel" and "views" in post:
                performance_metric = post["views"]
            elif content_type == "reel" and "play_count" in post:
                performance_metric = post["play_count"]
            
            # Stocker le contenu pour chaque modèle
            for model_name in model_names:
                content_data = {
                    "model_name": model_name,
                    "link": post["url"],
                    "content_type": content_type,
                    "platform": platform,
                    "extraction_date": datetime.datetime.now().isoformat(),
                    "performance_metric": performance_metric,
                    "engagement_score": post.get("engagement_score", 0),
                    "is_speaking": post.get("is_speaking", False),
                    "has_captions": post.get("has_captions", False),
                    "has_music": post.get("has_music", False),
                    "metadata": {k: v for k, v in post.items() if k not in [
                        "type", "url", "extraction_date", "performance_metric", 
                        "engagement_score", "is_speaking", "has_captions", "has_music"
                    ]}
                }
                
                if selector.store_content(content_data):
                    count += 1
    finally:
        selector.close()
    
    return count

def process_trending_content(trending_data):
    """
    Traite les contenus tendance et les stocke dans la base de données.
    
    Args:
        trending_data (dict): Données des contenus tendance
            {
                "platform": str,
                "content_type": str,
                "items": [
                    {
                        "name": str,
                        "url": str,
                        "rank": int,
                        ...
                    },
                    ...
                ]
            }
        
    Returns:
        bool: True si le traitement a réussi, False sinon
    """
    selector = ContentSelector()
    
    try:
        return selector.store_trending_content(trending_data)
    finally:
        selector.close()

if __name__ == "__main__":
    # Liste des modèles
    models = ["Talia", "Léa", "Lizz"]
    
    # Sélectionner le contenu pour tous les modèles
    daily_content = select_content_for_all_models(models)
    
    # Afficher le résultat
    print(json.dumps(daily_content, indent=2))
