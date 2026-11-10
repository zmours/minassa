#!/usr/bin/env python3
"""Construit les pages du hub minassa.fr.

Lit `donnees/ecoles.json`, interroge le catalogue public de chaque école
(`/api/public/catalog/courses?domain=`), rapatrie les couvertures et écrit :

- index.html                    l'accueil
- cours/index.html              le catalogue filtrable
- cours/<école>/<id>/index.html une fiche par cours d'école partenaire
- apprendre/index.html          les parcours d'arabe et la plateforme à venir
- sitemap.xml

Les pages /cours-femmes/ et /cours-coran/ ne sont pas touchées (A-2).

Bibliothèque standard seulement. Le résultat ne dépend que des données lues :
deux constructions sur les mêmes catalogues donnent les mêmes fichiers, pour
que la reconstruction nocturne ne commite que les vrais changements.

    python3 outils/construire.py            # lit l'API de production
    python3 outils/construire.py --hors-ligne  # garde les couvertures déjà là
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import shutil
import sys
import unicodedata
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
GABARITS = Path(__file__).resolve().parent / "gabarits"
API = "https://api.madrassanet.com/api"
SITE = "https://minassa.fr"
MADRASSANET = "https://www.madrassanet.com"
AGENT = "minassa-hub/1.0 (+https://minassa.fr)"
HORS_LIGNE = "--hors-ligne" in sys.argv

MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MOIS_LONGS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
              "octobre", "novembre", "décembre"]
LANGUES = {"fr": "en français", "ar": "en arabe", "en": "en anglais"}
PUBLICS = [("tous", "Tous"), ("femmes", "Sœurs"), ("hommes", "Hommes"), ("ados", "Adolescents")]

e = html.escape


# ── Icônes ──────────────────────────────────────────────────────────────────

def svg(chemins: str, taille: int = 24, epaisseur: float = 2) -> str:
    return (f'<svg width="{taille}" height="{taille}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="{epaisseur}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{chemins}</svg>')


I_EXTERNE = svg('<path d="M14 4h6v6"></path><path d="M20 4l-9 9"></path>'
                '<path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"></path>', 16, 2.2)
I_INFO = svg('<circle cx="12" cy="12" r="9"></circle><path d="M12 8h.01M11 12h1v5h1"></path>', 16)
I_CALENDRIER = svg('<rect x="3" y="5" width="18" height="16" rx="2"></rect><path d="M3 10h18M8 3v4M16 3v4"></path>', 18)
I_ECRAN = svg('<rect x="3" y="4" width="18" height="12" rx="2"></rect><path d="M8 20h8M12 16v4"></path>', 18)
I_PERSONNES = svg('<circle cx="9" cy="8" r="3.5"></circle><path d="M2.5 20c.8-3.5 3.4-5.5 6.5-5.5s5.7 2 6.5 5.5'
                  'M16 4.5a3.5 3.5 0 0 1 0 7M18 14.8c1.8.7 3 2.5 3.5 5.2"></path>', 18)


# ── Utilitaires ─────────────────────────────────────────────────────────────

def date_fr(iso: str | None, longue: bool = False, annee: bool = True) -> str:
    if not iso:
        return ""
    d = dt.date.fromisoformat(iso[:10])
    mois = (MOIS_LONGS if longue else MOIS)[d.month - 1]
    jour = "1er" if d.day == 1 else str(d.day)
    return f"{jour} {mois}" + (f" {d.year}" if annee else "")


def prix_fr(montant: float | None, devise: str | None) -> str:
    if not montant:
        return "Gratuit"
    entier = int(montant) if float(montant).is_integer() else montant
    texte = f"{entier:,}".replace(",", " ").replace(".", ",")
    return f"{texte} €" if (devise or "EUR") == "EUR" else f"{texte} {devise}"


def sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn").lower()


def initiales(nom: str) -> str:
    morceaux = [m for m in re.split(r"[\s-]+", nom) if m]
    return "".join(m[0] for m in morceaux[:2]).upper()


def lire_json(url: str):
    requete = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        return json.load(reponse)


def telecharger(url: str, cible: Path) -> bool:
    if HORS_LIGNE:
        return cible.exists()
    try:
        requete = urllib.request.Request(url, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            contenu = reponse.read()
    except Exception as err:  # une couverture absente ne bloque pas la construction
        print(f"  ! couverture non lue : {url} ({err})")
        return cible.exists()
    cible.parent.mkdir(parents=True, exist_ok=True)
    if not cible.exists() or cible.read_bytes() != contenu:
        cible.write_bytes(contenu)
    return True


def ecrire(chemin: Path, contenu: str) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding="utf-8")


def gabarit(nom: str) -> str:
    return (GABARITS / nom).read_text(encoding="utf-8")


def remplir(modele: str, valeurs: dict[str, str]) -> str:
    def remplacer(m):
        cle = m.group(1)
        if cle not in valeurs:
            raise KeyError(f"marque {{{{{cle}}}}} sans valeur")
        return valeurs[cle]
    return re.sub(r"\{\{([A-Z_]+)\}\}", remplacer, modele)


# ── Gabarit commun ──────────────────────────────────────────────────────────

def tete(titre: str, description: str, chemin: str, image: str = "/og-image.jpg", extra: str = "") -> str:
    url = SITE + chemin
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titre)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Minassa">
<meta property="og:title" content="{e(titre)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}{image}">
<meta property="og:locale" content="fr_FR">
<meta name="theme-color" content="#0B4F4A">
<link rel="icon" type="image/svg+xml" href="/assets/logo/minassa-icone.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Naskh+Arabic:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/minassa.css">
{extra}</head>
<body>
"""


