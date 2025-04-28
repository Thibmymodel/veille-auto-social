#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module de scraping Twitter pour le système de veille automatisée.
Ce module permet de collecter du contenu depuis Twitter sans utiliser l'API officielle.
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
logger = logging.getLogger("twitter_scraper")

class TwitterScraper:
    """Classe pour scraper du contenu depuis Twitter."""
    
    def __init__(self, headless=True, proxy=None, use_nitter=True, retry_count=3, retry_delay=5):
        """
        Initialise le scraper Twitter.
        
        Args:
            headless (bool): Si True, le navigateur s'exécute en mode headless (sans interface graphique)
            proxy (str): Proxy à utiliser pour les requêtes (format: 'http://user:pass@ip:port')
            use_nitter (bool): Si True, utilise Nitter (alternative à Twitter) pour le scraping
            retry_count (int): Nombre de tentatives en cas d'échec
            retry_delay (int): Délai entre les tentatives en secondes
        """
        self.user_agent = UserAgent().random
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})
        self.driver = None
        self.headless = headless
        self.proxy = proxy
        self.use_nitter = use_nitter
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.is_logged_in = False
        
        # URLs de base
        self.twitter_url = "https://twitter.com"
        self.nitter_instances = [
            "https://nitter.net",
            "https://nitter.42l.fr",
            "https://nitter.pussthecat.org",
            "https://nitter.nixnet.services",
            "https://nitter.fdn.fr"
        ]
        self.nitter_url = random.choice(self.nitter_instances)
        
    def _initialize_driver(self):
        """Initialise le driver Selenium pour Twitter."""
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
                    
                    # Si on utilise Nitter, essayer une autre instance
                    if self.use_nitter:
                        self.nitter_url = random.choice(self.nitter_instances)
                        logger.info(f"Changement d'instance Nitter: {self.nitter_url}")
                    
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
        Se connecte à Twitter.
        
        Args:
            username (str): Nom d'utilisateur Twitter
            password (str): Mot de passe Twitter
            
        Returns:
            bool: True si la connexion a réussi, False sinon
        """
        if self.use_nitter:
            logger.info("Nitter ne nécessite pas de connexion")
            return True
            
        try:
            self._initialize_driver()
            
            # Accéder à la page de connexion
            self.driver.get(f"{self.twitter_url}/login")
            time.sleep(random.uniform(2, 4))
            
            # Remplir le formulaire de connexion
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@name='text' or @name='username']"))
            )
            self._type_like_human(username_field, username)
            time.sleep(random.uniform(0.5, 1.5))
            
            # Cliquer sur Suivant
            next_button = self.driver.find_element(By.XPATH, "//span[text()='Next' or text()='Suivant']/..")
            next_button.click()
            time.sleep(random.uniform(1, 2))
            
            # Saisir le mot de passe
            password_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@name='password']"))
            )
            self._type_like_human(password_field, password)
            time.sleep(random.uniform(0.5, 1.5))
            
            # Cliquer sur Se connecter
            login_button = self.driver.find_element(By.XPATH, "//span[text()='Log in' or text()='Se connecter']/..")
            login_button.click()
            
            # Attendre que la connexion soit établie
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//a[@aria-label='Profile' or @aria-label='Profil']"))
            )
            
            logger.info("Connexion à Twitter réussie")
            self.is_logged_in = True
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la connexion à Twitter: {str(e)}")
            return False
    
    def search_profiles(self, keywords, min_followers=10000, max_results=20):
        """
        Recherche des profils Twitter correspondant aux mots-clés.
        
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
            base_url = self.nitter_url if self.use_nitter else self.twitter_url
            
            for keyword in keywords:
                logger.info(f"Recherche de profils avec le mot-clé: {keyword}")
                
                # Accéder à la page de recherche
                search_url = f"{base_url}/search?f=users&q={keyword}"
                self.driver.get(search_url)
                time.sleep(random.uniform(3, 5))
                
                # Récupérer les résultats
                if self.use_nitter:
                    profile_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'timeline-item')]")
                else:
                    profile_elements = self.driver.find_elements(By.XPATH, "//div[@data-testid='cellInnerDiv']//a[contains(@href, '/status/') = false and contains(@href, '/search?') = false]")
                
                for profile in profile_elements[:min(30, len(profile_elements))]:
                    try:
                        if self.use_nitter:
                            # Extraction pour Nitter
                            profile_link = profile.find_element(By.XPATH, ".//a[contains(@href, '/') and not(contains(@href, '/status/'))]")
                            profile_url = profile_link.get_attribute("href")
                            username = profile_url.split("/")[-1]
                            
                            # Visiter le profil pour obtenir plus d'informations
                            self.driver.get(profile_url)
                            time.sleep(random.uniform(2, 4))
                            
                            # Récupérer le nombre d'abonnés
                            followers_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'profile-stat')][2]//span")
                            followers_text = followers_element.text.replace(",", "").replace(".", "").strip()
                            followers_count = int(''.join(filter(str.isdigit, followers_text))) if any(c.isdigit() for c in followers_text) else 0
                            
                            if "K" in followers_text or "k" in followers_text:
                                followers_count *= 1000
                            elif "M" in followers_text or "m" in followers_text:
                                followers_count *= 1000000
                            
                            if followers_count >= min_followers:
                                # Récupérer la bio
                                try:
                                    bio_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'profile-bio')]")
                                    bio = bio_element.text
                                except:
                                    bio = ""
                                
                                # Récupérer le nom complet
                                try:
                                    name_element = self.driver.find_element(By.XPATH, "//a[contains(@class, 'profile-card-fullname')]")
                                    name = name_element.text
                                except:
                                    name = username
                                
                                profiles.append({
                                    "username": username,
                                    "name": name,
                                    "bio": bio,
                                    "followers": followers_count,
                                    "url": profile_url.replace(self.nitter_url, self.twitter_url)
                                })
                                
                                logger.info(f"Profil trouvé: {username} avec {followers_count} abonnés")
                        else:
                            # Extraction pour Twitter
                            profile_url = profile.get_attribute("href")
                            if not profile_url or "/status/" in profile_url or "/search?" in profile_url:
                                continue
                                
                            username = profile_url.split("/")[-1]
                            
                            # Visiter le profil pour obtenir plus d'informations
                            self.driver.get(profile_url)
                            time.sleep(random.uniform(3, 5))
                            
                            # Récupérer le nombre d'abonnés
                            followers_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/followers')]//span")
                            followers_text = followers_element.text.replace(",", "").replace(".", "").strip()
                            followers_count = int(''.join(filter(str.isdigit, followers_text))) if any(c.isdigit() for c in followers_text) else 0
                            
                            if "K" in followers_text or "k" in followers_text:
                                followers_count *= 1000
                            elif "M" in followers_text or "m" in followers_text:
                                followers_count *= 1000000
                            
                            if followers_count >= min_followers:
                                # Récupérer la bio
                                try:
                                    bio_element = self.driver.find_element(By.XPATH, "//div[@data-testid='userBio']")
                                    bio = bio_element.text
                                except:
                                    bio = ""
                                
                                # Récupérer le nom complet
                                try:
                                    name_element = self.driver.find_element(By.XPATH, "//div[@data-testid='UserName']//span")
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
            logger.error(f"Erreur lors de la recherche de profils Twitter: {str(e)}")
            return profiles
        
    def extract_recent_content(self, username, days_limit=14, max_posts=20):
        """
        Extrait le contenu récent d'un profil Twitter.
        
        Args:
            username (str): Nom d'utilisateur du profil Twitter
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
            base_url = self.nitter_url if self.use_nitter else self.twitter_url
            
            # Accéder au profil
            profile_url = f"{base_url}/{username}"
            self.driver.get(profile_url)
            time.sleep(random.uniform(3, 5))
            
            # Vérifier si le profil est protégé
            if self.use_nitter:
                try:
                    protected_element = self.driver.find_element(By.XPATH, "//div[contains(text(), 'This account is protected') or contains(text(), 'Ce compte est protégé')]")
                    logger.info(f"Le profil {username} est protégé")
                    return posts
                except NoSuchElementException:
                    pass
            else:
                try:
                    protected_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'These Tweets are protected') or contains(text(), 'Ces Tweets sont protégés')]")
                    logger.info(f"Le profil {username} est protégé")
                    return posts
                except NoSuchElementException:
                    pass
            
            # Récupérer les tweets
            tweet_elements = []
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            while len(tweet_elements) < max_posts:
                # Récupérer tous les tweets visibles
                if self.use_nitter:
                    elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'timeline-item')]")
                else:
                    elements = self.driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
                
                tweet_elements.extend([e for e in elements if e not in tweet_elements])
                
                if len(tweet_elements) >= max_posts:
                    break
                
                # Faire défiler la page
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
                
                # Vérifier si on a atteint le bas de la page
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            
            # Limiter le nombre de tweets à analyser
            tweet_elements = tweet_elements[:min(max_posts, len(tweet_elements))]
            
            for tweet_element in tweet_elements:
                try:
                    if self.use_nitter:
                        # Extraction pour Nitter
                        tweet_link = tweet_element.find_element(By.XPATH, ".//a[contains(@href, '/status/')]")
                        tweet_url = tweet_link.get_attribute("href")
                        tweet_url = tweet_url.replace(self.nitter_url, self.twitter_url)
                        
                        # Récupérer la date du tweet
                        date_element = tweet_element.find_element(By.XPATH, ".//span[contains(@class, 'tweet-date')]//a")
                        date_text = date_element.get_attribute("title")  # Format: "MMM DD, YYYY · HH:MM:SS AM/PM"
                        
                        # Convertir la date en format YYYY-MM-DD
                        try:
                            tweet_date = datetime.strptime(date_text, "%b %d, %Y · %I:%M:%S %p")
                            post_date = tweet_date.strftime("%Y-%m-%d")
                            days_ago = (datetime.now() - tweet_date).days
                        except:
                            # Essayer un autre format
                            try:
                                tweet_date = datetime.strptime(date_text, "%d %b %Y · %H:%M:%S")
                                post_date = tweet_date.strftime("%Y-%m-%d")
                                days_ago = (datetime.now() - tweet_date).days
                            except:
                                # Utiliser la date du jour si le format n'est pas reconnu
                                post_date = datetime.now().strftime("%Y-%m-%d")
                                days_ago = 0
                        
                        if days_ago > days_limit:
                            continue
                        
                        # Déterminer le type de tweet (texte, photo, vidéo)
                        post_type = "text"  # Par défaut
                        
                        try:
                            img_element = tweet_element.find_element(By.XPATH, ".//div[contains(@class, 'attachment')]//img")
                            post_type = "photo"
                            media_url = img_element.get_attribute("src")
                        except NoSuchElementException:
                            try:
                                video_element = tweet_element.find_element(By.XPATH, ".//div[contains(@class, 'attachment')]//video")
                                post_type = "video"
                                media_url = video_element.get_attribute("poster") or ""
                            except NoSuchElementException:
                                media_url = ""
                        
                        # Récupérer le texte du tweet
                        try:
                            text_element = tweet_element.find_element(By.XPATH, ".//div[contains(@class, 'tweet-content')]")
                            tweet_text = text_element.text
                        except:
                            tweet_text = ""
                        
                        # Récupérer les statistiques du tweet
                        stats = {}
                        try:
                            stats_elements = tweet_element.find_elements(By.XPATH, ".//div[contains(@class, 'tweet-stats')]//span[contains(@class, 'tweet-stat')]")
                            for stat in stats_elements:
                                stat_text = stat.text.strip()
                                if "reply" in stat_text.lower() or "réponse" in stat_text.lower():
                                    stats["replies"] = int(''.join(filter(str.isdigit, stat_text))) if any(c.isdigit() for c in stat_text) else 0
                                elif "retweet" in stat_text.lower():
                                    stats["retweets"] = int(''.join(filter(str.isdigit, stat_text))) if any(c.isdigit() for c in stat_text) else 0
                                elif "like" in stat_text.lower() or "j'aime" in stat_text.lower():
                                    stats["likes"] = int(''.join(filter(str.isdigit, stat_text))) if any(c.isdigit() for c in stat_text) else 0
                        except:
                            stats = {"replies": 0, "retweets": 0, "likes": 0}
                    else:
                        # Extraction pour Twitter
                        tweet_link = tweet_element.find_element(By.XPATH, ".//a[contains(@href, '/status/')]")
                        tweet_url = tweet_link.get_attribute("href")
                        
                        # Récupérer la date du tweet
                        date_element = tweet_element.find_element(By.XPATH, ".//time")
                        date_text = date_element.get_attribute("datetime")  # Format: "YYYY-MM-DDTHH:MM:SS.000Z"
                        
                        # Convertir la date en format YYYY-MM-DD
                        tweet_date = datetime.strptime(date_text.split("T")[0], "%Y-%m-%d")
                        post_date = tweet_date.strftime("%Y-%m-%d")
                        days_ago = (datetime.now() - tweet_date).days
                        
                        if days_ago > days_limit:
                            continue
                        
                        # Déterminer le type de tweet (texte, photo, vidéo)
                        post_type = "text"  # Par défaut
                        media_url = ""
                        
                        try:
                            img_element = tweet_element.find_element(By.XPATH, ".//img[@alt='Image']")
                            post_type = "photo"
                            media_url = img_element.get_attribute("src")
                        except NoSuchElementException:
                            try:
                                video_element = tweet_element.find_element(By.XPATH, ".//video")
                                post_type = "video"
                                media_url = video_element.get_attribute("poster") or ""
                            except NoSuchElementException:
                                pass
                        
                        # Récupérer le texte du tweet
                        try:
                            text_element = tweet_element.find_element(By.XPATH, ".//div[@data-testid='tweetText']")
                            tweet_text = text_element.text
                        except:
                            tweet_text = ""
                        
                        # Récupérer les statistiques du tweet
                        stats = {"replies": 0, "retweets": 0, "likes": 0}
                        try:
                            reply_element = tweet_element.find_element(By.XPATH, ".//div[@data-testid='reply']/../span")
                            stats["replies"] = int(reply_element.text) if reply_element.text.isdigit() else 0
                        except:
                            pass
                        
                        try:
                            retweet_element = tweet_element.find_element(By.XPATH, ".//div[@data-testid='retweet']/../span")
                            stats["retweets"] = int(retweet_element.text) if retweet_element.text.isdigit() else 0
                        except:
                            pass
                        
                        try:
                            like_element = tweet_element.find_element(By.XPATH, ".//div[@data-testid='like']/../span")
                            stats["likes"] = int(like_element.text) if like_element.text.isdigit() else 0
                        except:
                            pass
                    
                    # Vérifier si le tweet contient des sous-titres (important pour Lizz)
                    has_captions = False
                    if "[" in tweet_text and "]" in tweet_text:
                        has_captions = True
                    
                    # Vérifier si le tweet mentionne que la personne parle (important pour Lizz)
                    is_speaking = False
                    speaking_keywords = ["je vous parle", "je parle", "je vous explique", "face caméra", "facecam"]
                    if any(keyword in tweet_text.lower() for keyword in speaking_keywords):
                        is_speaking = True
                    
                    # Vérifier si le tweet contient de la musique (important pour Talia et Léa)
                    has_music = False
                    music_keywords = ["musique", "music", "song", "chanson", "écouter", "listen"]
                    if any(keyword in tweet_text.lower() for keyword in music_keywords):
                        has_music = True
                    
                    # Calculer le score d'engagement
                    engagement_score = stats.get("likes", 0) + stats.get("retweets", 0) * 2 + stats.get("replies", 0)
                    
                    # Ajouter le tweet à la liste
                    posts.append({
                        "type": post_type,
                        "url": tweet_url,
                        "media_url": media_url,
                        "date": post_date,
                        "days_ago": days_ago,
                        "text": tweet_text,
                        "likes": stats.get("likes", 0),
                        "retweets": stats.get("retweets", 0),
                        "replies": stats.get("replies", 0),
                        "engagement_score": engagement_score,
                        "has_captions": has_captions,
                        "is_speaking": is_speaking,
                        "has_music": has_music,
                        "platform": "twitter",
                        "username": username
                    })
                    
                    logger.info(f"Tweet extrait: {tweet_url} ({post_type}) - {stats.get('likes', 0)} likes, {days_ago} jours")
                    
                except Exception as e:
                    logger.error(f"Erreur lors de l'analyse du tweet: {str(e)}")
                    continue
                
                time.sleep(random.uniform(1, 2))
            
            # Trier les tweets par score d'engagement
            posts.sort(key=lambda x: x["engagement_score"], reverse=True)
            
            return posts
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction du contenu Twitter: {str(e)}")
            return posts
    
    def extract_videos(self, username, days_limit=14, max_videos=10):
        """
        Extrait spécifiquement les vidéos d'un profil Twitter.
        
        Args:
            username (str): Nom d'utilisateur du profil Twitter
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
            base_url = self.nitter_url if self.use_nitter else self.twitter_url
            
            # Accéder au profil
            profile_url = f"{base_url}/{username}/media"
            self.driver.get(profile_url)
            time.sleep(random.uniform(3, 5))
            
            # Vérifier si le profil est protégé
            if self.use_nitter:
                try:
                    protected_element = self.driver.find_element(By.XPATH, "//div[contains(text(), 'This account is protected') or contains(text(), 'Ce compte est protégé')]")
                    logger.info(f"Le profil {username} est protégé")
                    return videos
                except NoSuchElementException:
                    pass
            else:
                try:
                    protected_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'These Tweets are protected') or contains(text(), 'Ces Tweets sont protégés')]")
                    logger.info(f"Le profil {username} est protégé")
                    return videos
                except NoSuchElementException:
                    pass
            
            # Récupérer les tweets avec vidéos
            tweet_elements = []
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            while len(videos) < max_videos:
                # Récupérer tous les tweets visibles
                if self.use_nitter:
                    elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'timeline-item')]")
                    
                    # Filtrer pour ne garder que les tweets avec vidéos
                    for element in elements:
                        try:
                            video_element = element.find_element(By.XPATH, ".//div[contains(@class, 'attachment')]//video")
                            if element not in tweet_elements:
                                tweet_elements.append(element)
                        except NoSuchElementException:
                            pass
                else:
                    elements = self.driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
                    
                    # Filtrer pour ne garder que les tweets avec vidéos
                    for element in elements:
                        try:
                            video_element = element.find_element(By.XPATH, ".//video")
                            if element not in tweet_elements:
                                tweet_elements.append(element)
                        except NoSuchElementException:
                            pass
                
                if len(tweet_elements) >= max_videos:
                    break
                
                # Faire défiler la page
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
                
                # Vérifier si on a atteint le bas de la page
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            
            # Limiter le nombre de tweets à analyser
            tweet_elements = tweet_elements[:min(max_videos, len(tweet_elements))]
            
            for tweet_element in tweet_elements:
                try:
                    if self.use_nitter:
                        # Extraction pour Nitter
                        tweet_link = tweet_element.find_element(By.XPATH, ".//a[contains(@href, '/status/')]")
                        tweet_url = tweet_link.get_attribute("href")
                        tweet_url = tweet_url.replace(self.nitter_url, self.twitter_url)
                        
                        # Récupérer la date du tweet
                        date_element = tweet_element.find_element(By.XPATH, ".//span[contains(@class, 'tweet-date')]//a")
                        date_text = date_element.get_attribute("title")  # Format: "MMM DD, YYYY · HH:MM:SS AM/PM"
                        
                        # Convertir la date en format YYYY-MM-DD
                        try:
                            tweet_date = datetime.strptime(date_text, "%b %d, %Y · %I:%M:%S %p")
                            post_date = tweet_date.strftime("%Y-%m-%d")
                            days_ago = (datetime.now() - tweet_date).days
                        except:
                            # Essayer un autre format
                            try:
                                tweet_date = datetime.strptime(date_text, "%d %b %Y · %H:%M:%S")
                                post_date = tweet_date.strftime("%Y-%m-%d")
                                days_ago = (datetime.now() - tweet_date).days
                            except:
                                # Utiliser la date du jour si le format n'est pas reconnu
                                post_date = datetime.now().strftime("%Y-%m-%d")
                                days_ago = 0
                        
                        if days_ago > days_limit:
                            continue
                        
                        # Récupérer l'URL de la vidéo
                        video_element = tweet_element.find_element(By.XPATH, ".//div[contains(@class, 'attachment')]//video")
                        media_url = video_element.get_attribute("poster") or ""
                        
                        # Récupérer le texte du tweet
                        try:
                            text_element = tweet_element.find_element(By.XPATH, ".//div[contains(@class, 'tweet-content')]")
                            tweet_text = text_element.text
                        except:
                            tweet_text = ""
                        
                        # Récupérer les statistiques du tweet
                        stats = {}
                        try:
                            stats_elements = tweet_element.find_elements(By.XPATH, ".//div[contains(@class, 'tweet-stats')]//span[contains(@class, 'tweet-stat')]")
                            for stat in stats_elements:
                                stat_text = stat.text.strip()
                                if "reply" in stat_text.lower() or "réponse" in stat_text.lower():
                                    stats["replies"] = int(''.join(filter(str.isdigit, stat_text))) if any(c.isdigit() for c in stat_text) else 0
                                elif "retweet" in stat_text.lower():
                                    stats["retweets"] = int(''.join(filter(str.isdigit, stat_text))) if any(c.isdigit() for c in stat_text) else 0
                                elif "like" in stat_text.lower() or "j'aime" in stat_text.lower():
                                    stats["likes"] = int(''.join(filter(str.isdigit, stat_text))) if any(c.isdigit() for c in stat_text) else 0
                        except:
                            stats = {"replies": 0, "retweets": 0, "likes": 0}
                    else:
                        # Extraction pour Twitter
                        tweet_link = tweet_element.find_element(By.XPATH, ".//a[contains(@href, '/status/')]")
                        tweet_url = tweet_link.get_attribute("href")
                        
                        # Récupérer la date du tweet
                        date_element = tweet_element.find_element(By.XPATH, ".//time")
                        date_text = date_element.get_attribute("datetime")  # Format: "YYYY-MM-DDTHH:MM:SS.000Z"
                        
                        # Convertir la date en format YYYY-MM-DD
                        tweet_date = datetime.strptime(date_text.split("T")[0], "%Y-%m-%d")
                        post_date = tweet_date.strftime("%Y-%m-%d")
                        days_ago = (datetime.now() - tweet_date).days
                        
                        if days_ago > days_limit:
                            continue
                        
                        # Récupérer l'URL de la vidéo
                        video_element = tweet_element.find_element(By.XPATH, ".//video")
                        media_url = video_element.get_attribute("poster") or ""
                        
                        # Récupérer le texte du tweet
                        try:
                            text_element = tweet_element.find_element(By.XPATH, ".//div[@data-testid='tweetText']")
                            tweet_text = text_element.text
                        except:
                            tweet_text = ""
                        
                        # Récupérer les statistiques du tweet
                        stats = {"replies": 0, "retweets": 0, "likes": 0}
                        try:
                            reply_element = tweet_element.find_element(By.XPATH, ".//div[@data-testid='reply']/../span")
                            stats["replies"] = int(reply_element.text) if reply_element.text.isdigit() else 0
                        except:
                            pass
                        
                        try:
                            retweet_element = tweet_element.find_element(By.XPATH, ".//div[@data-testid='retweet']/../span")
                            stats["retweets"] = int(retweet_element.text) if retweet_element.text.isdigit() else 0
                        except:
                            pass
                        
                        try:
                            like_element = tweet_element.find_element(By.XPATH, ".//div[@data-testid='like']/../span")
                            stats["likes"] = int(like_element.text) if like_element.text.isdigit() else 0
                        except:
                            pass
                    
                    # Vérifier si la vidéo contient des sous-titres (important pour Lizz)
                    has_captions = False
                    if "[" in tweet_text and "]" in tweet_text:
                        has_captions = True
                    
                    # Vérifier si la vidéo mentionne que la personne parle (important pour Lizz)
                    is_speaking = False
                    speaking_keywords = ["je vous parle", "je parle", "je vous explique", "face caméra", "facecam"]
                    if any(keyword in tweet_text.lower() for keyword in speaking_keywords):
                        is_speaking = True
                    
                    # Vérifier si la vidéo contient de la musique (important pour Talia et Léa)
                    has_music = False
                    music_keywords = ["musique", "music", "song", "chanson", "écouter", "listen"]
                    if any(keyword in tweet_text.lower() for keyword in music_keywords):
                        has_music = True
                    
                    # Calculer le score d'engagement
                    engagement_score = stats.get("likes", 0) + stats.get("retweets", 0) * 2 + stats.get("replies", 0)
                    
                    # Ajouter la vidéo à la liste
                    videos.append({
                        "type": "video",
                        "url": tweet_url,
                        "media_url": media_url,
                        "date": post_date,
                        "days_ago": days_ago,
                        "text": tweet_text,
                        "likes": stats.get("likes", 0),
                        "retweets": stats.get("retweets", 0),
                        "replies": stats.get("replies", 0),
                        "engagement_score": engagement_score,
                        "has_captions": has_captions,
                        "is_speaking": is_speaking,
                        "has_music": has_music,
                        "platform": "twitter",
                        "username": username
                    })
                    
                    logger.info(f"Vidéo extraite: {tweet_url} - {stats.get('likes', 0)} likes, {days_ago} jours")
                    
                except Exception as e:
                    logger.error(f"Erreur lors de l'analyse de la vidéo: {str(e)}")
                    continue
                
                time.sleep(random.uniform(1, 2))
            
            # Trier les vidéos par score d'engagement
            videos.sort(key=lambda x: x["engagement_score"], reverse=True)
            
            return videos
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des vidéos Twitter: {str(e)}")
            return videos
    
    def analyze_engagement(self, tweet_url):
        """
        Analyse l'engagement d'un tweet.
        
        Args:
            tweet_url (str): URL du tweet
            
        Returns:
            dict: Dictionnaire contenant les métriques d'engagement
        """
        return self._retry_on_failure(self._analyze_engagement, tweet_url)
    
    def _analyze_engagement(self, tweet_url):
        """
        Implémentation interne de l'analyse d'engagement.
        """
        engagement = {
            "likes": 0,
            "retweets": 0,
            "replies": 0,
            "quotes": 0,
            "views": 0,
            "engagement_rate": 0.0
        }
        
        try:
            self._initialize_driver()
            
            # Convertir l'URL Twitter en URL Nitter si nécessaire
            if self.use_nitter and self.twitter_url in tweet_url:
                tweet_url = tweet_url.replace(self.twitter_url, self.nitter_url)
            
            # Accéder au tweet
            self.driver.get(tweet_url)
            time.sleep(random.uniform(2, 4))
            
            if self.use_nitter:
                # Extraction pour Nitter
                try:
                    stats_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'tweet-stats')]//span[contains(@class, 'tweet-stat')]")
                    for stat in stats_elements:
                        stat_text = stat.text.strip()
                        if "reply" in stat_text.lower() or "réponse" in stat_text.lower():
                            engagement["replies"] = int(''.join(filter(str.isdigit, stat_text))) if any(c.isdigit() for c in stat_text) else 0
                        elif "retweet" in stat_text.lower():
                            engagement["retweets"] = int(''.join(filter(str.isdigit, stat_text))) if any(c.isdigit() for c in stat_text) else 0
                        elif "like" in stat_text.lower() or "j'aime" in stat_text.lower():
                            engagement["likes"] = int(''.join(filter(str.isdigit, stat_text))) if any(c.isdigit() for c in stat_text) else 0
                except:
                    pass
                
                # Récupérer le nombre d'abonnés pour calculer le taux d'engagement
                try:
                    # Extraire le nom d'utilisateur de l'URL du tweet
                    username = tweet_url.split("/status/")[0].split("/")[-1]
                    
                    # Accéder au profil
                    self.driver.get(f"{self.nitter_url}/{username}")
                    time.sleep(random.uniform(2, 3))
                    
                    # Récupérer le nombre d'abonnés
                    followers_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'profile-stat')][2]//span")
                    followers_text = followers_element.text.replace(",", "").replace(".", "").strip()
                    followers_count = int(''.join(filter(str.isdigit, followers_text))) if any(c.isdigit() for c in followers_text) else 0
                    
                    if "K" in followers_text or "k" in followers_text:
                        followers_count *= 1000
                    elif "M" in followers_text or "m" in followers_text:
                        followers_count *= 1000000
                    
                    if followers_count > 0:
                        # Calculer le taux d'engagement (likes + retweets + replies) / abonnés * 100
                        engagement["engagement_rate"] = round((engagement["likes"] + engagement["retweets"] + engagement["replies"]) / followers_count * 100, 2)
                except:
                    pass
            else:
                # Extraction pour Twitter
                try:
                    # Récupérer le nombre de vues
                    try:
                        views_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Views') or contains(text(), 'Vues')]/../span[1]")
                        views_text = views_element.text.replace(",", "").strip()
                        engagement["views"] = int(''.join(filter(str.isdigit, views_text))) if any(c.isdigit() for c in views_text) else 0
                        
                        if "K" in views_text or "k" in views_text:
                            engagement["views"] *= 1000
                        elif "M" in views_text or "m" in views_text:
                            engagement["views"] *= 1000000
                    except:
                        pass
                    
                    # Récupérer le nombre de réponses
                    try:
                        reply_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/status/') and contains(@href, '/replies')]//span")
                        engagement["replies"] = int(reply_element.text) if reply_element.text.isdigit() else 0
                    except:
                        pass
                    
                    # Récupérer le nombre de retweets
                    try:
                        retweet_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/status/') and contains(@href, '/retweets')]//span")
                        engagement["retweets"] = int(retweet_element.text) if retweet_element.text.isdigit() else 0
                    except:
                        pass
                    
                    # Récupérer le nombre de likes
                    try:
                        like_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/status/') and contains(@href, '/likes')]//span")
                        engagement["likes"] = int(like_element.text) if like_element.text.isdigit() else 0
                    except:
                        pass
                    
                    # Récupérer le nombre de citations
                    try:
                        quote_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/status/') and contains(@href, '/quotes')]//span")
                        engagement["quotes"] = int(quote_element.text) if quote_element.text.isdigit() else 0
                    except:
                        pass
                    
                    # Récupérer le nombre d'abonnés pour calculer le taux d'engagement
                    try:
                        # Extraire le nom d'utilisateur de l'URL du tweet
                        username = tweet_url.split("/status/")[0].split("/")[-1]
                        
                        # Accéder au profil
                        self.driver.get(f"{self.twitter_url}/{username}")
                        time.sleep(random.uniform(2, 3))
                        
                        # Récupérer le nombre d'abonnés
                        followers_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/followers')]//span")
                        followers_text = followers_element.text.replace(",", "").replace(".", "").strip()
                        followers_count = int(''.join(filter(str.isdigit, followers_text))) if any(c.isdigit() for c in followers_text) else 0
                        
                        if "K" in followers_text or "k" in followers_text:
                            followers_count *= 1000
                        elif "M" in followers_text or "m" in followers_text:
                            followers_count *= 1000000
                        
                        if followers_count > 0:
                            # Calculer le taux d'engagement (likes + retweets + replies + quotes) / abonnés * 100
                            engagement["engagement_rate"] = round((engagement["likes"] + engagement["retweets"] + engagement["replies"] + engagement["quotes"]) / followers_count * 100, 2)
                    except:
                        pass
                except Exception as e:
                    logger.error(f"Erreur lors de l'analyse de l'engagement: {str(e)}")
            
            return engagement
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse de l'engagement: {str(e)}")
            return engagement
    
    def get_account_stats(self, username):
        """
        Récupère les statistiques d'un compte Twitter.
        
        Args:
            username (str): Nom d'utilisateur du profil Twitter
            
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
            "tweets_count": 0,
            "avg_likes": 0,
            "avg_retweets": 0,
            "avg_replies": 0,
            "engagement_rate": 0.0,
            "bio": "",
            "website": "",
            "is_protected": False
        }
        
        try:
            self._initialize_driver()
            base_url = self.nitter_url if self.use_nitter else self.twitter_url
            
            # Accéder au profil
            profile_url = f"{base_url}/{username}"
            self.driver.get(profile_url)
            time.sleep(random.uniform(3, 5))
            
            # Vérifier si le profil est protégé
            if self.use_nitter:
                try:
                    protected_element = self.driver.find_element(By.XPATH, "//div[contains(text(), 'This account is protected') or contains(text(), 'Ce compte est protégé')]")
                    stats["is_protected"] = True
                    logger.info(f"Le profil {username} est protégé")
                except NoSuchElementException:
                    pass
                
                # Récupérer le nombre d'abonnés
                try:
                    followers_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'profile-stat')][2]//span")
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
                    following_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'profile-stat')][1]//span")
                    following_text = following_element.text.replace(",", "").replace(".", "").strip()
                    stats["following"] = int(''.join(filter(str.isdigit, following_text))) if any(c.isdigit() for c in following_text) else 0
                    
                    if "K" in following_text or "k" in following_text:
                        stats["following"] *= 1000
                    elif "M" in following_text or "m" in following_text:
                        stats["following"] *= 1000000
                except:
                    pass
                
                # Récupérer le nombre de tweets
                try:
                    tweets_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'profile-stat')][3]//span")
                    tweets_text = tweets_element.text.replace(",", "").replace(".", "").strip()
                    stats["tweets_count"] = int(''.join(filter(str.isdigit, tweets_text))) if any(c.isdigit() for c in tweets_text) else 0
                    
                    if "K" in tweets_text or "k" in tweets_text:
                        stats["tweets_count"] *= 1000
                    elif "M" in tweets_text or "m" in tweets_text:
                        stats["tweets_count"] *= 1000000
                except:
                    pass
                
                # Récupérer la bio
                try:
                    bio_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'profile-bio')]")
                    stats["bio"] = bio_element.text
                except:
                    pass
                
                # Récupérer le site web
                try:
                    website_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'profile-website')]//a")
                    stats["website"] = website_element.get_attribute("href")
                except:
                    pass
            else:
                # Vérifier si le profil est protégé
                try:
                    protected_element = self.driver.find_element(By.XPATH, "//span[contains(text(), 'These Tweets are protected') or contains(text(), 'Ces Tweets sont protégés')]")
                    stats["is_protected"] = True
                    logger.info(f"Le profil {username} est protégé")
                except NoSuchElementException:
                    pass
                
                # Récupérer le nombre d'abonnés
                try:
                    followers_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/followers')]//span")
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
                    following_element = self.driver.find_element(By.XPATH, "//a[contains(@href, '/following')]//span")
                    following_text = following_element.text.replace(",", "").replace(".", "").strip()
                    stats["following"] = int(''.join(filter(str.isdigit, following_text))) if any(c.isdigit() for c in following_text) else 0
                    
                    if "K" in following_text or "k" in following_text:
                        stats["following"] *= 1000
                    elif "M" in following_text or "m" in following_text:
                        stats["following"] *= 1000000
                except:
                    pass
                
                # Récupérer le nombre de tweets
                try:
                    tweets_element = self.driver.find_element(By.XPATH, "//div[contains(@aria-label, 'tweets') or contains(@aria-label, 'Tweets')]//span")
                    tweets_text = tweets_element.text.replace(",", "").replace(".", "").strip()
                    stats["tweets_count"] = int(''.join(filter(str.isdigit, tweets_text))) if any(c.isdigit() for c in tweets_text) else 0
                    
                    if "K" in tweets_text or "k" in tweets_text:
                        stats["tweets_count"] *= 1000
                    elif "M" in tweets_text or "m" in tweets_text:
                        stats["tweets_count"] *= 1000000
                except:
                    pass
                
                # Récupérer la bio
                try:
                    bio_element = self.driver.find_element(By.XPATH, "//div[@data-testid='userBio']")
                    stats["bio"] = bio_element.text
                except:
                    pass
                
                # Récupérer le site web
                try:
                    website_element = self.driver.find_element(By.XPATH, "//a[@data-testid='UserUrl']")
                    stats["website"] = website_element.get_attribute("href")
                except:
                    pass
            
            # Si le profil n'est pas protégé, calculer les moyennes d'engagement
            if not stats["is_protected"]:
                # Récupérer quelques tweets pour calculer les moyennes
                posts = self.extract_recent_content(username, days_limit=30, max_posts=5)
                
                if posts:
                    likes_list = [post["likes"] for post in posts]
                    retweets_list = [post["retweets"] for post in posts]
                    replies_list = [post["replies"] for post in posts]
                    
                    # Calculer les moyennes
                    if likes_list:
                        stats["avg_likes"] = sum(likes_list) / len(likes_list)
                    
                    if retweets_list:
                        stats["avg_retweets"] = sum(retweets_list) / len(retweets_list)
                    
                    if replies_list:
                        stats["avg_replies"] = sum(replies_list) / len(replies_list)
                    
                    # Calculer le taux d'engagement moyen
                    if stats["followers"] > 0:
                        avg_engagement = (stats["avg_likes"] + stats["avg_retweets"] + stats["avg_replies"]) / stats["followers"] * 100
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
def extract_twitter_content(username, days_limit=14, max_posts=20, headless=True, use_nitter=True):
    """
    Extrait le contenu récent d'un profil Twitter.
    
    Args:
        username (str): Nom d'utilisateur du profil Twitter
        days_limit (int): Limite en jours pour le contenu récent
        max_posts (int): Nombre maximum de posts à extraire
        headless (bool): Si True, le navigateur s'exécute en mode headless
        use_nitter (bool): Si True, utilise Nitter pour le scraping
        
    Returns:
        list: Liste de dictionnaires contenant les informations des posts
    """
    scraper = TwitterScraper(headless=headless, use_nitter=use_nitter)
    try:
        posts = scraper.extract_recent_content(username, days_limit, max_posts)
        return posts
    finally:
        scraper.close()

def extract_twitter_videos(username, days_limit=14, max_videos=10, headless=True, use_nitter=True):
    """
    Extrait spécifiquement les vidéos d'un profil Twitter.
    
    Args:
        username (str): Nom d'utilisateur du profil Twitter
        days_limit (int): Limite en jours pour les vidéos récentes
        max_videos (int): Nombre maximum de vidéos à extraire
        headless (bool): Si True, le navigateur s'exécute en mode headless
        use_nitter (bool): Si True, utilise Nitter pour le scraping
        
    Returns:
        list: Liste de dictionnaires contenant les informations des vidéos
    """
    scraper = TwitterScraper(headless=headless, use_nitter=use_nitter)
    try:
        videos = scraper.extract_videos(username, days_limit, max_videos)
        return videos
    finally:
        scraper.close()

def get_twitter_account_stats(username, headless=True, use_nitter=True):
    """
    Récupère les statistiques d'un compte Twitter.
    
    Args:
        username (str): Nom d'utilisateur du profil Twitter
        headless (bool): Si True, le navigateur s'exécute en mode headless
        use_nitter (bool): Si True, utilise Nitter pour le scraping
        
    Returns:
        dict: Dictionnaire contenant les statistiques du compte
    """
    scraper = TwitterScraper(headless=headless, use_nitter=use_nitter)
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
    posts = extract_twitter_content(username, days_limit=7, max_posts=5)
    
    print(f"Nombre de posts extraits: {len(posts)}")
    for post in posts:
        print(f"Post: {post['url']} - Type: {post['type']} - Likes: {post['likes']} - Date: {post['date']}")
    
    # Exemple d'extraction de vidéos
    videos = extract_twitter_videos(username, days_limit=14, max_videos=5)
    
    print(f"Nombre de vidéos extraites: {len(videos)}")
    for video in videos:
        print(f"Vidéo: {video['url']} - Likes: {video['likes']} - Date: {video['date']}")
