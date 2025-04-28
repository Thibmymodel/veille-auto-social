#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module de scraping Threads pour le système de veille automatisée.
Ce module permet de collecter du contenu depuis Threads sans utiliser l'API officielle.
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
logger = logging.getLogger("threads_scraper")

class ThreadsScraper:
    """Classe pour scraper du contenu depuis Threads."""
    
    def __init__(self, headless=True, proxy=None, retry_count=3, retry_delay=5):
        """
        Initialise le scraper Threads.
        
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
        self.threads_url = "https://www.threads.net"
        
    def _initialize_driver(self):
        """Initialise le driver Selenium pour Threads."""
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
    
    def login(self, username, password):
        """
        Se connecte à Threads via Instagram.
        
        Args:
            username (str): Nom d'utilisateur Instagram
            password (str): Mot de passe Instagram
            
        Returns:
            bool: True si la connexion a réussi, False sinon
        """
        try:
            self._initialize_driver()
            
            # Accéder à la page d'accueil de Threads
            self.driver.get(self.threads_url)
            time.sleep(random.uniform(2, 4))
            
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
            
            # Remplir le formulaire de connexion Instagram
            try:
                username_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@name='username']"))
                )
                self._type_like_human(username_field, username)
                time.sleep(random.uniform(0.5, 1.5))
                
                password_field = self.driver.find_element(By.XPATH, "//input[@name='password']")
                self._type_like_human(password_field, password)
                time.sleep(random.uniform(0.5, 1.5))
                
                # Cliquer sur Se connecter
                submit_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
                submit_button.click()
                
                # Attendre que la connexion soit établie
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'x1n2onr6')]"))
                )
                
                logger.info("Connexion à Threads réussie")
                self.is_logged_in = True
                return True
            except Exception as e:
                logger.error(f"Erreur lors de la connexion à Threads: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de la connexion à Threads: {str(e)}")
            return False
    
    def search_profiles(self, keywords, min_followers=10000, max_results=20):
        """
        Recherche des profils Threads correspondant aux mots-clés.
        
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
                search_url = f"{self.threads_url}/search/"
                self.driver.get(search_url)
                time.sleep(random.uniform(3, 5))
                
                # Saisir le mot-clé dans la barre de recherche
                try:
                    search_input = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Search' or @placeholder='Rechercher']"))
                    )
                    self._type_like_human(search_input, keyword)
                    time.sleep(random.uniform(2, 3))
                    
                    # Attendre les résultats de recherche
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'x1n2onr6')]//a[contains(@href, '@')]"))
                    )
                    
                    # Récupérer les résultats
                    profile_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'x1n2onr6')]//a[contains(@href, '@')]")
                    
                    for profile in profile_elements[:min(30, len(profile_elements))]:
                        try:
                            profile_url = profile.get_attribute("href")
                            username = profile_url.split("@")[-1].split("/")[0]
                            
                            # Visiter le profil pour obtenir plus d'informations
                            self.driver.get(profile_url)
                            time.sleep(random.uniform(2, 4))
                            
                            # Récupérer le nombre d'abonnés
                            try:
                                followers_element = WebDriverWait(self.driver, 5).until(
                                    EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'followers') or contains(text(), 'abonnés')]"))
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
                                # Récupérer le nom complet
                                try:
                                    name_element = self.driver.find_element(By.XPATH, "//h2[contains(@class, 'x1lliihq')]")
                                    name = name_element.text
                                except:
                                    name = username
                                
                                # Récupérer la bio
                                try:
                                    bio_element = self.driver.find_element(By.XPATH, "//h1[contains(@class, 'x1lliihq')]/following-sibling::div")
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
                        
                        except Exception as e:
                            logger.error(f"Erreur lors de l'analyse du profil: {str(e)}")
                            continue
                    
                    if len(profiles) >= max_results:
                        break
                        
                except Exception as e:
                    logger.error(f"Erreur lors de la recherche avec le mot-clé {keyword}: {str(e)}")
                    continue
                
                time.sleep(random.uniform(2, 5))
            
            return profiles
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de profils Threads: {str(e)}")
            return profiles
        
    def extract_recent_content(self, username, days_limit=14, max_posts=20):
        """
        Extrait le contenu récent d'un profil Threads.
        
        Args:
            username (str): Nom d'utilisateur du profil Threads (sans @)
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
            profile_url = f"{self.threads_url}/@{username}"
            self.driver.get(profile_url)
            time.sleep(random.uniform(3, 5))
            
            # Vérifier si le profil est privé
            try:
                private_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'This account is private') or contains(text(), 'Ce compte est privé')]")
                logger.info(f"Le profil {username} est privé")
                return posts
            except NoSuchElementException:
                pass
            
            # Récupérer les threads
            thread_elements = []
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            while len(thread_elements) < max_posts:
                # Récupérer tous les threads visibles
                elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'x1n2onr6')]//article")
                
                thread_elements.extend([e for e in elements if e not in thread_elements])
                
                if len(thread_elements) >= max_posts:
                    break
                
                # Faire défiler la page
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
                
                # Vérifier si on a atteint le bas de la page
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            
            # Limiter le nombre de threads à analyser
            thread_elements = thread_elements[:min(max_posts, len(thread_elements))]
            
            for thread_element in thread_elements:
                try:
                    # Récupérer l'URL du thread
                    thread_link = thread_element.find_element(By.XPATH, ".//a[contains(@href, '/t/')]")
                    thread_url = thread_link.get_attribute("href")
                    
                    # Récupérer la date du thread (Threads n'affiche pas la date exacte sur la page de profil)
                    # On va visiter le thread pour obtenir plus d'informations
                    self.driver.get(thread_url)
                    time.sleep(random.uniform(2, 3))
                    
                    # Récupérer la date du thread
                    try:
                        date_element = self.driver.find_element(By.XPATH, "//time")
                        date_text = date_element.get_attribute("datetime")  # Format: "YYYY-MM-DDTHH:MM:SS.000Z"
                        
                        # Convertir la date en format YYYY-MM-DD
                        thread_date = datetime.strptime(date_text.split("T")[0], "%Y-%m-%d")
                        post_date = thread_date.strftime("%Y-%m-%d")
                        days_ago = (datetime.now() - thread_date).days
                    except:
                        # Si on ne peut pas récupérer la date, on suppose qu'elle est récente
                        post_date = datetime.now().strftime("%Y-%m-%d")
                        days_ago = 0
                    
                    if days_ago > days_limit:
                        # Revenir à la page de profil
                        self.driver.get(profile_url)
                        time.sleep(random.uniform(2, 3))
                        continue
                    
                    # Déterminer le type de thread (texte, photo, vidéo)
                    post_type = "text"  # Par défaut
                    media_url = ""
                    
                    try:
                        img_element = self.driver.find_element(By.XPATH, "//article//img[not(contains(@alt, 'profile picture'))]")
                        post_type = "photo"
                        media_url = img_element.get_attribute("src")
                    except NoSuchElementException:
                        try:
                            video_element = self.driver.find_element(By.XPATH, "//article//video")
                            post_type = "video"
                            media_url = video_element.get_attribute("poster") or ""
                        except NoSuchElementException:
                            pass
                    
                    # Récupérer le texte du thread
                    try:
                        text_element = self.driver.find_element(By.XPATH, "//article//div[contains(@class, 'x1lliihq')]")
                        thread_text = text_element.text
                    except:
                        thread_text = ""
                    
                    # Récupérer les statistiques du thread
                    likes = 0
                    replies = 0
                    
                    try:
                        likes_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'likes') or contains(text(), 'j'aime')]")
                        likes_text = likes_element.text.replace(",", "").replace(".", "").strip()
                        likes = int(''.join(filter(str.isdigit, likes_text))) if any(c.isdigit() for c in likes_text) else 0
                        
                        if "K" in likes_text or "k" in likes_text:
                            likes *= 1000
                        elif "M" in likes_text or "m" in likes_text:
                            likes *= 1000000
                    except:
                        pass
                    
                    try:
                        replies_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'replies') or contains(text(), 'réponses')]")
                        replies_text = replies_element.text.replace(",", "").replace(".", "").strip()
                        replies = int(''.join(filter(str.isdigit, replies_text))) if any(c.isdigit() for c in replies_text) else 0
                        
                        if "K" in replies_text or "k" in replies_text:
                            replies *= 1000
                        elif "M" in replies_text or "m" in replies_text:
                            replies *= 1000000
                    except:
                        pass
                    
                    # Vérifier si le thread contient des sous-titres (important pour Lizz)
                    has_captions = False
                    if "[" in thread_text and "]" in thread_text:
                        has_captions = True
                    
                    # Vérifier si le thread mentionne que la personne parle (important pour Lizz)
                    is_speaking = False
                    speaking_keywords = ["je vous parle", "je parle", "je vous explique", "face caméra", "facecam"]
                    if any(keyword in thread_text.lower() for keyword in speaking_keywords):
                        is_speaking = True
                    
                    # Vérifier si le thread contient de la musique (important pour Talia et Léa)
                    has_music = False
                    music_keywords = ["musique", "music", "song", "chanson", "écouter", "listen"]
                    if any(keyword in thread_text.lower() for keyword in music_keywords):
                        has_music = True
                    
                    # Calculer le score d'engagement
                    engagement_score = likes + replies * 2
                    
                    # Ajouter le thread à la liste
                    posts.append({
                        "type": post_type,
                        "url": thread_url,
                        "media_url": media_url,
                        "date": post_date,
                        "days_ago": days_ago,
                        "text": thread_text,
                        "likes": likes,
                        "replies": replies,
                        "engagement_score": engagement_score,
                        "has_captions": has_captions,
                        "is_speaking": is_speaking,
                        "has_music": has_music,
                        "platform": "threads",
                        "username": username
                    })
                    
                    logger.info(f"Thread extrait: {thread_url} ({post_type}) - {likes} likes, {days_ago} jours")
                    
                    # Revenir à la page de profil
                    self.driver.get(profile_url)
                    time.sleep(random.uniform(2, 3))
                    
                except Exception as e:
                    logger.error(f"Erreur lors de l'analyse du thread: {str(e)}")
                    continue
            
            # Trier les threads par score d'engagement
            posts.sort(key=lambda x: x["engagement_score"], reverse=True)
            
            return posts
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction du contenu Threads: {str(e)}")
            return posts
    
    def extract_videos(self, username, days_limit=14, max_videos=10):
        """
        Extrait spécifiquement les vidéos d'un profil Threads.
        
        Args:
            username (str): Nom d'utilisateur du profil Threads (sans @)
            days_limit (int): Limite en jours pour les vidéos récentes
            max_videos (int): Nombre maximum de vidéos à extraire
            
        Returns:
            list: Liste de dictionnaires contenant les informations des vidéos
        """
        return self._retry_on_failure(self._extract_videos, username, days_limit, max_videos)
    
    def _extract_videos(self, username, days_limit=14, max_videos=10):
        """
        Implémentation interne de l'extraction de vidéos.
        """
        videos = []
        
        try:
            self._initialize_driver()
            
            # Accéder au profil
            profile_url = f"{self.threads_url}/@{username}"
            self.driver.get(profile_url)
            time.sleep(random.uniform(3, 5))
            
            # Vérifier si le profil est privé
            try:
                private_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'This account is private') or contains(text(), 'Ce compte est privé')]")
                logger.info(f"Le profil {username} est privé")
                return videos
            except NoSuchElementException:
                pass
            
            # Récupérer les threads
            thread_elements = []
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            while len(videos) < max_videos:
                # Récupérer tous les threads visibles
                elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'x1n2onr6')]//article")
                
                for element in elements:
                    if element not in thread_elements:
                        thread_elements.append(element)
                        
                        # Vérifier si le thread contient une vidéo
                        try:
                            video_element = element.find_element(By.XPATH, ".//video")
                            
                            # Récupérer l'URL du thread
                            thread_link = element.find_element(By.XPATH, ".//a[contains(@href, '/t/')]")
                            thread_url = thread_link.get_attribute("href")
                            
                            # Visiter le thread pour obtenir plus d'informations
                            self.driver.get(thread_url)
                            time.sleep(random.uniform(2, 3))
                            
                            # Récupérer la date du thread
                            try:
                                date_element = self.driver.find_element(By.XPATH, "//time")
                                date_text = date_element.get_attribute("datetime")  # Format: "YYYY-MM-DDTHH:MM:SS.000Z"
                                
                                # Convertir la date en format YYYY-MM-DD
                                thread_date = datetime.strptime(date_text.split("T")[0], "%Y-%m-%d")
                                post_date = thread_date.strftime("%Y-%m-%d")
                                days_ago = (datetime.now() - thread_date).days
                            except:
                                # Si on ne peut pas récupérer la date, on suppose qu'elle est récente
                                post_date = datetime.now().strftime("%Y-%m-%d")
                                days_ago = 0
                            
                            if days_ago <= days_limit:
                                # Récupérer l'URL de la vidéo
                                video_element = self.driver.find_element(By.XPATH, "//article//video")
                                media_url = video_element.get_attribute("poster") or ""
                                
                                # Récupérer le texte du thread
                                try:
                                    text_element = self.driver.find_element(By.XPATH, "//article//div[contains(@class, 'x1lliihq')]")
                                    thread_text = text_element.text
                                except:
                                    thread_text = ""
                                
                                # Récupérer les statistiques du thread
                                likes = 0
                                replies = 0
                                
                                try:
                                    likes_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'likes') or contains(text(), 'j'aime')]")
                                    likes_text = likes_element.text.replace(",", "").replace(".", "").strip()
                                    likes = int(''.join(filter(str.isdigit, likes_text))) if any(c.isdigit() for c in likes_text) else 0
                                    
                                    if "K" in likes_text or "k" in likes_text:
                                        likes *= 1000
                                    elif "M" in likes_text or "m" in likes_text:
                                        likes *= 1000000
                                except:
                                    pass
                                
                                try:
                                    replies_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'replies') or contains(text(), 'réponses')]")
                                    replies_text = replies_element.text.replace(",", "").replace(".", "").strip()
                                    replies = int(''.join(filter(str.isdigit, replies_text))) if any(c.isdigit() for c in replies_text) else 0
                                    
                                    if "K" in replies_text or "k" in replies_text:
                                        replies *= 1000
                                    elif "M" in replies_text or "m" in replies_text:
                                        replies *= 1000000
                                except:
                                    pass
                                
                                # Vérifier si la vidéo contient des sous-titres (important pour Lizz)
                                has_captions = False
                                if "[" in thread_text and "]" in thread_text:
                                    has_captions = True
                                
                                # Vérifier si la vidéo mentionne que la personne parle (important pour Lizz)
                                is_speaking = False
                                speaking_keywords = ["je vous parle", "je parle", "je vous explique", "face caméra", "facecam"]
                                if any(keyword in thread_text.lower() for keyword in speaking_keywords):
                                    is_speaking = True
                                
                                # Vérifier si la vidéo contient de la musique (important pour Talia et Léa)
                                has_music = False
                                music_keywords = ["musique", "music", "song", "chanson", "écouter", "listen"]
                                if any(keyword in thread_text.lower() for keyword in music_keywords):
                                    has_music = True
                                
                                # Calculer le score d'engagement
                                engagement_score = likes + replies * 2
                                
                                # Ajouter la vidéo à la liste
                                videos.append({
                                    "type": "video",
                                    "url": thread_url,
                                    "media_url": media_url,
                                    "date": post_date,
                                    "days_ago": days_ago,
                                    "text": thread_text,
                                    "likes": likes,
                                    "replies": replies,
                                    "engagement_score": engagement_score,
                                    "has_captions": has_captions,
                                    "is_speaking": is_speaking,
                                    "has_music": has_music,
                                    "platform": "threads",
                                    "username": username
                                })
                                
                                logger.info(f"Vidéo extraite: {thread_url} - {likes} likes, {days_ago} jours")
                            
                            # Revenir à la page de profil
                            self.driver.get(profile_url)
                            time.sleep(random.uniform(2, 3))
                            
                            if len(videos) >= max_videos:
                                break
                        except NoSuchElementException:
                            # Ce thread ne contient pas de vidéo
                            continue
                        except Exception as e:
                            logger.error(f"Erreur lors de l'analyse de la vidéo: {str(e)}")
                            # Revenir à la page de profil
                            self.driver.get(profile_url)
                            time.sleep(random.uniform(2, 3))
                            continue
                
                if len(videos) >= max_videos:
                    break
                
                # Faire défiler la page
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
                
                # Vérifier si on a atteint le bas de la page
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            
            # Trier les vidéos par score d'engagement
            videos.sort(key=lambda x: x["engagement_score"], reverse=True)
            
            return videos
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des vidéos Threads: {str(e)}")
            return videos
    
    def get_account_stats(self, username):
        """
        Récupère les statistiques d'un compte Threads.
        
        Args:
            username (str): Nom d'utilisateur du profil Threads (sans @)
            
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
            "threads_count": 0,
            "avg_likes": 0,
            "avg_replies": 0,
            "engagement_rate": 0.0,
            "bio": "",
            "website": "",
            "is_private": False
        }
        
        try:
            self._initialize_driver()
            
            # Accéder au profil
            profile_url = f"{self.threads_url}/@{username}"
            self.driver.get(profile_url)
            time.sleep(random.uniform(3, 5))
            
            # Vérifier si le profil est privé
            try:
                private_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'This account is private') or contains(text(), 'Ce compte est privé')]")
                stats["is_private"] = True
                logger.info(f"Le profil {username} est privé")
            except NoSuchElementException:
                pass
            
            # Récupérer le nombre d'abonnés
            try:
                followers_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'followers') or contains(text(), 'abonnés')]")
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
                following_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'following') or contains(text(), 'abonnements')]")
                following_text = following_element.text.replace(",", "").replace(".", "").strip()
                stats["following"] = int(''.join(filter(str.isdigit, following_text))) if any(c.isdigit() for c in following_text) else 0
                
                if "K" in following_text or "k" in following_text:
                    stats["following"] *= 1000
                elif "M" in following_text or "m" in following_text:
                    stats["following"] *= 1000000
            except:
                pass
            
            # Récupérer la bio
            try:
                bio_element = self.driver.find_element(By.XPATH, "//h1[contains(@class, 'x1lliihq')]/following-sibling::div")
                stats["bio"] = bio_element.text
            except:
                pass
            
            # Récupérer le site web
            try:
                website_element = self.driver.find_element(By.XPATH, "//a[contains(@href, 'http') and not(contains(@href, 'threads.net'))]")
                stats["website"] = website_element.get_attribute("href")
            except:
                pass
            
            # Si le profil n'est pas privé, calculer les moyennes d'engagement
            if not stats["is_private"]:
                # Récupérer quelques threads pour calculer les moyennes
                posts = self.extract_recent_content(username, days_limit=30, max_posts=5)
                
                if posts:
                    likes_list = [post["likes"] for post in posts]
                    replies_list = [post["replies"] for post in posts]
                    
                    # Calculer les moyennes
                    if likes_list:
                        stats["avg_likes"] = sum(likes_list) / len(likes_list)
                    
                    if replies_list:
                        stats["avg_replies"] = sum(replies_list) / len(replies_list)
                    
                    # Calculer le taux d'engagement moyen
                    if stats["followers"] > 0:
                        avg_engagement = (stats["avg_likes"] + stats["avg_replies"]) / stats["followers"] * 100
                        stats["engagement_rate"] = round(avg_engagement, 2)
                    
                    # Estimer le nombre de threads
                    stats["threads_count"] = len(posts)
            
            return stats
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques du compte: {str(e)}")
            return stats
    
    def close(self):
        """Ferme le scraper et libère les ressources."""
        self._close_driver()
        self.session.close()