def entete(actif: str = "") -> str:
    def lien(href: str, texte: str, cle: str) -> str:
        courant = ' aria-current="page"' if cle == actif else ""
        return f'<a href="{href}"{courant}>{texte}</a>'
    return f"""<header class="entete">
  <div class="conteneur entete__in">
    <a href="/" class="entete__logo" aria-label="Minassa, accueil"><img src="/assets/logo/minassa-logo.svg" alt="Minassa منصّة" width="160" height="44"></a>
    <nav class="nav" aria-label="Navigation principale">
      {lien("/cours/", "Cours", "cours")}
      {lien("/apprendre/", "Apprendre", "apprendre")}
      {lien("/#ecoles", "Écoles", "ecoles")}
      <a href="/#votre-ecole" class="nav__ecole">Votre école sur Minassa</a>
    </nav>
  </div>
</header>
"""


def pied() -> str:
    return f"""<footer class="pied">
  <div class="conteneur pied__in">
    <div class="pied__marque">
      <img src="/assets/logo/minassa-logo-inverse.svg" alt="Minassa منصّة" width="175" height="48">
      <p>Minassa présente les cours des écoles. Chaque école inscrit ses élèves et encaisse elle-même.</p>
    </div>
    <nav aria-label="Minassa">
      <strong>Minassa</strong>
      <a href="/cours/">Cours</a><a href="/apprendre/">Apprendre</a><a href="/#ecoles">Écoles</a>
    </nav>
    <nav aria-label="Écoles">
      <strong>Écoles</strong>
      <a href="/#votre-ecole">Votre école sur Minassa</a>
    </nav>
    <nav aria-label="Plateforme">
      <strong>Plateforme</strong>
      <a href="{MADRASSANET}" target="_blank" rel="noopener">MadrassaNET {I_EXTERNE}</a>
      <a href="/#plateforme">Suivre ses cours en ligne</a>
    </nav>
    <nav aria-label="Informations">
      <strong>Informations</strong>
      <a href="/mentions-legales.html">Mentions légales</a>
      <a href="/politique-confidentialite.html">Confidentialité</a>
      <a href="mailto:contact@minassa.fr">contact@minassa.fr</a>
    </nav>
  </div>
  <div class="conteneur pied__bas">
    <span>© 2026 Minassa</span>
    <span>Plateforme d'apprentissage : <a href="{MADRASSANET}" target="_blank" rel="noopener">MadrassaNET</a></span>
  </div>
</footer>
"""


def page(titre, description, chemin, corps, actif="", image="/og-image.jpg", extra_tete="", scripts="") -> str:
    return (tete(titre, description, chemin, image, extra_tete) + entete(actif) + "<main>\n" + corps
            + "</main>\n" + pied() + scripts + "</body>\n</html>\n")


# ── Données ─────────────────────────────────────────────────────────────────

