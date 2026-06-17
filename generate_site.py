"""
generate_site.py
-----------------
Génère un mini-site statique de petites annonces immobilières fictives
sur des localités réelles du Sénégal, à des fins pédagogiques (exercice
de web scraping avec BeautifulSoup).

Le site est volontairement "réaliste mais imparfait" : formats de prix
hétérogènes, surfaces parfois manquantes, casse des villes incohérente,
quelques annonces dupliquées... Ces imperfections sont consignées dans
data/corrige_formateur.json (réservé au formateur) afin de pouvoir
vérifier, plus tard dans le parcours, que les apprenants les détectent
bien lors du module de data cleaning.

Usage :
    pip install jinja2
    python generate_site.py

Sortie :
    site/index.html
    site/annonces/annonce-XXXXX.html  (une page par annonce)
    site/style.css
    site/robots.txt
    data/corrige_formateur.json   (réservé formateur, ne pas distribuer)
"""

import json
import os
import random
import sys
from datetime import date, timedelta

from jinja2 import Environment, FileSystemLoader

# Graine fixe : tout le monde dans la promotion génère exactement le même site
random.seed(42)

SITE_NAME = "Keur Immo"
NB_ANNONCES_UNIQUES = 55  # valeur par défaut
NB_DOUBLONS = 5  # valeur par défaut

# --------------------------------------------------------------------------
# Référentiel géographique (localités réelles du Sénégal)
# --------------------------------------------------------------------------

VILLES_REGION = [
    "Thiès", "Mbour", "Saly Portudal", "Joal-Fadiouth", "Kaolack",
    "Saint-Louis", "Ziguinchor", "Touba", "Diourbel", "Louga",
    "Tambacounda", "Kolda", "Matam", "Fatick", "Richard-Toll",
    "Tivaouane", "Bignona", "Kédougou", "Mboro",
]

QUARTIERS_DAKAR = [
    "Plateau", "Almadies", "Ngor", "Yoff", "Mermoz", "Sacré-Cœur",
    "Point E", "Fann Résidence", "Liberté 6", "Grand Yoff",
    "Parcelles Assainies", "Ouakam", "Hann Mariste", "Médina",
    "Sicap Liberté", "Ouest Foire", "Patte d'Oie", "Cité Keur Gorgui",
    "Mamelles", "Cambérène", "Yarakh", "Colobane", "Derklé",
]
QUARTIERS_PIKINE = ["Pikine Nord", "Pikine Est", "Thiaroye", "Guinaw Rails"]
QUARTIERS_GUEDIAWAYE = ["Golf Sud", "Sam Notaire", "Wakhinane", "Médina Gounass"]
QUARTIERS_RUFISQUE = ["Rufisque Est", "Rufisque Ouest", "Bargny", "Diamniadio"]

VILLES_AVEC_QUARTIERS = {
    "Dakar": QUARTIERS_DAKAR,
    "Pikine": QUARTIERS_PIKINE,
    "Guédiawaye": QUARTIERS_GUEDIAWAYE,
    "Rufisque": QUARTIERS_RUFISQUE,
}

# Pondération : plus d'annonces à Dakar et environs, comme dans la réalité
POOL_VILLES = (
    ["Dakar"] * 9
    + ["Pikine"] * 2
    + ["Guédiawaye"] * 2
    + ["Rufisque"] * 2
    + VILLES_REGION
)

QUARTIERS_PREMIUM = {
    "Almadies", "Ngor", "Point E", "Mermoz", "Fann Résidence", "Cité Keur Gorgui",
}

TYPES_BIEN = ["Appartement", "Villa", "Studio", "Maison", "Duplex", "Terrain"]

SURFACE_RANGES = {
    "Studio": (20, 40),
    "Appartement": (45, 140),
    "Duplex": (90, 220),
    "Maison": (80, 250),
    "Villa": (150, 500),
    "Terrain": (100, 1000),
}
MULTIPLICATEUR_TYPE = {"Villa": 1.3, "Terrain": 0.4, "Studio": 0.9}

