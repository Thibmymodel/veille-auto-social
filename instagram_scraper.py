#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module de scraping Instagram pour le système de veille automatisée.
Ce module permet de collecter du contenu depuis Instagram sans utiliser l'API officielle.
"""

import os
import time
import random
import logging
import requests
import json
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
logger = logging.getLogger("instagram_scraper")

class InstagramScraper:
    """Classe pour scraper du contenu depuis Instagram."""
    
    def __init__(self, headless=True, proxy=None, retry_count=3, retry_delay=5):
        """
        Initialise le scraper Instagram.
        
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
        self.base_url = "https://www.instagram.com"
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.is_logged_in = False
        
    def _initialize_driver(self):
        """Initialise le driver Selenium pour Instagram."""
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
    
    def login(self, username, password):
        """
        Se connecte à Instagram.
        
        Args:
            username (str): Nom d'utilisateur Instagram
            password (str): Mot de passe Instagram
            
        Returns:
            bool: True si la connexion a réussi, False sinon
        """
        try:
            self._initialize_driver()
            
            # Accéder à la page de connexion
            self.driver.get(f"{self.base_url}/accounts/login/")
            time.sleep(random.uniform(2, 4))
            
            # Accepter les cookies si nécessaire
            try:
                cookie_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Allow') or contains(text(), 'Accepter')]"))
                )
                cookie_button.click()
                time.sleep(random.uniform(1, 2))
            except:
                logger.info("Pas de popup de cookies ou déjà accepté")
            
            # Remplir le formulaire de connexion
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            password_field = self.driver.find_element(By.NAME, "password")
            
            # Simuler une saisie humaine
            self._type_like_human(username_field, username)
            time.sleep(random.uniform(0.5, 1.5))
            self._type_like_human(password_field, password)
            time.sleep(random.uniform(0.5, 1.5))
            
            # Cliquer sur le bouton de connexion
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            # Attendre que la connexion soit établie
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/direct/inbox/') or contains(@href, '/explore/')]"))
            )
            
            # Gérer les popups après connexion
            self._handle_post_login_popups()
            
            logger.info("Connexion à Instagram réussie")
            self.is_logged_in = True
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la connexion à Instagram: {str(e)}")
            return False
    
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
    
    def _handle_post_login_popups(self):
        """Gère les popups qui peuvent apparaître après la connexion."""
        try:
            # Popup "Save Your Login Info"
            save_info_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Save Info') or contains(text(), 'Enregistrer')]"))
            )
            save_info_button.click()
            time.sleep(random.uniform(1, 2))
        except:
            pass
        
        try:
            # Popup "Turn on Notifications"
            not_now_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now') or contains(text(), 'Plus tard')]"))
            )
            not_now_button.click()
        except:
            pass
    
    def search_profiles(self, keywords, min_followers=10000, max_results=20):
        """
        Recherche des profils Instagram correspondant aux mots-clés.
        
        Args:
            keywords (list): Liste de mots-clés pour la recherche
            min_followers (int): Nombre minimum d'abonnés
            max_results (int): Nombre maximum de résultats à retourner
            
        Returns:
            list: Liste de dictionnaires contenant les informations des profils
        """
        profiles = []
        
        try:
            self._initialize_driver()
            
            for keyword in keywords:
                logger.info(f"Recherche de profils avec le mot-clé: {keyword}")
                
                # Accéder à la page de recherche
                self.driver.get(f"{self.base_url}/explore/search/")
                time.sleep(random.uniform(2, 4))
                
                # Saisir le mot-clé dans la barre de recherche
                search_box = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Search' or @placeholder='Rechercher']"))
                )
                search_box.clear()
                self._type_like_human(search_box, keyword)
                time.sleep(random.uniform(2, 4))
                
                # Cliquer sur les résultats de type "compte"
                try:
                    accounts_tab = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//span[text()='Accounts' or text()='Comptes']"))
                    )
                    accounts_tab.click()
                    time.sleep(random.uniform(2, 3))
                except:
                    logger.info("Onglet 'Comptes' non trouvé ou déjà sélectionné")
                
                # Récupérer les résultats
                profile_elements = self.driver.find_elements(By.XPATH, "//div[@role='none']//a[contains(@href, '/')]")
                
                for profile in profile_elements[:min(30, len(profile_elements))]:
                    try:
                        profile_url = profile.get_attribute("href")
                        if "/p/" in profile_url or "/explore/" in profile_url:
                            continue
                            
                        username = profile_url.split("/")[-2] if profile_url.endswith("/") else profile_url.split("/")[-1]
                        
                        # Visiter le profil pour obtenir plus d'informations
                        self.driver.get(profile_url)
                        time.sleep(random.uniform(3, 5))
                        
                        # Récupérer le nombre d'abonnés
                        followers_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/followers/')]//span")
                        followers_text = followers_element.text.replace(",", "").replace("k", "000").replace("m", "000000").replace(".", "")
                        followers_count = int(''.join(filter(str.isdigit, followers_text))) if any(c.isdigit() for c in followers_text) else 0
                        
                        if followers_count >= min_followers:
                            # Récupérer la bio
                            try:
                                bio_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'biography')]")
                                bio = bio_element.text
                            except:
                                bio = ""
                            
                            # Récupérer le nom complet
                            try:
                                name_element = self.driver.find_element(By.XPATH, "//h2")
                                name = name_element.text
                            except:
                                name = username
                            
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
                    
                    except Exception as e:
                        logger.error(f"Erreur lors de l'analyse du profil: {str(e)}")
                        continue
                
                if len(profiles) >= max_results:
                    break
                    
                time.sleep(random.uniform(2, 5))
            
            return profiles
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de profils Instagram: {str(e)}")
            return profiles
        
    def extract_recent_content(self, username, days_limit=14, max_posts=20):
        """
        Extrait le contenu récent d'un profil Instagram.
        
        Args:
            username (str): Nom d'utilisateur du profil Instagram
            days_limit (int): Limite en jours pour le contenu récent
            max_posts (int): Nombre maximum de posts à extraire
            
        Returns:
            list: Liste de dictionnaires contenant les informations des posts
        """
        posts = []
        
        try:
            self._initialize_driver()
            
            # Accéder au profil
            profile_url = f"{self.base_url}/{username}/"
            self.driver.get(profile_url)
            time.sleep(random.uniform(3, 5))
            
            # Vérifier si le profil est privé
            try:
                private_element = self.driver.find_element(By.XPATH, "//h2[contains(text(), 'This Account is Private') or contains(text(), 'Ce compte est privé')]")
                logger.info(f"Le profil {username} est privé")
                return posts
            except NoSuchElementException:
                pass
            
            # Récupérer les posts
            post_elements = []
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            while len(post_elements) < max_posts:
                # Récupérer tous les liens de posts visibles
                elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")
                post_elements.extend([e for e in elements if e not in post_elements])
                
                if len(post_elements) >= max_posts:
                    break
                
                # Faire défiler la page
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
                
                # Vérifier si on a atteint le bas de la page
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            
            # Limiter le nombre de posts à analyser
            post_elements = post_elements[:min(max_posts, len(post_elements))]
            
            for post_element in post_elements:
                try:
                    post_url = post_element.get_attribute("href")
                    
                    # Visiter la page du post
                    self.driver.get(post_url)
                    time.sleep(random.uniform(2, 4))
                    
                    # Récupérer la date du post
                    time_element = self.driver.find_element(By.XPATH, "//time")
                    post_date_str = time_element.get_attribute("datetime")
                    post_date = post_date_str.split("T")[0]  # Format YYYY-MM-DD
                    
                    # Vérifier si le post est dans la limite de jours
                    post_datetime = datetime.strptime(post_date, "%Y-%m-%d")
                    days_ago = (datetime.now() - post_datetime).days
                    
                    if days_ago > days_limit:
                        continue
                    
                    # Déterminer le type de post (photo, vidéo, carousel)
                    post_type = "photo"  # Par défaut
                    
                    try:
                        video_element = self.driver.find_element(By.XPATH, "//video")
                        post_type = "video"
                    except NoSuchElementException:
                        pass
                    
                    try:
                        carousel_element = self.driver.find_element(By.XPATH, "//button[contains(@aria-label, 'Next') or contains(@aria-label, 'Suivant')]")
                        post_type = "carousel"
                    except NoSuchElementException:
                        pass
                    
                    # Récupérer l'URL de l'image ou de la vidéo
                    media_url = ""
                    if post_type == "photo":
                        img_element = self.driver.find_element(By.XPATH, "//article//img[not(contains(@alt, 'profile picture'))]")
                        media_url = img_element.get_attribute("src")
                    elif post_type == "video":
                        video_element = self.driver.find_element(By.XPATH, "//video")
                        media_url = video_element.get_attribute("src") or video_element.get_attribute("poster")
                    else:  # carousel
                        img_element = self.driver.find_element(By.XPATH, "//article//img[not(contains(@alt, 'profile picture'))]")
                        media_url = img_element.get_attribute("src")
                    
                    # Récupérer le nombre de likes
                    likes_count = 0
                    try:
                        likes_element = self.driver.find_element(By.XPATH, "//section//a[contains(@href, '/liked_by/')]")
                        likes_text = likes_element.text.replace(",", "").replace("likes", "").replace("like", "").strip()
                        likes_count = int(''.join(filter(str.isdigit, likes_text))) if any(c.isdigit() for c in likes_text) else 0
                    except:
                        # Essayer une autre méthode
                        try:
                            likes_element = self.driver.find_element(By.XPATH, "//section//span[contains(text(), 'like') or contains(text(), 'j'aime')]")
                            likes_text = likes_element.text.replace(",", "").replace("likes", "").replace("like", "").replace("j'aime", "").strip()
                            likes_count = int(''.join(filter(str.isdigit, likes_text))) if any(c.isdigit() for c in likes_text) else 0
                        except:
                            pass
                    
                    # Récupérer le nombre de commentaires
                    comments_count = 0
                    try:
                        comments_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'comment') or contains(text(), 'commentaire')]")
                        comments_text = comments_element.text.replace(",", "").replace("comments", "").replace("comment", "").replace("commentaires", "").replace("commentaire", "").strip()
                        comments_count = int(''.join(filter(str.isdigit, comments_text))) if any(c.isdigit() for c in comments_text) else 0
                    except:
                        pass
                    
                    # Récupérer la description
                    caption = ""
                    try:
                        caption_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'caption')]//span")
                        caption = caption_element.text
                    except:
                        pass
                    
                    # Vérifier si le post contient de la musique (important pour les critères de sélection)
                    has_music = False
                    try:
                        music_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/music/')]")
                        has_music = True
                    except:
                        pass
                    
                    # Vérifier si le post contient des sous-titres visibles (important pour Lizz)
                    has_captions = False
                    try:
                        captions_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'caption')]//span[contains(text(), '[') and contains(text(), ']')]")
                        has_captions = True
                    except:
                        pass
                    
                    # Ajouter le post à la liste
                    posts.append({
                        "type": post_type,
                        "url": post_url,
                        "media_url": media_url,
                        "date": post_date,
                        "days_ago": days_ago,
                        "likes": likes_count,
                        "comments": comments_count,
                        "caption": caption,
                        "has_music": has_music,
                        "has_captions": has_captions,
                        "platform": "instagram",
                        "username": username
                    })
                    
                    logger.info(f"Post extrait: {post_url} ({post_type}) - {likes_count} likes, {days_ago} jours")
                    
                except Exception as e:
                    logger.error(f"Erreur lors de l'analyse du post: {str(e)}")
                    continue
                
                time.sleep(random.uniform(1, 3))
            
            return posts
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction du contenu Instagram: {str(e)}")
            return posts
    
    def extract_reels(self, username, days_limit=14, max_reels=10):
        """
        Extrait spécifiquement les réels d'un profil Instagram.
        
        Args:
            username (str): Nom d'utilisateur du profil Instagram
            days_limit (int): Limite en jours pour les réels récents
            max_reels (int): Nombre maximum de réels à extraire
            
        Returns:
            list: Liste de dictionnaires contenant les informations des réels
        """
        reels = []
        
        try:
            self._initialize_driver()
            
            # Accéder à l'onglet Reels du profil
            reels_url = f"{self.base_url}/{username}/reels/"
            self.driver.get(reels_url)
            time.sleep(random.uniform(3, 5))
            
            # Vérifier si le profil est privé
            try:
                private_element = self.driver.find_element(By.XPATH, "//h2[contains(text(), 'This Account is Private') or contains(text(), 'Ce compte est privé')]")
                logger.info(f"Le profil {username} est privé")
                return reels
            except NoSuchElementException:
                pass
            
            # Récupérer les réels
            reel_elements = []
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            while len(reel_elements) < max_reels:
                # Récupérer tous les liens de réels visibles
                elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/')]")
                reel_elements.extend([e for e in elements if e not in reel_elements])
                
                if len(reel_elements) >= max_reels:
                    break
                
                # Faire défiler la page
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
                
                # Vérifier si on a atteint le bas de la page
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            
            # Limiter le nombre de réels à analyser
            reel_elements = reel_elements[:min(max_reels, len(reel_elements))]
            
            # Calculer la moyenne des vues pour ce compte
            avg_views = self._calculate_average_reel_views(username, reel_elements[:min(5, len(reel_elements))])
            
            for reel_element in reel_elements:
                try:
                    reel_url = reel_element.get_attribute("href")
                    
                    # Visiter la page du réel
                    self.driver.get(reel_url)
                    time.sleep(random.uniform(2, 4))
                    
                    # Récupérer la date du réel
                    time_element = self.driver.find_element(By.XPATH, "//time")
                    reel_date_str = time_element.get_attribute("datetime")
                    reel_date = reel_date_str.split("T")[0]  # Format YYYY-MM-DD
                    
                    # Vérifier si le réel est dans la limite de jours
                    reel_datetime = datetime.strptime(reel_date, "%Y-%m-%d")
                    days_ago = (datetime.now() - reel_datetime).days
                    
                    if days_ago > days_limit:
                        continue
                    
                    # Récupérer le nombre de vues
                    views_count = 0
                    try:
                        views_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'views') or contains(text(), 'vues')]")
                        views_text = views_element.text.replace(",", "").replace("views", "").replace("view", "").replace("vues", "").replace("vue", "").strip()
                        views_count = int(''.join(filter(str.isdigit, views_text))) if any(c.isdigit() for c in views_text) else 0
                        
                        # Convertir K et M en nombres
                        if "k" in views_text.lower():
                            views_count *= 1000
                        elif "m" in views_text.lower():
                            views_count *= 1000000
                    except:
                        pass
                    
                    # Récupérer le nombre de likes
                    likes_count = 0
                    try:
                        likes_element = self.driver.find_element(By.XPATH, "//section//a[contains(@href, '/liked_by/')]")
                        likes_text = likes_element.text.replace(",", "").replace("likes", "").replace("like", "").strip()
                        likes_count = int(''.join(filter(str.isdigit, likes_text))) if any(c.isdigit() for c in likes_text) else 0
                    except:
                        # Essayer une autre méthode
                        try:
                            likes_element = self.driver.find_element(By.XPATH, "//section//span[contains(text(), 'like') or contains(text(), 'j'aime')]")
                            likes_text = likes_element.text.replace(",", "").replace("likes", "").replace("like", "").replace("j'aime", "").strip()
                            likes_count = int(''.join(filter(str.isdigit, likes_text))) if any(c.isdigit() for c in likes_text) else 0
                        except:
                            pass
                    
                    # Récupérer le nombre de commentaires
                    comments_count = 0
                    try:
                        comments_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'comment') or contains(text(), 'commentaire')]")
                        comments_text = comments_element.text.replace(",", "").replace("comments", "").replace("comment", "").replace("commentaires", "").replace("commentaire", "").strip()
                        comments_count = int(''.join(filter(str.isdigit, comments_text))) if any(c.isdigit() for c in comments_text) else 0
                    except:
                        pass
                    
                    # Récupérer la description
                    caption = ""
                    try:
                        caption_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'caption')]//span")
                        caption = caption_element.text
                    except:
                        pass
                    
                    # Vérifier si le réel contient de la musique
                    has_music = False
                    music_title = ""
                    try:
                        music_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/music/')]")
                        has_music = True
                        music_title = music_element.text
                    except:
                        pass
                    
                    # Vérifier si la personne parle face caméra (important pour Lizz)
                    is_speaking = False
                    try:
                        # Rechercher des indices dans la description
                        speaking_keywords = ["je vous parle", "je parle", "je vous explique", "face caméra", "facecam"]
                        is_speaking = any(keyword in caption.lower() for keyword in speaking_keywords)
                    except:
                        pass
                    
                    # Vérifier si le réel contient des sous-titres visibles (important pour Lizz)
                    has_captions = False
                    try:
                        captions_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'caption')]//span[contains(text(), '[') and contains(text(), ']')]")
                        has_captions = True
                    except:
                        pass
                    
                    # Calculer le ratio de performance par rapport à la moyenne
                    performance_ratio = views_count / avg_views if avg_views > 0 else 0
                    
                    # Ajouter le réel à la liste
                    reels.append({
                        "type": "reel",
                        "url": reel_url,
                        "date": reel_date,
                        "days_ago": days_ago,
                        "views": views_count,
                        "likes": likes_count,
                        "comments": comments_count,
                        "caption": caption,
                        "has_music": has_music,
                        "music_title": music_title,
                        "is_speaking": is_speaking,
                        "has_captions": has_captions,
                        "performance_ratio": performance_ratio,
                        "avg_views": avg_views,
                        "platform": "instagram",
                        "username": username
                    })
                    
                    logger.info(f"Réel extrait: {reel_url} - {views_count} vues, ratio: {performance_ratio:.2f}, {days_ago} jours")
                    
                except Exception as e:
                    logger.error(f"Erreur lors de l'analyse du réel: {str(e)}")
                    continue
                
                time.sleep(random.uniform(1, 3))
            
            # Trier les réels par ratio de performance
            reels.sort(key=lambda x: x["performance_ratio"], reverse=True)
            
            return reels
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des réels Instagram: {str(e)}")
            return reels
    
    def _calculate_average_reel_views(self, username, reel_elements, sample_size=5):
        """
        Calcule la moyenne des vues pour les réels d'un compte.
        
        Args:
            username (str): Nom d'utilisateur du profil Instagram
            reel_elements (list): Liste des éléments de réels
            sample_size (int): Nombre de réels à analyser pour la moyenne
            
        Returns:
            float: Moyenne des vues
        """
        views_list = []
        
        # Valeurs par défaut selon les spécifications
        default_values = {
            "talia": 4000,
            "léa": 3000,
            "lizz": 3500
        }
        
        # Utiliser une valeur par défaut si le nom d'utilisateur correspond
        for model_name, default_views in default_values.items():
            if model_name.lower() in username.lower():
                logger.info(f"Utilisation de la valeur par défaut pour {username}: {default_views} vues")
                return default_views
        
        # Si pas assez d'éléments ou erreur, retourner une valeur par défaut
        if not reel_elements or len(reel_elements) == 0:
            logger.warning(f"Pas assez de réels pour calculer la moyenne pour {username}, utilisation de la valeur par défaut: 3000")
            return 3000
        
        # Limiter le nombre de réels à analyser
        sample_elements = reel_elements[:min(sample_size, len(reel_elements))]
        
        for reel_element in sample_elements:
            try:
                reel_url = reel_element.get_attribute("href")
                
                # Visiter la page du réel
                self.driver.get(reel_url)
                time.sleep(random.uniform(2, 3))
                
                # Récupérer le nombre de vues
                try:
                    views_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'views') or contains(text(), 'vues')]")
                    views_text = views_element.text.replace(",", "").replace("views", "").replace("view", "").replace("vues", "").replace("vue", "").strip()
                    views_count = int(''.join(filter(str.isdigit, views_text))) if any(c.isdigit() for c in views_text) else 0
                    
                    # Convertir K et M en nombres
                    if "k" in views_text.lower():
                        views_count *= 1000
                    elif "m" in views_text.lower():
                        views_count *= 1000000
                    
                    if views_count > 0:
                        views_list.append(views_count)
                except:
                    pass
                
            except Exception as e:
                logger.error(f"Erreur lors du calcul de la moyenne des vues: {str(e)}")
                continue
        
        # Calculer la moyenne
        if views_list:
            avg_views = sum(views_list) / len(views_list)
            logger.info(f"Moyenne des vues calculée pour {username}: {avg_views:.2f} vues")
            return avg_views
        else:
            logger.warning(f"Impossible de calculer la moyenne des vues pour {username}, utilisation de la valeur par défaut: 3000")
            return 3000
    
    def analyze_engagement(self, post_url):
        """
        Analyse l'engagement d'un post Instagram.
        
        Args:
            post_url (str): URL du post Instagram
            
        Returns:
            dict: Dictionnaire contenant les métriques d'engagement
        """
        engagement = {
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "saves": 0,
            "views": 0,
            "engagement_rate": 0.0
        }
        
        try:
            self._initialize_driver()
            
            # Accéder au post
            self.driver.get(post_url)
            time.sleep(random.uniform(2, 4))
            
            # Récupérer le nombre de likes
            try:
                likes_element = self.driver.find_element(By.XPATH, "//section//a[contains(@href, '/liked_by/')]")
                likes_text = likes_element.text.replace(",", "").replace("likes", "").replace("like", "").strip()
                engagement["likes"] = int(''.join(filter(str.isdigit, likes_text))) if any(c.isdigit() for c in likes_text) else 0
            except:
                # Essayer une autre méthode
                try:
                    likes_element = self.driver.find_element(By.XPATH, "//section//span[contains(text(), 'like') or contains(text(), 'j'aime')]")
                    likes_text = likes_element.text.replace(",", "").replace("likes", "").replace("like", "").replace("j'aime", "").strip()
                    engagement["likes"] = int(''.join(filter(str.isdigit, likes_text))) if any(c.isdigit() for c in likes_text) else 0
                except:
                    pass
            
            # Récupérer le nombre de commentaires
            try:
                comments_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'comment') or contains(text(), 'commentaire')]")
                comments_text = comments_element.text.replace(",", "").replace("comments", "").replace("comment", "").replace("commentaires", "").replace("commentaire", "").strip()
                engagement["comments"] = int(''.join(filter(str.isdigit, comments_text))) if any(c.isdigit() for c in comments_text) else 0
            except:
                pass
            
            # Récupérer le nombre de vues (pour les vidéos et réels)
            try:
                views_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'views') or contains(text(), 'vues')]")
                views_text = views_element.text.replace(",", "").replace("views", "").replace("view", "").replace("vues", "").replace("vue", "").strip()
                views_count = int(''.join(filter(str.isdigit, views_text))) if any(c.isdigit() for c in views_text) else 0
                
                # Convertir K et M en nombres
                if "k" in views_text.lower():
                    views_count *= 1000
                elif "m" in views_text.lower():
                    views_count *= 1000000
                
                engagement["views"] = views_count
            except:
                pass
            
            # Récupérer le nombre d'abonnés pour calculer le taux d'engagement
            try:
                # Extraire le nom d'utilisateur de l'URL du post
                username = post_url.split("/p/")[0].split("/")[-1]
                if not username and "/reel/" in post_url:
                    username = post_url.split("/reel/")[0].split("/")[-1]
                
                # Accéder au profil
                self.driver.get(f"{self.base_url}/{username}/")
                time.sleep(random.uniform(2, 3))
                
                # Récupérer le nombre d'abonnés
                followers_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/followers/')]//span")
                followers_text = followers_element.text.replace(",", "").replace("k", "000").replace("m", "000000").replace(".", "")
                followers_count = int(''.join(filter(str.isdigit, followers_text))) if any(c.isdigit() for c in followers_text) else 0
                
                if followers_count > 0:
                    # Calculer le taux d'engagement (likes + commentaires) / abonnés * 100
                    engagement["engagement_rate"] = round((engagement["likes"] + engagement["comments"]) / followers_count * 100, 2)
            except:
                pass
            
            return engagement
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse de l'engagement: {str(e)}")
            return engagement
    
    def get_account_stats(self, username):
        """
        Récupère les statistiques d'un compte Instagram.
        
        Args:
            username (str): Nom d'utilisateur du profil Instagram
            
        Returns:
            dict: Dictionnaire contenant les statistiques du compte
        """
        stats = {
            "username": username,
            "followers": 0,
            "following": 0,
            "posts_count": 0,
            "avg_likes": 0,
            "avg_comments": 0,
            "avg_views": 0,
            "engagement_rate": 0.0,
            "bio": "",
            "website": "",
            "is_private": False
        }
        
        try:
            self._initialize_driver()
            
            # Accéder au profil
            profile_url = f"{self.base_url}/{username}/"
            self.driver.get(profile_url)
            time.sleep(random.uniform(3, 5))
            
            # Vérifier si le profil est privé
            try:
                private_element = self.driver.find_element(By.XPATH, "//h2[contains(text(), 'This Account is Private') or contains(text(), 'Ce compte est privé')]")
                stats["is_private"] = True
                logger.info(f"Le profil {username} est privé")
            except NoSuchElementException:
                pass
            
            # Récupérer le nombre d'abonnés
            try:
                followers_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/followers/')]//span")
                followers_text = followers_element.text.replace(",", "").replace("k", "000").replace("m", "000000").replace(".", "")
                stats["followers"] = int(''.join(filter(str.isdigit, followers_text))) if any(c.isdigit() for c in followers_text) else 0
            except:
                pass
            
            # Récupérer le nombre d'abonnements
            try:
                following_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/following/')]//span")
                following_text = following_element.text.replace(",", "").replace("k", "000").replace("m", "000000").replace(".", "")
                stats["following"] = int(''.join(filter(str.isdigit, following_text))) if any(c.isdigit() for c in following_text) else 0
            except:
                pass
            
            # Récupérer le nombre de posts
            try:
                posts_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'post') or contains(text(), 'publication')]")
                posts_text = posts_element.text.replace(",", "").replace("posts", "").replace("post", "").replace("publications", "").replace("publication", "").strip()
                stats["posts_count"] = int(''.join(filter(str.isdigit, posts_text))) if any(c.isdigit() for c in posts_text) else 0
            except:
                pass
            
            # Récupérer la bio
            try:
                bio_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'biography')]")
                stats["bio"] = bio_element.text
            except:
                pass
            
            # Récupérer le site web
            try:
                website_element = self.driver.find_element(By.XPATH, "//a[contains(@href, 'http') and not(contains(@href, 'instagram.com'))]")
                stats["website"] = website_element.get_attribute("href")
            except:
                pass
            
            # Si le profil n'est pas privé, calculer les moyennes d'engagement
            if not stats["is_private"]:
                # Récupérer quelques posts pour calculer les moyennes
                post_elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")[:5]
                
                likes_list = []
                comments_list = []
                views_list = []
                
                for post_element in post_elements:
                    try:
                        post_url = post_element.get_attribute("href")
                        
                        # Visiter la page du post
                        self.driver.get(post_url)
                        time.sleep(random.uniform(2, 3))
                        
                        # Récupérer le nombre de likes
                        try:
                            likes_element = self.driver.find_element(By.XPATH, "//section//a[contains(@href, '/liked_by/')]")
                            likes_text = likes_element.text.replace(",", "").replace("likes", "").replace("like", "").strip()
                            likes_count = int(''.join(filter(str.isdigit, likes_text))) if any(c.isdigit() for c in likes_text) else 0
                            likes_list.append(likes_count)
                        except:
                            # Essayer une autre méthode
                            try:
                                likes_element = self.driver.find_element(By.XPATH, "//section//span[contains(text(), 'like') or contains(text(), 'j'aime')]")
                                likes_text = likes_element.text.replace(",", "").replace("likes", "").replace("like", "").replace("j'aime", "").strip()
                                likes_count = int(''.join(filter(str.isdigit, likes_text))) if any(c.isdigit() for c in likes_text) else 0
                                likes_list.append(likes_count)
                            except:
                                pass
                        
                        # Récupérer le nombre de commentaires
                        try:
                            comments_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'comment') or contains(text(), 'commentaire')]")
                            comments_text = comments_element.text.replace(",", "").replace("comments", "").replace("comment", "").replace("commentaires", "").replace("commentaire", "").strip()
                            comments_count = int(''.join(filter(str.isdigit, comments_text))) if any(c.isdigit() for c in comments_text) else 0
                            comments_list.append(comments_count)
                        except:
                            pass
                        
                        # Récupérer le nombre de vues (pour les vidéos)
                        try:
                            views_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'views') or contains(text(), 'vues')]")
                            views_text = views_element.text.replace(",", "").replace("views", "").replace("view", "").replace("vues", "").replace("vue", "").strip()
                            views_count = int(''.join(filter(str.isdigit, views_text))) if any(c.isdigit() for c in views_text) else 0
                            
                            # Convertir K et M en nombres
                            if "k" in views_text.lower():
                                views_count *= 1000
                            elif "m" in views_text.lower():
                                views_count *= 1000000
                            
                            views_list.append(views_count)
                        except:
                            pass
                        
                    except Exception as e:
                        logger.error(f"Erreur lors de l'analyse du post pour les statistiques: {str(e)}")
                        continue
                
                # Calculer les moyennes
                if likes_list:
                    stats["avg_likes"] = sum(likes_list) / len(likes_list)
                
                if comments_list:
                    stats["avg_comments"] = sum(comments_list) / len(comments_list)
                
                if views_list:
                    stats["avg_views"] = sum(views_list) / len(views_list)
                
                # Calculer le taux d'engagement moyen
                if stats["followers"] > 0 and likes_list and comments_list:
                    avg_engagement = (stats["avg_likes"] + stats["avg_comments"]) / stats["followers"] * 100
                    stats["engagement_rate"] = round(avg_engagement, 2)
            
            return stats
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques du compte: {str(e)}")
            return stats
    
    def close(self):
        """Ferme le scraper et libère les ressources."""
        self._close_driver()
        self.session.close()