def charger_cours(config: dict) -> list[dict]:
    """Les cours ouverts de chaque école partenaire, dans l'ordre de ecoles.json."""
    aujourdhui = dt.date.today().isoformat()
    tous = []
    for ecole in config["ecoles"]:
        url = f"{API}/public/catalog/courses?domain={ecole['domaine']}"
        print(f"→ {ecole['nomCourt']} : {url}")
        cours = lire_json(url)  # une école illisible arrête tout : on ne publie pas un catalogue amputé
        for c in sorted(cours, key=lambda c: c["id"]):
            if not c.get("enrollmentOpen", True):
                continue
            if c.get("enrollmentDeadline") and c["enrollmentDeadline"] < aujourdhui:
                continue
            c["_ecole"] = ecole
            c["_chemin"] = f"/cours/{ecole['code']}/{c['id']}/"
            couverture = c.get("coverImageUrl")
            c["_image"] = None
            if couverture:
                source = couverture if couverture.startswith("http") else API + couverture
                cible = RACINE / "assets" / "couvertures" / f"{ecole['code']}-{c['id']}.jpg"
                if telecharger(source, cible):
                    c["_image"] = f"/assets/couvertures/{cible.name}"
            tous.append(c)
        print(f"  {len([c for c in tous if c['_ecole'] is ecole])} cours ouverts")
    return tous


def info_cours(c: dict) -> list[str]:
    ecole = c["_ecole"]
    morceaux = []
    horaire = ecole.get("horaires", {}).get(str(c["id"]))
    if horaire:
        morceaux.append(horaire)
    if c.get("totalHours"):
        morceaux.append(f"{c['totalHours']} h")
    if ecole.get("publicLibelle"):
        morceaux.append(ecole["publicLibelle"])
    if c.get("language") in LANGUES:
        morceaux.append(LANGUES[c["language"]].replace("en ", "").capitalize())
    return morceaux


def etat_cours(c: dict) -> str:
    if c.get("enrollmentDeadline"):
        return f"Inscriptions jusqu'au {date_fr(c['enrollmentDeadline'], annee=False)}"
    return "Inscriptions ouvertes"


def logo_ecole(ecole: dict, classe: str = "sigle") -> str:
    return (f'<span class="{classe}" aria-hidden="true" style="background: {ecole["fond"]}; color: {ecole["accent"]}; '
            f'box-shadow: inset 0 0 0 2px {ecole["accent"]}">{e(ecole["sigle"])}</span>')


LOGO_MINASSA = '<img src="/assets/logo/minassa-icone.svg" alt="" width="22" height="22">'


def image_ou_vide(src: str | None, alt: str = "") -> str:
    if src:
        return f'<img src="{src}" alt="{e(alt)}" loading="lazy" width="640" height="360">'
    return '<div class="couverture-vide" aria-hidden="true">اِقْرَأْ</div>'


# ── Cartes ──────────────────────────────────────────────────────────────────

def carte_accueil_ecole(c: dict) -> str:
    ecole = c["_ecole"]
    return f"""      <a href="{c['_chemin']}" class="carte carte-cours">
        {image_ou_vide(c['_image'])}
        <div class="carte-cours__corps">
          <span class="ecole-ligne">{logo_ecole(ecole)}{e(ecole['nomCourt'])}</span>
          <span class="carte-cours__nom">{e(c['name'])}</span>
          <span class="carte-cours__info">{e(' · '.join(info_cours(c)))}</span>
          <span class="carte-cours__bas"><span class="prix">{prix_fr(c.get('price'), c.get('currency'))}</span><span class="pastille pastille--ecole">{e(etat_cours(c).replace("Inscriptions j", "J"))}</span></span>
        </div>
      </a>
"""


def carte_accueil_offre(o: dict) -> str:
    return f"""      <a href="{o['lien']}" class="carte carte-cours">
        {image_ou_vide(o['image'])}
        <div class="carte-cours__corps">
          <span class="ecole-ligne">{LOGO_MINASSA}Minassa</span>
          <span class="carte-cours__nom">{e(o['nom'])}</span>
          <span class="carte-cours__info">{e(o['infoCourte'])}</span>
          <span class="carte-cours__bas"><span class="prix">{e(o['prix'])} <small>{e(o['periode'])}</small></span><span class="pastille pastille--pre">Préinscription</span></span>
        </div>
      </a>
"""