# --------------------------------------------------------------------------
# Textes (descriptions, contacts) — rédigés à la main pour rester crédibles
# --------------------------------------------------------------------------

PRENOMS = [
    "Mamadou", "Ousmane", "Abdoulaye", "Moussa", "Ibrahima", "Cheikh", "Modou",
    "El Hadji", "Mariama", "Fatou", "Awa", "Khadija", "Aissatou", "Ndeye",
    "Sokhna", "Bineta", "Astou", "Coumba", "Babacar", "Aliou",
]
NOMS = [
    "Diop", "Ndiaye", "Fall", "Sarr", "Gueye", "Diallo", "Ba", "Sow",
    "Cissé", "Faye", "Diouf", "Mbaye", "Niang", "Thiam", "Sy", "Kane",
]

PHRASES_INTRO = {
    "Appartement": ["Appartement lumineux et bien agencé",
                    "Bel appartement dans une résidence calme",
                    "Appartement moderne avec belle exposition"],
    "Villa": ["Belle villa avec jardin",
              "Villa moderne de standing",
              "Villa spacieuse idéale pour une famille"],
    "Studio": ["Studio fonctionnel et bien entretenu",
               "Petit studio idéal pour un étudiant ou un jeune actif"],
    "Maison": ["Maison familiale à habiter directement",
               "Belle maison traditionnelle dans un quartier calme"],
    "Duplex": ["Duplex récent avec belle hauteur sous plafond",
               "Beau duplex bien agencé sur deux niveaux"],
    "Terrain": ["Terrain viabilisé bien situé",
                "Belle parcelle clôturée, titre foncier disponible"],
}

PHRASES_ATOUTS = [
    "À proximité du marché et des commerces.",
    "Quartier calme et sécurisé.",
    "Proche des écoles et de la mosquée.",
    "Vue dégagée, idéal pour une famille.",
    "À quelques minutes de la plage.",
    "Accès facile à la route nationale.",
    "Proche de l'aéroport international Blaise Diagne.",
    "Quartier résidentiel prisé.",
    "Idéal pour un investissement locatif.",
    "Eau et électricité disponibles.",
    "Voisinage tranquille, peu de passage.",
]

PHRASES_CLOTURE = [
    "Visite sur rendez-vous.",
    "Disponible immédiatement.",
    "Prix légèrement négociable.",
    "Documents en règle.",
    "Affaire à saisir rapidement.",
]

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]


# --------------------------------------------------------------------------
# Fonctions de génération
# --------------------------------------------------------------------------

def choisir_ville_quartier():
    ville = random.choice(POOL_VILLES)
    quartier = random.choice(VILLES_AVEC_QUARTIERS[ville]) if ville in VILLES_AVEC_QUARTIERS else None
    return ville, quartier


def prix_m2_base(ville, quartier):
    if ville == "Dakar" and quartier in QUARTIERS_PREMIUM:
        return (400_000, 900_000)
    if ville in VILLES_AVEC_QUARTIERS:
        return (150_000, 420_000)
    if ville in {"Mbour", "Saly Portudal", "Joal-Fadiouth"}:
        return (150_000, 500_000)  # zone touristique
    return (50_000, 160_000)


def generer_prix_et_surface(type_bien, ville, quartier):
    surf_min, surf_max = SURFACE_RANGES[type_bien]
    surface = round(random.uniform(surf_min, surf_max))
    pm2_min, pm2_max = prix_m2_base(ville, quartier)
    multiplicateur = MULTIPLICATEUR_TYPE.get(type_bien, 1.0)
    prix_m2 = random.uniform(pm2_min, pm2_max) * multiplicateur
    prix_total = surface * prix_m2
    prix_total = round(prix_total / 250_000) * 250_000  # arrondi "réaliste"
    return int(prix_total), surface