# Fonctions pour utilisation directe
def extract_instagram_content(username, days_limit=14, max_posts=20, headless=True):
    """
    Extrait le contenu récent d'un profil Instagram.
    
    Args:
        username (str): Nom d'utilisateur du profil Instagram
        days_limit (int): Limite en jours pour le contenu récent
        max_posts (int): Nombre maximum de posts à extraire
        headless (bool): Si True, le navigateur s'exécute en mode headless
        
    Returns:
        list: Liste de dictionnaires contenant les informations des posts
    """
    scraper = InstagramScraper(headless=headless)
    try:
        posts = scraper.extract_recent_content(username, days_limit, max_posts)
        return posts
    finally:
        scraper.close()

def extract_instagram_reels(username, days_limit=14, max_reels=10, headless=True):
    """
    Extrait spécifiquement les réels d'un profil Instagram.
    
    Args:
        username (str): Nom d'utilisateur du profil Instagram
        days_limit (int): Limite en jours pour les réels récents
        max_reels (int): Nombre maximum de réels à extraire
        headless (bool): Si True, le navigateur s'exécute en mode headless
        
    Returns:
        list: Liste de dictionnaires contenant les informations des réels
    """
    scraper = InstagramScraper(headless=headless)
    try:
        reels = scraper.extract_reels(username, days_limit, max_reels)
        return reels
    finally:
        scraper.close()

def get_instagram_account_stats(username, headless=True):
    """
    Récupère les statistiques d'un compte Instagram.
    
    Args:
        username (str): Nom d'utilisateur du profil Instagram
        headless (bool): Si True, le navigateur s'exécute en mode headless
        
    Returns:
        dict: Dictionnaire contenant les statistiques du compte
    """
    scraper = InstagramScraper(headless=headless)
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
    posts = extract_instagram_content(username, days_limit=7, max_posts=5)
    
    print(f"Nombre de posts extraits: {len(posts)}")
    for post in posts:
        print(f"Post: {post['url']} - Type: {post['type']} - Likes: {post['likes']} - Date: {post['date']}")
    
    # Exemple d'extraction de réels
    reels = extract_instagram_reels(username, days_limit=14, max_reels=5)
    
    print(f"Nombre de réels extraits: {len(reels)}")
    for reel in reels:
        print(f"Réel: {reel['url']} - Vues: {reel['views']} - Ratio: {reel['performance_ratio']:.2f} - Date: {reel['date']}")