def ligne_catalogue(*, cle, publics, texte, image, ecole_html, nom, resume, puces, prix, etat, etat_classe, lien, cta) -> str:
    puces_html = "".join(f'<span class="puce">{e(p)}</span>' for p in puces)
    return f"""        <article class="carte ligne-cours" data-ecole="{cle}" data-publics="{' '.join(publics)}" data-texte="{e(sans_accents(texte))}">
          <div class="ligne-cours__image">{image}</div>
          <div class="ligne-cours__corps">
            <span class="ecole-ligne">{ecole_html}</span>
            <h2>{e(nom)}</h2>
            <p>{e(resume)}</p>
            <div class="puces">{puces_html}</div>
          </div>
          <div class="ligne-cours__action">
            <span class="prix">{prix}</span>
            <span class="pastille {etat_classe}">{e(etat)}</span>
            <a href="{lien}" class="btn">{cta}</a>
          </div>
        </article>
"""


# ── Pages ───────────────────────────────────────────────────────────────────

def construire_accueil(config, cours) -> str:
    offres = config["offresMinassa"]
    cartes = "".join(carte_accueil_ecole(c) for c in cours[:4]) + "".join(carte_accueil_offre(o) for o in offres)
    nb = len(cours) + len(offres)

    ecoles = ""
    for ecole in config["ecoles"]:
        n = len([c for c in cours if c["_ecole"] is ecole])
        ecoles += f"""      <a href="/cours/?ecole={ecole['code']}" class="carte carte-ecole">
        {logo_ecole(ecole, 'carte-ecole__logo')}
        <span class="carte-ecole__texte">
          <span class="carte-ecole__nom">{e(ecole['nom'])}</span>
          <span class="entree__texte">{e(ecole['presentation'])}</span>
          <span class="entree__lien">{n} cours →</span>
        </span>
      </a>
"""
    ecoles += f"""      <a href="/cours/?ecole=minassa" class="carte carte-ecole">
        <img class="carte-ecole__logo" src="/assets/logo/minassa-icone.svg" alt="" width="72" height="72">
        <span class="carte-ecole__texte">
          <span class="carte-ecole__nom">Minassa</span>
          <span class="entree__texte">Mémorisation du Coran, tilâwa et tajwîd, en petits groupes : cours pour les sœurs, et le week-end pour hommes et adolescents.</span>
          <span class="entree__lien">{len(offres)} offres →</span>
        </span>
      </a>
"""
    nb_ecoles = len(config["ecoles"]) + 1
    corps = remplir(gabarit("accueil.html"), {
        "NB_COURS": f"{nb} cours ouverts" if nb > 1 else "1 cours ouvert",
        "NB_ECOLES": f"{nb_ecoles} écoles",
        "CARTES_COURS": cartes,
        "ECOLES": ecoles,
        "MADRASSANET": MADRASSANET,
        "I_EXTERNE": I_EXTERNE,
        "I_INFO": I_INFO,
    })
    return page("Minassa — cours d'arabe, de Coran et de sciences islamiques en ligne",
                "Les cours en direct des écoles en ligne, les préinscriptions Minassa et les parcours d'arabe à suivre à son rythme.",
                "/", corps)


def construire_catalogue(config, cours) -> str:
    lignes = ""
    for c in cours:
        ecole = c["_ecole"]
        puces = info_cours(c)
        texte = " ".join([c["name"], c.get("description") or "", ecole["nomCourt"], *c.get("categories", [])])
        lignes += ligne_catalogue(
            cle=ecole["code"], publics=ecole["publics"], texte=texte, image=image_ou_vide(c["_image"]),
            ecole_html=logo_ecole(ecole) + e(ecole["nomCourt"]), nom=c["name"], resume=c.get("description") or "",
            puces=puces, prix=prix_fr(c.get("price"), c.get("currency")), etat=etat_cours(c),
            etat_classe="pastille--ecole", lien=c["_chemin"], cta="Voir le cours")
    for o in config["offresMinassa"]:
        texte = " ".join([o["nom"], o["resume"], "Minassa", "Coran tajwid tajweed tilawa hifz memorisation"])
        lignes += ligne_catalogue(
            cle="minassa", publics=o["publics"], texte=texte, image=image_ou_vide(o["image"]),
            ecole_html=LOGO_MINASSA + "Minassa", nom=o["nom"], resume=o["resume"], puces=o["puces"],
            prix=f"{e(o['prix'])} <small>{e(o['periode'])}</small>", etat="Préinscription",
            etat_classe="pastille--pre", lien=o["lien"], cta="Se préinscrire")

    def boutons(nom, options):
        return "".join(
            f'<button type="button" class="filtre" data-filtre="{nom}" data-valeur="{v}" aria-pressed="{"true" if i == 0 else "false"}">{e(l)}</button>'
            for i, (v, l) in enumerate(options))

    options_ecoles = [("toutes", "Toutes"), ("minassa", "Minassa")] + [(x["code"], x["nomCourt"]) for x in config["ecoles"]]
    corps = remplir(gabarit("cours.html"), {
        "FILTRES_PUBLIC": boutons("pour", PUBLICS),
        "FILTRES_ECOLE": boutons("ecole", options_ecoles),
        "LIGNES": lignes,
        "NB": str(len(cours) + len(config["offresMinassa"])),
    })
    return page("Les cours en direct — Minassa",
                "Cours de Coran, d'arabe et de sciences islamiques en direct : les préinscriptions Minassa et les cours des écoles partenaires.",
                "/cours/", corps, actif="cours", scripts='<script src="/assets/minassa.js" defer></script>\n')