def formater_prix(prix):
    """Retourne (texte_affiche, valeur_reelle_ou_None). Introduit des formats hétérogènes."""
    if random.random() < 0.05:
        return "Prix sur demande", None
    fmt = random.choice(["espace", "point", "brut", "millions"])
    if fmt == "espace":
        return f"{prix:,.0f} FCFA".replace(",", " "), prix
    if fmt == "point":
        return f"{prix:,.0f} F CFA".replace(",", "."), prix
    if fmt == "brut":
        return f"{prix} FCFA", prix
    millions = round(prix / 1_000_000)
    return f"{millions} millions FCFA", prix  # approximation volontaire


def formater_surface(surface):
    """Retourne le texte affiché, ou None si le champ est volontairement absent."""
    if random.random() < 0.08:
        return None
    fmt = random.choice(["m2_exp", "m2_simple", "m_ambigu"])
    if fmt == "m2_exp":
        return f"{surface} m²"
    if fmt == "m2_simple":
        return f"{surface}m2"
    return f"{surface} m"  # unité ambiguë, laissée telle quelle


def formater_pieces(type_bien, surface):
    if type_bien in {"Studio", "Terrain"}:
        return None, None
    pieces = max(2, round(surface / 30))
    if random.random() < 0.1:
        return None, pieces  # absent à l'affichage malgré une valeur réelle
    fmt = random.choice(["nombre", "type_t", "texte"])
    if fmt == "nombre":
        return str(pieces), pieces
    if fmt == "type_t":
        return f"T{pieces}", pieces
    return f"{pieces} pièces", pieces


def date_aleatoire():
    debut = date(2024, 1, 1)
    fin = date(2026, 6, 1)
    d = debut + timedelta(days=random.randint(0, (fin - debut).days))
    fmt = random.choice(["iso", "fr_slash", "fr_texte"])
    if fmt == "iso":
        return d.isoformat(), d
    if fmt == "fr_slash":
        return d.strftime("%d/%m/%Y"), d
    return f"{d.day} {MOIS_FR[d.month - 1]} {d.year}", d


def texte_localisation(ville, quartier):
    base = ville if not quartier else f"{ville}, quartier {quartier}"
    style = random.choice(["normal", "normal", "normal", "majuscules", "minuscules"])
    if style == "majuscules":
        return base.upper()
    if style == "minuscules":
        return base.lower()
    return base


def generer_description(type_bien):
    if random.random() < 0.04:
        return ""
    intro = random.choice(PHRASES_INTRO[type_bien])
    atouts = random.sample(PHRASES_ATOUTS, k=random.randint(1, 3))
    cloture = random.choice(PHRASES_CLOTURE)
    return " ".join([intro + "."] + atouts + [cloture])


def generer_contact():
    nom = f"{random.choice(PRENOMS)} {random.choice(NOMS)}"
    prefixe = random.choice(["70", "75", "76", "77", "78"])
    suite = f"{random.randint(0, 999):03d} {random.randint(0, 99):02d} {random.randint(0, 99):02d}"
    return nom, f"+221 {prefixe} {suite}"


def generer_annonce(idx):
    type_bien = random.choice(TYPES_BIEN)
    ville, quartier = choisir_ville_quartier()
    prix_reel, surface_reelle = generer_prix_et_surface(type_bien, ville, quartier)
    prix_affiche, prix_valeur = formater_prix(prix_reel)
    surface_affichee = formater_surface(surface_reelle)
    pieces_affichees, pieces_reelles = formater_pieces(type_bien, surface_reelle)
    date_affichee, date_reelle = date_aleatoire()
    agent, telephone = generer_contact()
    intro = random.choice(PHRASES_INTRO[type_bien])

    annonce = {
        "ref": f"REF-{idx:05d}",
        "slug": f"annonce-{idx:05d}",
        "titre": f"{intro} à {ville}",
        "type_bien": type_bien,
        "ville": ville,
        "quartier": quartier,
        "localisation_texte": texte_localisation(ville, quartier),
        "prix_affiche": prix_affiche,
        "surface_affichee": surface_affichee,
        "pieces_affichees": pieces_affichees,
        "description": generer_description(type_bien),
        "agent": agent,
        "telephone": telephone,
        "date_affichee": date_affichee,
    }

    verite = {
        "ref": annonce["ref"],
        "type_bien": type_bien,
        "ville": ville,
        "quartier": quartier,
        "prix_reel": prix_valeur,
        "surface_reelle": surface_reelle,
        "pieces_reelles": pieces_reelles,
        "date_reelle": date_reelle.isoformat(),
        "doublon_de": None,
    }
    return annonce, verite


