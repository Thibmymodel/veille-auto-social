# Documentation du Système de Veille Automatisée pour Créatrices OnlyFans

## Vue d'ensemble

Ce système permet d'automatiser la veille de contenu sur les réseaux sociaux pour les créatrices OnlyFans.
Il collecte du contenu depuis Instagram, Twitter, Threads et TikTok, sélectionne les contenus les plus pertinents
selon des critères spécifiques, et met à jour un Google Sheet avec les résultats.

## Architecture du système

Le système est composé des modules suivants :

1. **Scrapers de réseaux sociaux** :
   - `instagram_scraper.py` : Extraction de contenu depuis Instagram
   - `twitter_scraper.py` : Extraction de contenu depuis Twitter
   - `threads_scraper.py` : Extraction de contenu depuis Threads
   - `tiktok_scraper.py` : Extraction de contenu depuis TikTok

2. **Algorithme de sélection de contenu** :
   - `content_selector.py` : Sélection du contenu le plus pertinent selon des critères spécifiques

3. **Intégration Google Sheets** :
   - `google_sheet_integration.py` : Mise à jour du Google Sheet avec le contenu sélectionné

4. **Script principal** :
   - `veille_automatisee.py` : Orchestration de l'ensemble du processus

5. **Déploiement** :
   - `deploy.py` : Script de déploiement pour différentes plateformes

## Fonctionnalités principales

### Extraction de contenu

Le système extrait les types de contenu suivants :

- **Photos** : Images statiques des profils
- **Vidéos** : Vidéos standards des profils
- **Réels/Stories** : Contenus courts et dynamiques
- **Tendances** : Hashtags et sons populaires

### Critères de sélection

Le contenu est sélectionné selon les critères suivants :

- **Récence** : Contenu récemment publié
- **Performance** : Contenu avec un bon taux d'engagement
- **Pertinence** : Contenu correspondant aux préférences spécifiques de chaque modèle
  - Talia : Préfère les vidéos sans parole, avec musique
  - Léa : Préfère les vidéos sans parole, avec musique
  - Lizz : Préfère les vidéos avec parole, avec sous-titres

### Mise à jour du Google Sheet

Le système met à jour un Google Sheet avec les informations suivantes pour chaque modèle :

- Liens vers les photos récentes
- Lien vers une vidéo récente
- Lien vers un réel performant
- Tendances actuelles (hashtags, sons)

## Installation et déploiement

Le système peut être déployé sur différentes plateformes :

1. **Linux standard** :
   ```
   sudo python3 deploy.py
   ```

2. **Windows avec WSL** :
   ```
   bash install_wsl.sh
   ```

3. **Railway (cloud)** :
   ```
   railway up
   ```

Pour des instructions détaillées, consultez les fichiers README spécifiques à chaque plateforme.

## Configuration

### Authentification Google

Deux méthodes d'authentification sont supportées :

1. **OAuth2** (recommandé pour les installations locales) :
   - Nécessite un fichier `client_secrets.json`
   - Utilise un navigateur pour l'authentification interactive

2. **Compte de service** (recommandé pour les déploiements cloud) :
   - Nécessite un fichier `service_account.json`
   - Le Google Sheet doit être partagé avec l'adresse email du compte de service

### Configuration des modèles

Les modèles sont configurés dans le fichier `veille_automatisee.py` :

```python
MODELS = [
    {
        "name": "Talia",
        "instagram": "talia_srz",
        "twitter": "talia_srz",
        "threads": "talia_srz",
        "tiktok": "talia_srz",
        "style": "Coquin soft, caption + musique uniquement",
        "avg_views": 4000,
        "preferences": {
            "prefers_speaking": False,
            "prefers_captions": False,
            "prefers_music": True
        }
    },
    # Autres modèles...
]
```

## Utilisation

### Modes d'exécution

Le système peut être exécuté dans différents modes :

1. **Mode test** :
   ```
   python3 veille_automatisee.py --test
   ```

2. **Mode continu** (jusqu'à atteindre le quota journalier) :
   ```
   python3 veille_automatisee.py --continuous
   ```

3. **Mode planifié** (à une heure spécifique chaque jour) :
   ```
   python3 veille_automatisee.py --schedule --hour 0 --minute 0
   ```

### Options spécifiques

Des options spécifiques sont disponibles pour des cas d'utilisation particuliers :

- `--instagram-only` : Exécuter uniquement le scraping Instagram
- `--twitter-only` : Exécuter uniquement le scraping Twitter
- `--threads-only` : Exécuter uniquement le scraping Threads
- `--tiktok-only` : Exécuter uniquement le scraping TikTok
- `--trending-only` : Exécuter uniquement le scraping des tendances
- `--model <nom>` : Exécuter uniquement pour un modèle spécifique

## Maintenance et dépannage

### Logs

Les logs sont disponibles dans le répertoire `logs` :

- `veille_automatisee.log` : Log principal du système
- `deployment.log` : Log du déploiement
- `service.log` : Log du service systemd (Linux)

### Problèmes courants

1. **Erreur d'authentification Google** :
   - Vérifiez que les fichiers d'authentification sont correctement configurés
   - Assurez-vous que les API nécessaires sont activées dans la console Google Cloud

2. **Erreur de scraping** :
   - Les sites web peuvent changer leur structure HTML, nécessitant une mise à jour des scrapers
   - Certains sites peuvent bloquer les requêtes automatisées, nécessitant des délais plus longs entre les requêtes

3. **Erreur de base de données** :
   - Vérifiez les permissions du fichier de base de données SQLite
   - Assurez-vous que le disque a suffisamment d'espace libre

## Personnalisation

### Ajout de nouveaux modèles

Pour ajouter un nouveau modèle :

1. Ajoutez ses informations dans la liste `MODELS` dans `veille_automatisee.py`
2. Configurez ses préférences spécifiques
3. Assurez-vous que le Google Sheet contient une feuille pour ce modèle

### Modification des critères de sélection

Les critères de sélection peuvent être modifiés dans `content_selector.py` :

- Ajustez les seuils de performance
- Modifiez les préférences de contenu
- Changez les quotas de contenu

## Sécurité et confidentialité

- Le système utilise uniquement des données publiquement accessibles
- Les identifiants d'authentification Google doivent être gardés confidentiels
- Aucune donnée personnelle n'est collectée ou stockée

## Limitations connues

- Le système dépend de la structure HTML des sites web, qui peut changer
- Certains sites peuvent limiter le nombre de requêtes, ralentissant le processus
- L'authentification OAuth2 nécessite une interaction utilisateur initiale

## Support et contact

Pour toute question ou problème, veuillez contacter l'administrateur système.

---

© 2025 Système de Veille Automatisée pour Créatrices OnlyFans