def construire_fiche(c) -> str:
    ecole = c["_ecole"]
    inscription = f"https://{ecole['domaine']}/signup?courseId={c['id']}"
    objectifs = [l.strip() for l in (c.get("objectives") or "").splitlines() if l.strip()]
    paragraphes = [p.strip() for p in (c.get("longDescription") or "").split("\n\n") if p.strip()]
    enseignants = [t["name"] for t in (c.get("teachers") or []) if t.get("name")]
    horaire = ecole.get("horaires", {}).get(str(c["id"]))
    dates = ""
    if c.get("startDate") and c.get("endDate"):
        dates = f"{date_fr(c['startDate'])} → {date_fr(c['endDate'])}"

    chiffres = []
    if dates:
        chiffres.append(("Dates", dates))
    if c.get("totalHours"):
        chiffres.append(("Volume", f"{c['totalHours']} heures"))
    chiffres.append(("Format", "En ligne, en direct" if c.get("deliveryMode") == "ONLINE" else "En présentiel"))
    public = " · ".join(x for x in [ecole.get("publicLibelle"), LANGUES.get(c.get("language"), "")] if x)
    if public:
        chiffres.append(("Public", public))
    chiffres_html = "".join(f'<div class="chiffre"><div class="chiffre__label">{e(a)}</div><div class="chiffre__valeur">{e(b)}</div></div>' for a, b in chiffres)

    blocs = [f'<div class="chiffres">{chiffres_html}</div>']
    if objectifs:
        blocs.append('<div><h2>Ce que vous apprendrez</h2><ul class="liste-losanges">'
                     + "".join(f"<li>{e(o)}</li>" for o in objectifs) + "</ul></div>")
    if paragraphes:
        blocs.append("<div><h2>Le cours</h2>" + "".join(f"<p>{e(p)}</p>" for p in paragraphes) + "</div>")
    if c.get("prerequisites"):
        blocs.append(f'<div class="encadre"><h2>Prérequis</h2><p>{e(c["prerequisites"])}</p></div>')
    if enseignants:
        blocs.append('<div><h2>Les enseignants</h2><div class="enseignants">' + "".join(
            f'<div class="enseignant"><span class="initiales" aria-hidden="true">{e(initiales(n))}</span>{e(n)}</div>'
            for n in enseignants) + "</div></div>")

    infos = []
    if horaire:
        infos.append(f"<span>{I_CALENDRIER}{e(horaire)}</span>")
    if c.get("deliveryMode") == "ONLINE":
        infos.append(f"<span>{I_ECRAN}Classe virtuelle, avec rediffusions</span>")
    if c.get("seatsAvailable"):
        infos.append(f"<span>{I_PERSONNES}Places disponibles</span>")
    echeance = (f'<span class="pastille pastille--ecole">Inscriptions jusqu\'au {date_fr(c["enrollmentDeadline"], longue=True)}</span>'
                if c.get("enrollmentDeadline") else "")
    categories = "".join(f"<span>{e(x)}</span>" for x in c.get("categories") or [])
    image = (f'<img src="{c["_image"]}" alt="" width="480" height="270">' if c["_image"] else "")

    jsonld = {
        "@context": "https://schema.org", "@type": "Course", "name": c["name"],
        "description": c.get("description") or "", "inLanguage": c.get("language") or "fr",
        "url": SITE + c["_chemin"],
        "provider": {"@type": "Organization", "name": ecole["nom"], "url": f"https://{ecole['domaine']}"},
        "offers": {"@type": "Offer", "price": c.get("price") or 0, "priceCurrency": c.get("currency") or "EUR",
                   "url": inscription, "category": "Paid" if c.get("price") else "Free"},
        "hasCourseInstance": {"@type": "CourseInstance", "courseMode": "online",
                              **({"startDate": c["startDate"]} if c.get("startDate") else {}),
                              **({"endDate": c["endDate"]} if c.get("endDate") else {})},
    }
    corps = f"""<section class="fiche-tete" style="--ecole-fond: {ecole['fond']}; --ecole-accent-trait: {ecole['accent']}99; --ecole-accent-texte: {ecole.get('accentTexte', ecole['accent'])}">
  <div class="conteneur fiche-tete__in">
    <nav class="ariane" aria-label="Fil d'Ariane"><a href="/">Accueil</a> › <a href="/cours/">Cours</a> › {e(ecole['nomCourt'])}</nav>
    <div class="fiche-tete__ligne">
      <div class="fiche-tete__texte">
        <span class="fiche-tete__ecole">{logo_ecole(ecole)}{e(ecole['nom'])}</span>
        <h1>{e(c['name'])}</h1>
        <p class="fiche-tete__chapo">{e(c.get('description') or '')}</p>
        <div class="fiche-tete__cats">{categories}</div>
      </div>
      {image}
    </div>
  </div>
</section>
<section class="conteneur fiche-corps">
  <div class="fiche-principal">
    {''.join(blocs)}
  </div>
  <aside class="inscription" aria-label="Inscription">
    <div class="inscription__prix"><strong>{prix_fr(c.get('price'), c.get('currency'))}</strong></div>
    {echeance}
    <a href="{inscription}" class="btn btn--terre" rel="noopener">S'inscrire sur le site de l'école {I_EXTERNE}</a>
    <p class="inscription__note">Vous continuez sur <strong>{e(ecole['domaine'])}</strong>. L'inscription et le paiement se font auprès de l'école.</p>
    <div class="inscription__infos">{''.join(infos)}</div>
  </aside>
</section>
"""
    extra = '<script type="application/ld+json">' + json.dumps(jsonld, ensure_ascii=False) + "</script>\n"
    return page(f"{c['name']} — {ecole['nomCourt']} | Minassa", c.get("description") or c["name"], c["_chemin"],
                corps, actif="cours", image=c["_image"] or "/og-image.jpg", extra_tete=extra)