# Fonctions pour utilisation directe
def extract_threads_content(username, days_limit=14, max_posts=20, headless=True):
    """
    Extrait le contenu récent d'un profil Threads.
    
    Args:
        username (str): Nom d'utilisateur du profil Threads (sans @)
        days_limit (int): Limite en jours pour le contenu récent
        max_posts (int): Nombre maximum de posts à extraire
        headless (bool): Si True, le navigateur s'exécute en mode headless
        
    Returns:
        list: Liste de dictionnaires contenant les informations des posts
    """
    scraper = ThreadsScraper(headless=headless)
    try:
        posts = scraper.extract_recent_content(username, days_limit, max_posts)
        return posts
    finally:
        scraper.close()

def extract_threads_videos(username, days_limit=14, max_videos=10, headless=True):
    """
    Extrait spécifiquement les vidéos d'un profil Threads.
    
    Args:
        username (str): Nom d'utilisateur du profil Threads (sans @)
        days_limit (int): Limite en jours pour les vidéos récentes
        max_videos (int): Nombre maximum de vidéos à extraire
        headless (bool): Si True, le navigateur s'exécute en mode headless
        
    Returns:
        list: Liste de dictionnaires contenant les informations des vidéos
    """
    scraper = ThreadsScraper(headless=headless)
    try:
        videos = scraper.extract_videos(username, days_limit, max_videos)
        return videos
    finally:
        scraper.close()

def get_threads_account_stats(username, headless=True):
    """
    Récupère les statistiques d'un compte Threads.
    
    Args:
        username (str): Nom d'utilisateur du profil Threads (sans @)
        headless (bool): Si True, le navigateur s'exécute en mode headless
        
    Returns:
        dict: Dictionnaire contenant les statistiques du compte
    """
    scraper = ThreadsScraper(headless=headless)
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
    posts = extract_threads_content(username, days_limit=7, max_posts=5)
    
    print(f"Nombre de posts extraits: {len(posts)}")
    for post in posts:
        print(f"Post: {post['url']} - Type: {post['type']} - Likes: {post['likes']} - Date: {post['date']}")
    
    # Exemple d'extraction de vidéos
    videos = extract_threads_videos(username, days_limit=14, max_videos=5)
    
    print(f"Nombre de vidéos extraites: {len(videos)}")
    for video in videos:
        print(f"Vidéo: {video['url']} - Likes: {video['likes']} - Date: {video['date']}")