def generer_doublons(annonces, verites, n):
    """Republie n annonces existantes sous une nouvelle référence (avec une nouvelle date)."""
    base = random.sample(list(zip(annonces, verites)), k=n)
    nouvelles_annonces, nouvelles_verites = [], []
    for i, (a, v) in enumerate(base):
        idx = NB_ANNONCES_UNIQUES + i + 1
        a2 = dict(a)
        v2 = dict(v)
        a2["ref"] = f"REF-{idx:05d}"
        a2["slug"] = f"annonce-{idx:05d}"
        a2["date_affichee"], nouvelle_date = date_aleatoire()
        v2["ref"] = a2["ref"]
        v2["date_reelle"] = nouvelle_date.isoformat()
        v2["doublon_de"] = v["ref"]
        nouvelles_annonces.append(a2)
        nouvelles_verites.append(v2)
    return nouvelles_annonces, nouvelles_verites


def main():
    global NB_ANNONCES_UNIQUES, NB_DOUBLONS
    
    # Récupérer le nombre d'annonces depuis les arguments en ligne de commande
    if len(sys.argv) > 1:
        try:
            NB_ANNONCES_UNIQUES = int(sys.argv[1])
            if NB_ANNONCES_UNIQUES <= 0:
                raise ValueError("Le nombre d'annonces doit être positif")
            # Calculer le nombre de doublons proportionnel (environ 9% du nombre d'annonces uniques)
            # minimum 1 doublon, maximum 20% du nombre d'annonces
            NB_DOUBLONS = max(1, min(round(NB_ANNONCES_UNIQUES * 0.09), round(NB_ANNONCES_UNIQUES * 0.2)))
        except ValueError as e:
            print(f"Erreur : {e}")
            print("Usage : python generate_site.py [nombre_annonces]")
            print("Exemple : python generate_site.py 1000")
            sys.exit(1)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(os.path.join(base_dir, "templates")))

    annonces, verites = [], []
    for idx in range(1, NB_ANNONCES_UNIQUES + 1):
        a, v = generer_annonce(idx)
        annonces.append(a)
        verites.append(v)

    doublons_a, doublons_v = generer_doublons(annonces, verites, NB_DOUBLONS)
    annonces += doublons_a
    verites += doublons_v
    random.shuffle(annonces)  # ordre d'affichage non trié, comme un vrai site

    site_dir = os.path.join(base_dir, "site")
    annonces_dir = os.path.join(site_dir, "annonces")
    os.makedirs(annonces_dir, exist_ok=True)

    # Page d'accueil
    tpl_index = env.get_template("index.html")
    with open(os.path.join(site_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(tpl_index.render(site_name=SITE_NAME, annonces=annonces))

    # Une page par annonce
    tpl_annonce = env.get_template("annonce.html")
    for a in annonces:
        with open(os.path.join(annonces_dir, f"{a['slug']}.html"), "w", encoding="utf-8") as f:
            f.write(tpl_annonce.render(site_name=SITE_NAME, a=a))

    # robots.txt permissif (site pédagogique, scraping autorisé)
    with open(os.path.join(site_dir, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n")

    # Corrigé formateur (réservé, ne pas distribuer aux apprenants)
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "corrige_formateur.json"), "w", encoding="utf-8") as f:
        json.dump(verites, f, ensure_ascii=False, indent=2)

    print(f"Site généré : {len(annonces)} annonces ({NB_ANNONCES_UNIQUES} uniques + {NB_DOUBLONS} doublons)")
    print(f" -> {site_dir}/index.html")
    print(f" -> {os.path.join(data_dir, 'corrige_formateur.json')} (réservé formateur)")


if __name__ == "__main__":
    main()