def construire_apprendre() -> str:
    corps = remplir(gabarit("apprendre.html"), {})
    return page("Apprendre l'arabe, de 3 ans à l'âge adulte — Minassa",
                "Neuf parcours d'arabe qui s'enchaînent, et bientôt une plateforme complète pour les suivre en autonomie : vidéos, audio, fiches, exercices et quiz.",
                "/apprendre/", corps, actif="apprendre",
                extra_tete='<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>\n',
                scripts='<script src="/assets/minassa.js" defer></script>\n')


def construire_sitemap(cours) -> str:
    chemins = ["/", "/cours/", "/apprendre/", "/cours-femmes/", "/cours-coran/"] + [c["_chemin"] for c in cours]
    urls = "".join(f"  <url><loc>{SITE}{p}</loc></url>\n" for p in chemins)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'


def main() -> None:
    config = json.loads((RACINE / "donnees" / "ecoles.json").read_text(encoding="utf-8"))
    cours = charger_cours(config)

    # Les fiches sont entièrement générées : on repart de zéro pour effacer les cours fermés.
    for dossier in (RACINE / "cours").glob("*/"):
        if dossier.is_dir():
            shutil.rmtree(dossier)
    gardees = {f"{c['_ecole']['code']}-{c['id']}.jpg" for c in cours}
    for image in (RACINE / "assets" / "couvertures").glob("*.jpg"):
        if image.name not in gardees:
            image.unlink()

    ecrire(RACINE / "index.html", construire_accueil(config, cours))
    ecrire(RACINE / "cours" / "index.html", construire_catalogue(config, cours))
    for c in cours:
        ecrire(RACINE / c["_chemin"].strip("/") / "index.html", construire_fiche(c))
    ecrire(RACINE / "apprendre" / "index.html", construire_apprendre())
    ecrire(RACINE / "sitemap.xml", construire_sitemap(cours))
    print(f"✓ {len(cours)} cours d'écoles, {len(config['offresMinassa'])} offres Minassa")


if __name__ == "__main__":
    main()
