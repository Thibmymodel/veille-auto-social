#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module de scraping TikTok pour le système de veille automatisée.
Ce module permet de collecter du contenu depuis TikTok sans utiliser l'API officielle.
"""

import os
import time
import random
import logging
import requests
import json
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from fake_useragent import UserAgent
from datetime import datetime, timedelta

# Configuration du logging
logger = logging.getLogger("tiktok_scraper")

class TikTokScraper:
    """Classe pour scraper du contenu depuis TikTok."""
    
    def __init__(self, headless=True, proxy=None, retry_count=3, retry_delay=5):
        """
        Initialise le scraper TikTok.
        
        Args:
            headless (bool): Si True, le navigateur s'exécute en mode headless (sans interface graphique)
            proxy (str): Proxy à utiliser pour les requêtes (format: 'http://user:pass@ip:port')
            retry_count (int): Nombre de tentatives en cas d'échec
            retry_delay (int): Délai entre les tentatives en secondes
        """
        self.user_agent = UserAgent().random
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})
        self.driver = None
        self.headless = headless
        self.proxy = proxy
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.is_logged_in = False
        
        # URL de base
        self.tiktok_url = "https://www.tiktok.com"
        
    def _initialize_driver(self):
        """Initialise le driver Selenium pour TikTok."""
        if self.driver:
            return
            
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"user-agent={self.user_agent}")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        if self.proxy:
            chrome_options.add_argument(f"--proxy-server={self.proxy}")
        
        # Configuration spécifique pour Railway
        if 'RAILWAY_ENVIRONMENT' in os.environ:
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.binary_location = "/usr/bin/google-chrome"
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(30)
        
        # Masquer la détection de Selenium
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        
    def _close_driver(self):
        """Ferme le driver Selenium."""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def _retry_on_failure(self, func, *args, **kwargs):
        """
        Exécute une fonction avec plusieurs tentatives en cas d'échec.
        
        Args:
            func: Fonction à exécuter
            *args: Arguments positionnels pour la fonction
            **kwargs: Arguments nommés pour la fonction
            
        Returns:
            Le résultat de la fonction ou None en cas d'échec
        """
        for attempt in range(self.retry_count):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Tentative {attempt+1}/{self.retry_count} échouée: {str(e)}")
                if attempt < self.retry_count - 1:
                    # Changer d'user agent entre les tentatives
                    self.user_agent = UserAgent().random
                    self.session.headers.update({'User-Agent': self.user_agent})
                    
                    # Fermer et réinitialiser le driver
                    self._close_driver()
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Échec après {self.retry_count} tentatives: {str(e)}")
                    return None
    
    def _type_like_human(self, element, text):
        """
        Simule une saisie humaine dans un champ de formulaire.
        
        Args:
            element: Élément du formulaire
            text (str): Texte à saisir
        """
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))
    
    def _handle_cookies_popup(self):
        """Gère les popups de cookies sur TikTok."""
        try:
            # Attendre que le popup de cookies apparaisse
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Accepter')]"))
            )
            
            # Cliquer sur le bouton d'acceptation
            accept_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Accepter')]")
            accept_button.click()
            time.sleep(random.uniform(1, 2))
            
            logger.info("Popup de cookies géré avec succès")
        except:
            # Le popup de cookies n'est pas apparu ou a déjà été géré
            pass
    
    def _handle_login_popup(self):
        """Gère les popups de connexion sur TikTok."""
        try:
            # Attendre que le popup de connexion apparaisse
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'login-modal')]"))
            )
            
            # Cliquer sur le bouton de fermeture
            close_button = self.driver.find_element(By.XPATH, "//button[contains(@class, 'close-button')]")
            close_button.click()
            time.sleep(random.uniform(1, 2))
            
            logger.info("Popup de connexion fermé avec succès")
        except:
            # Le popup de connexion n'est pas apparu ou a déjà été géré
            pass
    
    def login(self, username, password):
        """
        Se connecte à TikTok.
        
        Args:
            username (str): Nom d'utilisateur TikTok
            password (str): Mot de passe TikTok
            
        Returns:
            bool: True si la connexion a réussi, False sinon
        """
        try:
            self._initialize_driver()
            
            # Accéder à la page d'accueil de TikTok
            self.driver.get(self.tiktok_url)
            time.sleep(random.uniform(2, 4))
            
            # Gérer les popups
            self._handle_cookies_popup()
            
            # Cliquer sur le bouton de connexion
            try:
                login_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Log in') or contains(text(), 'Connexion')]"))
                )
                login_button.click()
                time.sleep(random.uniform(1, 2))
            except:
                # Peut-être déjà sur la page de connexion
                pass
            
            # Sélectionner la connexion par email/nom d'utilisateur
            try:
                use_email_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Use phone / email / username') or contains(text(), 'Utiliser un téléphone / e-mail / nom d'utilisateur')]"))
                )
                use_email_button.click()
                time.sleep(random.uniform(1, 2))
                
                # Sélectionner l'option de connexion par nom d'utilisateur
                username_option = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Log in with username') or contains(text(), 'Connexion avec un nom d'utilisateur')]")
                username_option.click()
                time.sleep(random.uniform(1, 2))
            except:
                # L'interface peut varier, essayer une autre approche
                try:
                    # Parfois, il y a un bouton direct pour se connecter avec un nom d'utilisateur
                    username_button = self.driver.find_element(By.XPATH, "//div[contains(text(), 'Username') or contains(text(), 'Nom d'utilisateur')]")
                    username_button.click()
                    time.sleep(random.uniform(1, 2))
                except:
                    # Continuer avec le formulaire actuel
                    pass
            
            # Remplir le formulaire de connexion
            try:
                username_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@name='username' or @placeholder='Username' or @placeholder='Nom d'utilisateur']"))
                )
                self._type_like_human(username_field, username)
                time.sleep(random.uniform(0.5, 1.5))
                
                password_field = self.driver.find_element(By.XPATH, "//input[@type='password']")
                self._type_like_human(password_field, password)
                time.sleep(random.uniform(0.5, 1.5))
                
                # Cliquer sur Se connecter
                submit_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
                submit_button.click()
                
                # Attendre que la connexion soit établie
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//span[contains(@class, 'avatar')]"))
                )
                
                logger.info("Connexion à TikTok réussie")
                self.is_logged_in = True
                return True
            except Exception as e:
                logger.error(f"Erreur lors de la connexion à TikTok: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de la connexion à TikTok: {str(e)}")
            return False
    
    def search_profiles(self, keywords, min_followers=10000, max_results=20):
        """
        Recherche des profils TikTok correspondant aux mots-clés.
        
        Args:
            keywords (list): Liste de mots-clés pour la recherche
            min_followers (int): Nombre minimum d'abonnés
            max_results (int): Nombre maximum de résultats à retourner
            
        Returns:
            list: Liste de dictionnaires contenant les informations des profils
        """
        return self._retry_on_failure(self._search_profiles, keywords, min_followers, max_results)
    
    def _search_profiles(self, keywords, min_followers=10000, max_results=20):
        """
        Implémentation interne de la recherche de profils.
        """
        profiles = []
        
        try:
            self._initialize_driver()
            
            for keyword in keywords:
                logger.info(f"Recherche de profils avec le mot-clé: {keyword}")
                
                # Accéder à la page de recherche
                search_url = f"{self.tiktok_url}/search/user?q={keyword}"
                self.driver.get(search_url)
                time.sleep(random.uniform(3, 5))
                
                # Gérer les popups
                self._handle_cookies_popup()
                self._handle_login_popup()
                
                # Attendre que les résultats de recherche apparaissent
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'user-card')]"))
                    )
                except:
                    logger.warning(f"Aucun résultat trouvé pour le mot-clé: {keyword}")
                    continue
                
                # Récupérer les résultats
                profile_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'user-card')]")
                
                for profile in profile_elements[:min(30, len(profile_elements))]:
                    try:
                        # Récupérer le nom d'utilisateur
                        username_element = profile.find_element(By.XPATH, ".//p[contains(@class, 'user-name')]")
                        username = username_element.text.strip()
                        if username.startswith('@'):
                            username = username[1:]
                        
                        # Récupérer le nom complet
                        try:
                            name_element = profile.find_element(By.XPATH, ".//p[contains(@class, 'user-title')]")
                            name = name_element.text.strip()
                        except:
                            name = username
                        
                        # Récupérer l'URL du profil
                        profile_url = f"{self.tiktok_url}/@{username}"
                        
                        # Visiter le profil pour obtenir plus d'informations
                        self.driver.get(profile_url)
                        time.sleep(random.uniform(2, 4))
                        
                        # Gérer les popups
                        self._handle_login_popup()
                        
                        # Récupérer le nombre d'abonnés
                        try:
                            followers_element = WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.XPATH, "//strong[contains(@title, 'Followers') or contains(@title, 'Abonnés')]"))
                            )
                            followers_text = followers_element.text.replace(",", "").replace(".", "").strip()
                            followers_count = int(''.join(filter(str.isdigit, followers_text))) if any(c.isdigit() for c in followers_text) else 0
                            
                            if "K" in followers_text or "k" in followers_text:
                                followers_count *= 1000
                            elif "M" in followers_text or "m" in followers_text:
                                followers_count *= 1000000
                        except:
                            # Si on ne peut pas récupérer le nombre d'abonnés, on suppose qu'il est inférieur au minimum
                            followers_count = 0
                        
                        if followers_count >= min_followers:
                            # Récupérer la bio
                            try:
                                bio_element = self.driver.find_element(By.XPATH, "//h2[contains(@class, 'bio')]/span")
                                bio = bio_element.text
                            except:
                                bio = ""
                            
                            profiles.append({
                                "username": username,
                                "name": name,
                                "bio": bio,
                                "followers": followers_count,
                                "url": profile_url
                            })
                            
                            logger.info(f"Profil trouvé: {username} avec {followers_count} abonnés")
                        
                        if len(profiles) >= max_results:
                            break
                        
                        # Revenir à la page de recherche
                        self.driver.get(search_url)
                        time.sleep(random.uniform(2, 3))
                        
                        # Gérer les popups
                        self._handle_login_popup()
                        
                    except Exception as e:
                        logger.error(f"Erreur lors de l'analyse du profil: {str(e)}")
                        continue
                
                if len(profiles) >= max_results:
                    break
                
                time.sleep(random.uniform(2, 5))
            
            return profiles
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de profils TikTok: {str(e)}")
            return profiles
    
    def extract_recent_content(self, username, days_limit=14, max_posts=20):
        """
        Extrait le contenu récent d'un profil TikTok.
        
        Args:
            username (str): Nom d'utilisateur du profil TikTok (sans @)
            days_limit (int): Limite en jours pour le contenu récent
            max_posts (int): Nombre maximum de posts à extraire
            
        Returns:
            list: Liste de dictionnaires contenant les informations des posts
        """
        return self._retry_on_failure(self._extract_recent_content, username, days_limit, max_posts)
    
    def _extract_recent_content(self, username, days_limit=14, max_posts=20):
        """
        Implémentation interne de l'extraction de contenu récent.
        """
        posts = []
        
        try:
            self._initialize_driver()
            
            # Accéder au profil
            profile_url = f"{self.tiktok_url}/@{username}"
            self.driver.get(profile_url)
            time.sleep(random.uniform(3, 5))
            
            # Gérer les popups
            self._handle_cookies_popup()
            self._handle_login_popup()
            
            # Vérifier si le profil est privé
            try:
                private_element = self.driver.find_element(By.XPATH, "//p[contains(text(), 'This account is private') or contains(text(), 'Ce compte est privé')]")
                logger.info(f"Le profil {username} est privé")
                return posts
            except NoSuchElementException:
                pass
            
            # Récupérer les vidéos
            video_elements = []
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            while len(video_elements) < max_posts:
                # Récupérer toutes les vidéos visibles
                elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'video-feed-item')]")
                
                video_elements.extend([e for e in elements if e not in video_elements])
                
                if len(video_elements) >= max_posts:
                    break
                
                # Faire défiler la page
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
                
                # Vérifier si on a atteint le bas de la page
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            
            # Limiter le nombre de vidéos à analyser
            video_elements = video_elements[:min(max_posts, len(video_elements))]
            
            for video_element in video_elements:
                try:
                    # Récupérer l'URL de la vidéo
                    video_link = video_element.find_element(By.XPATH, ".//a")
                    video_url = video_link.get_attribute("href")
                    
                    # Visiter la page de la vidéo pour obtenir plus d'informations
                    self.driver.get(video_url)
                    time.sleep(random.uniform(2, 3))
                    
                    # Gérer les popups
                    self._handle_login_popup()
                    
                    # Récupérer la date de la vidéo
                    try:
                        date_element = self.driver.find_element(By.XPATH, "//span[contains(@class, 'video-meta')]")
                        date_text = date_element.text.strip()
                        
                        # Convertir la date relative en date absolue
                        days_ago = 0
                        if "h" in date_text or "hour" in date_text:
                            days_ago = 0
                        elif "d" in date_text or "day" in date_text:
                            days_match = re.search(r'(\d+)d', date_text) or re.search(r'(\d+) day', date_text)
                            if days_match:
                                days_ago = int(days_match.group(1))
                        elif "w" in date_text or "week" in date_text:
                            weeks_match = re.search(r'(\d+)w', date_text) or re.search(r'(\d+) week', date_text)
                            if weeks_match:
                                days_ago = int(weeks_match.group(1)) * 7
                        elif "m" in date_text or "month" in date_text:
                            months_match = re.search(r'(\d+)m', date_text) or re.search(r'(\d+) month', date_text)
                            if months_match:
                                days_ago = int(months_match.group(1)) * 30
                        
                        post_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                    except:
                        # Si on ne peut pas récupérer la date, on suppose qu'elle est récente
                        post_date = datetime.now().strftime("%Y-%m-%d")
                        days_ago = 0
                    
                    if days_ago > days_limit:
                        # Revenir à la page de profil
                        self.driver.get(profile_url)
                        time.sleep(random.uniform(2, 3))
                        continue
                    
                    # Récupérer l'URL de la miniature de la vidéo
                    try:
                        thumbnail_element = self.driver.find_element(By.XPATH, "//video")
                        media_url = thumbnail_element.get_attribute("poster") or ""
                    except:
                        media_url = ""
                    
                    # Récupérer le texte de la vidéo
                    try:
                        text_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'video-caption')]")
                        video_text = text_element.text
                    except:
                        video_text = ""
                    
                    # Récupérer les statistiques de la vidéo
                    likes = 0
                    comments = 0
                    shares = 0
                    views = 0
                    
                    try:
                        stats_elements = self.driver.find_elements(By.XPATH, "//strong[@data-e2e]")
                        for stat in stats_elements:
                            stat_type = stat.get_attribute("data-e2e")
                            stat_text = stat.text.replace(",", "").replace(".", "").strip()
                            stat_value = int(''.join(filter(str.isdigit, stat_text))) if any(c.isdigit() for c in stat_text) else 0
                            
                            if "K" in stat_text or "k" in stat_text:
                                stat_value *= 1000
                            elif "M" in stat_text or "m" in stat_text:
                                stat_value *= 1000000
                            
                            if "like" in stat_type:
                                likes = stat_value
                            elif "comment" in stat_type:
                                comments = stat_value
                            elif "share" in stat_type:
                                shares = stat_value
                            elif "view" in stat_type:
                                views = stat_value
                    except:
                        pass
                    
                    # Vérifier si la vidéo contient des sous-titres (important pour Lizz)
                    has_captions = False
                    if "[" in video_text and "]" in video_text:
                        has_captions = True
                    
                    # Vérifier si la vidéo mentionne que la personne parle (important pour Lizz)
                    is_speaking = False
                    speaking_keywords = ["je vous parle", "je parle", "je vous explique", "face caméra", "facecam"]
                    if any(keyword in video_text.lower() for keyword in speaking_keywords):
                        is_speaking = True
                    
                    # Vérifier si la vidéo contient de la musique (important pour Talia et Léa)
                    has_music = True  # Par défaut, toutes les vidéos TikTok ont de la musique
                    
                    # Récupérer le nom de la musique
                    try:
                        music_element = self.driver.find_element(By.XPATH, "//h4[contains(@class, 'music-title')]")
                        music_name = music_element.text
                    except:
                        music_name = ""
                    
                    # Calculer le score d'engagement
                    engagement_score = likes + comments * 2 + shares * 3
                    
                    # Ajouter la vidéo à la liste
                    posts.append({
                        "type": "video",
                        "url": video_url,
                        "media_url": media_url,
                        "date": post_date,
                        "days_ago": days_ago,
                        "text": video_text,
                        "likes": likes,
                        "comments": comments,
                        "shares": shares,
                        "views": views,
                        "music": music_name,
                        "engagement_score": engagement_score,
                        "has_captions": has_captions,
                        "is_speaking": is_speaking,
                        "has_music": has_music,
                        "platform": "tiktok",
                        "username": username
                    })
                    
                    logger.info(f"Vidéo extraite: {video_url} - {likes} likes, {days_ago} jours")
                    
                    # Revenir à la page de profil
                    self.driver.get(profile_url)
                    time.sleep(random.uniform(2, 3))
                    
                except Exception as e:
                    logger.error(f"Erreur lors de l'analyse de la vidéo: {str(e)}")
                    # Revenir à la page de profil
                    self.driver.get(profile_url)
                    time.sleep(random.uniform(2, 3))
                    continue
            
            # Trier les vidéos par score d'engagement
            posts.sort(key=lambda x: x["engagement_score"], reverse=True)
            
            return posts
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction du contenu TikTok: {str(e)}")
            return posts
    
    def extract_trending_hashtags(self, limit=10):
        """
        Extrait les hashtags tendance sur TikTok.
        
        Args:
            limit (int): Nombre maximum de hashtags à extraire
            
        Returns:
            list: Liste de dictionnaires contenant les informations des hashtags
        """
        return self._retry_on_failure(self._extract_trending_hashtags, limit)
    
    def _extract_trending_hashtags(self, limit=10):
        """
        Implémentation interne de l'extraction des hashtags tendance.
        """
        hashtags = []
        
        try:
            self._initialize_driver()
            
            # Accéder à la page des tendances
            self.driver.get(f"{self.tiktok_url}/discover")
            time.sleep(random.uniform(3, 5))
            
            # Gérer les popups
            self._handle_cookies_popup()
            self._handle_login_popup()
            
            # Récupérer les hashtags tendance
            hashtag_elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/tag/')]")
            
            for i, hashtag_element in enumerate(hashtag_elements[:min(limit, len(hashtag_elements))]):
                try:
                    hashtag_url = hashtag_element.get_attribute("href")
                    hashtag_name = hashtag_url.split("/tag/")[-1]
                    
                    # Récupérer le texte du hashtag (peut contenir le nombre de vues)
                    hashtag_text = hashtag_element.text
                    
                    # Extraire le nombre de vues si disponible
                    views = 0
                    views_match = re.search(r'(\d+\.?\d*[KMB]?) views', hashtag_text)
                    if views_match:
                        views_text = views_match.group(1)
                        views = float(views_text.replace("K", "").replace("M", "").replace("B", ""))
                        if "K" in views_text:
                            views *= 1000
                        elif "M" in views_text:
                            views *= 1000000
                        elif "B" in views_text:
                            views *= 1000000000
                        views = int(views)
                    
                    hashtags.append({
                        "name": hashtag_name,
                        "url": hashtag_url,
                        "views": views,
                        "rank": i + 1
                    })
                    
                    logger.info(f"Hashtag tendance trouvé: #{hashtag_name}")
                    
                except Exception as e:
                    logger.error(f"Erreur lors de l'analyse du hashtag: {str(e)}")
                    continue
            
            return hashtags
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des hashtags tendance: {str(e)}")
            return hashtags
    
    def extract_trending_sounds(self, limit=10):
        """
        Extrait les sons tendance sur TikTok.
        
        Args:
            limit (int): Nombre maximum de sons à extraire
            
        Returns:
            list: Liste de dictionnaires contenant les informations des sons
        """
        return self._retry_on_failure(self._extract_trending_sounds, limit)
    
    def _extract_trending_sounds(self, limit=10):
        """
        Implémentation interne de l'extraction des sons tendance.
        """
        sounds = []
        
        try:
            self._initialize_driver()
            
            # Accéder à la page des tendances
            self.driver.get(f"{self.tiktok_url}/discover")
            time.sleep(random.uniform(3, 5))
            
            # Gérer les popups
            self._handle_cookies_popup()
            self._handle_login_popup()
            
            # Cliquer sur l'onglet des sons
            try:
                sounds_tab = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Sounds') or contains(text(), 'Sons')]"))
                )
                sounds_tab.click()
                time.sleep(random.uniform(2, 3))
            except:
                logger.warning("Impossible de trouver l'onglet des sons")
                return sounds
            
            # Récupérer les sons tendance
            sound_elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/music/')]")
            
            for i, sound_element in enumerate(sound_elements[:min(limit, len(sound_elements))]):
                try:
                    sound_url = sound_element.get_attribute("href")
                    sound_name = sound_url.split("/music/")[-1]
                    
                    # Récupérer le texte du son (peut contenir le nombre de vidéos)
                    sound_text = sound_element.text
                    
                    # Extraire le nombre de vidéos si disponible
                    videos_count = 0
                    videos_match = re.search(r'(\d+\.?\d*[KMB]?) videos', sound_text)
                    if videos_match:
                        videos_text = videos_match.group(1)
                        videos_count = float(videos_text.replace("K", "").replace("M", "").replace("B", ""))
                        if "K" in videos_text:
                            videos_count *= 1000
                        elif "M" in videos_text:
                            videos_count *= 1000000
                        elif "B" in videos_text:
                            videos_count *= 1000000000
                        videos_count = int(videos_count)
                    
                    sounds.append({
                        "name": sound_name,
                        "url": sound_url,
                        "videos_count": videos_count,
                        "rank": i + 1
                    })
                    
                    logger.info(f"Son tendance trouvé: {sound_name}")
                    
                except Exception as e:
                    logger.error(f"Erreur lors de l'analyse du son: {str(e)}")
                    continue
            
            return sounds
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des sons tendance: {str(e)}")
            return sounds
    
    def get_account_stats(self, username):
        """
        Récupère les statistiques d'un compte TikTok.
        
        Args:
            username (str): Nom d'utilisateur du profil TikTok (sans @)
            
        Returns:
            dict: Dictionnaire contenant les statistiques du compte
        """
        return self._retry_on_failure(self._get_account_stats, username)
    
    def _get_account_stats(self, username):
        """
        Implémentation interne de la récupération des statistiques du compte.
        """
        stats = {
            "username": username,
            "followers": 0,
            "following": 0,
            "likes": 0,
            "videos_count": 0,
            "avg_likes": 0,
            "avg_comments": 0,
            "avg_shares": 0,
            "engagement_rate": 0.0,
            "bio": "",
            "website": "",
            "is_private": False
        }
        
        try:
            self._initialize_driver()
            
            # Accéder au profil
            profile_url = f"{self.tiktok_url}/@{username}"
            self.driver.get(profile_url)
            time.sleep(random.uniform(3, 5))
            
            # Gérer les popups
            self._handle_cookies_popup()
            self._handle_login_popup()
            
            # Vérifier si le profil est privé
            try:
                private_element = self.driver.find_element(By.XPATH, "//p[contains(text(), 'This account is private') or contains(text(), 'Ce compte est privé')]")
                stats["is_private"] = True
                logger.info(f"Le profil {username} est privé")
            except NoSuchElementException:
                pass
            
            # Récupérer le nombre d'abonnés
            try:
                followers_element = self.driver.find_element(By.XPATH, "//strong[contains(@title, 'Followers') or contains(@title, 'Abonnés')]")
                followers_text = followers_element.text.replace(",", "").replace(".", "").strip()
                stats["followers"] = int(''.join(filter(str.isdigit, followers_text))) if any(c.isdigit() for c in followers_text) else 0
                
                if "K" in followers_text or "k" in followers_text:
                    stats["followers"] *= 1000
                elif "M" in followers_text or "m" in followers_text:
                    stats["followers"] *= 1000000
            except:
                pass
            
            # Récupérer le nombre d'abonnements
            try:
                following_element = self.driver.find_element(By.XPATH, "//strong[contains(@title, 'Following') or contains(@title, 'Abonnements')]")
                following_text = following_element.text.replace(",", "").replace(".", "").strip()
                stats["following"] = int(''.join(filter(str.isdigit, following_text))) if any(c.isdigit() for c in following_text) else 0
                
                if "K" in following_text or "k" in following_text:
                    stats["following"] *= 1000
                elif "M" in following_text or "m" in following_text:
                    stats["following"] *= 1000000
            except:
                pass
            
            # Récupérer le nombre de likes
            try:
                likes_element = self.driver.find_element(By.XPATH, "//strong[contains(@title, 'Likes') or contains(@title, 'J'aime')]")
                likes_text = likes_element.text.replace(",", "").replace(".", "").strip()
                stats["likes"] = int(''.join(filter(str.isdigit, likes_text))) if any(c.isdigit() for c in likes_text) else 0
                
                if "K" in likes_text or "k" in likes_text:
                    stats["likes"] *= 1000
                elif "M" in likes_text or "m" in likes_text:
                    stats["likes"] *= 1000000
            except:
                pass
            
            # Récupérer la bio
            try:
                bio_element = self.driver.find_element(By.XPATH, "//h2[contains(@class, 'bio')]/span")
                stats["bio"] = bio_element.text
            except:
                pass
            
            # Récupérer le site web
            try:
                website_element = self.driver.find_element(By.XPATH, "//a[contains(@class, 'link')]")
                stats["website"] = website_element.get_attribute("href")
            except:
                pass
            
            # Si le profil n'est pas privé, calculer les moyennes d'engagement
            if not stats["is_private"]:
                # Récupérer quelques vidéos pour calculer les moyennes
                posts = self.extract_recent_content(username, days_limit=30, max_posts=5)
                
                if posts:
                    likes_list = [post["likes"] for post in posts]
                    comments_list = [post["comments"] for post in posts]
                    shares_list = [post["shares"] for post in posts]
                    
                    # Calculer les moyennes
                    if likes_list:
                        stats["avg_likes"] = sum(likes_list) / len(likes_list)
                    
                    if comments_list:
                        stats["avg_comments"] = sum(comments_list) / len(comments_list)
                    
                    if shares_list:
                        stats["avg_shares"] = sum(shares_list) / len(shares_list)
                    
                    # Calculer le taux d'engagement moyen
                    if stats["followers"] > 0:
                        avg_engagement = (stats["avg_likes"] + stats["avg_comments"] + stats["avg_shares"]) / stats["followers"] * 100
                        stats["engagement_rate"] = round(avg_engagement, 2)
                    
                    # Estimer le nombre de vidéos
                    try:
                        # Compter le nombre de vidéos visibles sur la page
                        video_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'video-feed-item')]")
                        stats["videos_count"] = len(video_elements)
                    except:
                        pass
            
            return stats
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques du compte: {str(e)}")
            return stats
    
    def close(self):
        """Ferme le scraper et libère les ressources."""
        self._close_driver()
        self.session.close()

# Fonctions pour utilisation directe
def extract_tiktok_content(username, days_limit=14, max_posts=20, headless=True):
    """
    Extrait le contenu récent d'un profil TikTok.
    
    Args:
        username (str): Nom d'utilisateur du profil TikTok (sans @)
        days_limit (int): Limite en jours pour le contenu récent
        max_posts (int): Nombre maximum de posts à extraire
        headless (bool): Si True, le navigateur s'exécute en mode headless
        
    Returns:
        list: Liste de dictionnaires contenant les informations des posts
    """
    scraper = TikTokScraper(headless=headless)
    try:
        posts = scraper.extract_recent_content(username, days_limit, max_posts)
        return posts
    finally:
        scraper.close()

def get_tiktok_trending_hashtags(limit=10, headless=True):
    """
    Extrait les hashtags tendance sur TikTok.
    
    Args:
        limit (int): Nombre maximum de hashtags à extraire
        headless (bool): Si True, le navigateur s'exécute en mode headless
        
    Returns:
        list: Liste de dictionnaires contenant les informations des hashtags
    """
    scraper = TikTokScraper(headless=headless)
    try:
        hashtags = scraper.extract_trending_hashtags(limit)
        return hashtags
    finally:
        scraper.close()

def get_tiktok_trending_sounds(limit=10, headless=True):
    """
    Extrait les sons tendance sur TikTok.
    
    Args:
        limit (int): Nombre maximum de sons à extraire
        headless (bool): Si True, le navigateur s'exécute en mode headless
        
    Returns:
        list: Liste de dictionnaires contenant les informations des sons
    """
    scraper = TikTokScraper(headless=headless)
    try:
        sounds = scraper.extract_trending_sounds(limit)
        return sounds
    finally:
        scraper.close()

def get_tiktok_account_stats(username, headless=True):
    """
    Récupère les statistiques d'un compte TikTok.
    
    Args:
        username (str): Nom d'utilisateur du profil TikTok (sans @)
        headless (bool): Si True, le navigateur s'exécute en mode headless
        
    Returns:
        dict: Dictionnaire contenant les statistiques du compte
    """
    scraper = TikTokScraper(headless=headless)
    try:
        stats = scraper.get_account_stats(username)
        return stats
    finally:
        scraper.close()

# Exemple d'utilisation
if __name__ == "__main__":
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Exemple d'extraction de contenu
    username = "example_username"
    posts = extract_tiktok_content(username, days_limit=7, max_posts=5)
    
    print(f"Nombre de posts extraits: {len(posts)}")
    for post in posts:
        print(f"Post: {post['url']} - Likes: {post['likes']} - Date: {post['date']}")
    
    # Exemple d'extraction des hashtags tendance
    hashtags = get_tiktok_trending_hashtags(limit=5)
    
    print(f"Nombre de hashtags tendance extraits: {len(hashtags)}")
    for hashtag in hashtags:
        print(f"Hashtag: #{hashtag['name']} - Rang: {hashtag['rank']}")
    
    # Exemple d'extraction des sons tendance
    sounds = get_tiktok_trending_sounds(limit=5)
    
    print(f"Nombre de sons tendance extraits: {len(sounds)}")
    for sound in sounds:
        print(f"Son: {sound['name']} - Rang: {sound['rank']}")
