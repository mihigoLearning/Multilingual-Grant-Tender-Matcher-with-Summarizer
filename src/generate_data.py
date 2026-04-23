"""
Synthetic data generator for AIMS KTT T2.2.

Generates:
  tenders/        40 documents (.pdf/.html/.txt), 60% EN / 40% FR
  data/profiles.json       10 business profiles
  data/gold_matches.csv    3 expert-curated matches per profile

Reproducible: seed=42. Runs in <2 minutes on a laptop.
"""

import csv
import json
import os
import random
from datetime import date, timedelta
from pathlib import Path

from fpdf import FPDF

SEED = 42
ROOT = Path(__file__).resolve().parent.parent
TENDERS_DIR = ROOT / "tenders"
DATA_DIR = ROOT / "data"

SECTORS = ["agritech", "healthtech", "cleantech", "edtech", "fintech", "wastetech"]
BUDGETS = [5_000, 50_000, 200_000, 1_000_000]
COUNTRIES = ["Rwanda", "Kenya", "Senegal", "DRC", "Ethiopia"]
REGIONS_EN = ["East Africa", "West Africa", "Pan-African", "Sub-Saharan Africa"]
REGIONS_FR = ["Afrique de l'Est", "Afrique de l'Ouest", "Panafricain", "Afrique subsaharienne"]

# --- Templated boilerplate (bureaucratese) -----------------------------------

BOILERPLATE_EN = [
    "In alignment with regional strategic priorities, this call for proposals invites eligible applicants to submit expressions of interest.",
    "Applicants must demonstrate organisational capacity, financial probity, and a proven track record.",
    "Proposals will be evaluated on technical merit, cost-effectiveness, and alignment with stated outcomes.",
    "All submissions are subject to due diligence and compliance review.",
    "The contracting authority reserves the right to modify or cancel this solicitation at any stage.",
    "Shortlisted candidates may be invited to a clarification interview.",
    "Successful applicants will enter into a performance-based grant agreement.",
]

BOILERPLATE_FR = [
    "Conformément aux priorités stratégiques régionales, cet appel à propositions invite les candidats éligibles à soumettre leur manifestation d'intérêt.",
    "Les candidats doivent démontrer leur capacité organisationnelle, leur probité financière et un historique avéré.",
    "Les propositions seront évaluées sur leur mérite technique, leur rapport coût-efficacité et leur alignement avec les résultats attendus.",
    "Toutes les soumissions font l'objet d'une diligence raisonnable et d'un examen de conformité.",
    "L'autorité contractante se réserve le droit de modifier ou d'annuler cette sollicitation à tout moment.",
    "Les candidats présélectionnés pourront être invités à un entretien de clarification.",
    "Les candidats retenus concluront un accord de subvention basé sur la performance.",
]

# --- Sector descriptions -----------------------------------------------------

SECTOR_DESCRIPTIONS_EN = {
    "agritech": "agricultural technology, smallholder farmer productivity, climate-smart crops, and value-chain innovation",
    "healthtech": "digital health, telemedicine, maternal and child health, and medical supply chains",
    "cleantech": "clean energy, solar off-grid solutions, energy efficiency, and renewable infrastructure",
    "edtech": "educational technology, digital learning platforms, teacher training, and youth skills",
    "fintech": "financial technology, mobile money, digital lending, and financial inclusion",
    "wastetech": "waste management, circular economy, plastic recycling, and urban sanitation",
}

SECTOR_DESCRIPTIONS_FR = {
    "agritech": "technologie agricole, productivité des petits exploitants, cultures résilientes au climat et innovation dans la chaîne de valeur",
    "healthtech": "santé numérique, télémédecine, santé maternelle et infantile, et chaînes d'approvisionnement médical",
    "cleantech": "énergie propre, solutions solaires hors réseau, efficacité énergétique et infrastructures renouvelables",
    "edtech": "technologie éducative, plateformes d'apprentissage numérique, formation des enseignants et compétences des jeunes",
    "fintech": "technologie financière, monnaie mobile, prêts numériques et inclusion financière",
    "wastetech": "gestion des déchets, économie circulaire, recyclage du plastique et assainissement urbain",
}

TITLES_EN = [
    "Call for Proposals: {sector} Innovation Fund",
    "{region} Grant Programme for {sector} Startups",
    "Open Tender: {sector} Pilot Deployment",
    "Catalytic Grant — {sector} Scale-Up",
    "Request for Proposals: {sector} Acceleration Initiative",
]

TITLES_FR = [
    "Appel à Propositions : Fonds d'Innovation {sector}",
    "Programme de Subvention {region} pour Startups {sector}",
    "Appel d'Offres Ouvert : Déploiement Pilote {sector}",
    "Subvention Catalytique — Mise à l'Échelle {sector}",
    "Demande de Propositions : Initiative d'Accélération {sector}",
]


def fmt_budget(amount: int) -> str:
    if amount >= 1_000_000:
        return f"{amount // 1_000_000}M USD"
    return f"{amount // 1000}k USD"


def gen_tender(idx: int, rng: random.Random) -> dict:
    """Build one tender record. 60% EN / 40% FR."""
    lang = "en" if rng.random() < 0.60 else "fr"
    sector = rng.choice(SECTORS)
    budget = rng.choice(BUDGETS)
    region = rng.choice(REGIONS_EN if lang == "en" else REGIONS_FR)
    deadline = date(2026, 1, 1) + timedelta(days=rng.randint(30, 365))

    if lang == "en":
        title = rng.choice(TITLES_EN).format(sector=sector.capitalize(), region=region)
        sector_desc = SECTOR_DESCRIPTIONS_EN[sector]
        boiler = rng.sample(BOILERPLATE_EN, k=3)
        eligibility = (
            f"Eligible applicants: registered enterprises with 2+ years of operation, "
            f"5-50 employees, operating in {region}. Priority for women-led and youth-led ventures."
        )
        body = (
            f"This tender supports {sector_desc}. "
            f"The total available funding is {fmt_budget(budget)}. "
            f"Proposals must be submitted before {deadline.isoformat()}. "
            f"{' '.join(boiler)} "
            f"{eligibility}"
        )
    else:
        title = rng.choice(TITLES_FR).format(sector=sector.capitalize(), region=region)
        sector_desc = SECTOR_DESCRIPTIONS_FR[sector]
        boiler = rng.sample(BOILERPLATE_FR, k=3)
        eligibility = (
            f"Candidats éligibles : entreprises enregistrées avec 2+ ans d'activité, "
            f"5 à 50 employés, opérant en {region}. Priorité aux entreprises dirigées par des femmes et des jeunes."
        )
        body = (
            f"Cet appel d'offres soutient le secteur {sector_desc}. "
            f"Le financement total disponible est de {fmt_budget(budget)}. "
            f"Les propositions doivent être soumises avant le {deadline.isoformat()}. "
            f"{' '.join(boiler)} "
            f"{eligibility}"
        )

    return {
        "id": f"T{idx:03d}",
        "title": title,
        "sector": sector,
        "budget": budget,
        "deadline": deadline.isoformat(),
        "eligibility": eligibility,
        "region": region,
        "lang": lang,
        "body": body,
    }


def write_txt(tender: dict, path: Path) -> None:
    content = (
        f"TITLE: {tender['title']}\n"
        f"SECTOR: {tender['sector']}\n"
        f"BUDGET: {fmt_budget(tender['budget'])}\n"
        f"DEADLINE: {tender['deadline']}\n"
        f"REGION: {tender['region']}\n\n"
        f"{tender['body']}\n"
    )
    path.write_text(content, encoding="utf-8")


def write_html(tender: dict, path: Path) -> None:
    content = f"""<!DOCTYPE html>
<html lang="{tender['lang']}">
<head><meta charset="utf-8"><title>{tender['title']}</title></head>
<body>
<h1>{tender['title']}</h1>
<ul>
  <li><strong>Sector:</strong> {tender['sector']}</li>
  <li><strong>Budget:</strong> {fmt_budget(tender['budget'])}</li>
  <li><strong>Deadline:</strong> {tender['deadline']}</li>
  <li><strong>Region:</strong> {tender['region']}</li>
</ul>
<p>{tender['body']}</p>
</body>
</html>
"""
    path.write_text(content, encoding="utf-8")


def write_pdf(tender: dict, path: Path) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    # fpdf2 default font doesn't support all unicode; strip accents for PDF only.
    safe = lambda s: s.encode("latin-1", "replace").decode("latin-1")
    pdf.multi_cell(0, 8, safe(tender["title"]))
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 11)
    meta = (
        f"Sector: {tender['sector']}\n"
        f"Budget: {fmt_budget(tender['budget'])}\n"
        f"Deadline: {tender['deadline']}\n"
        f"Region: {tender['region']}\n"
    )
    pdf.multi_cell(0, 6, safe(meta))
    pdf.ln(2)
    pdf.multi_cell(0, 6, safe(tender["body"]))
    pdf.output(str(path))


# --- Profile generation ------------------------------------------------------

PROFILE_NEEDS_EN = {
    "agritech": "We support smallholder farmers with mobile advisory services and need working capital to scale our outreach across rural districts.",
    "healthtech": "Our clinic network delivers maternal health services and we seek funds to digitise patient records and expand telemedicine.",
    "cleantech": "We install solar home systems for off-grid households and are looking for growth capital to open new distribution hubs.",
    "edtech": "We run a digital learning platform for secondary school students and seek funding to localise content and train teachers.",
    "fintech": "We operate a mobile lending product for informal traders and need capital to upgrade our credit scoring and expand coverage.",
    "wastetech": "We recycle plastic waste into construction materials and are seeking grants to scale collection logistics and equipment.",
}

PROFILE_NEEDS_FR = {
    "agritech": "Nous soutenons les petits exploitants agricoles avec des services de conseil mobile et recherchons un fonds de roulement pour développer notre présence rurale.",
    "healthtech": "Notre réseau de cliniques offre des services de santé maternelle et nous cherchons des fonds pour numériser les dossiers et étendre la télémédecine.",
    "cleantech": "Nous installons des systèmes solaires domestiques hors réseau et recherchons du capital de croissance pour ouvrir de nouveaux centres de distribution.",
    "edtech": "Nous exploitons une plateforme d'apprentissage numérique pour lycéens et cherchons un financement pour localiser le contenu et former les enseignants.",
    "fintech": "Nous offrons un produit de prêt mobile pour commerçants informels et avons besoin de capitaux pour améliorer notre scoring et étendre la couverture.",
    "wastetech": "Nous recyclons les déchets plastiques en matériaux de construction et cherchons des subventions pour déployer la logistique de collecte.",
}


def gen_profiles(rng: random.Random) -> list[dict]:
    profiles = []
    sectors = (SECTORS * 2)[:10]  # ensure distribution across all 6 sectors
    rng.shuffle(sectors)
    for i in range(10):
        sector = sectors[i]
        country = rng.choice(COUNTRIES)
        employees = rng.choice([6, 12, 20, 35, 48])
        # Language preference: ~50/50 EN/FR, DRC/Senegal lean FR
        if country in ("DRC", "Senegal"):
            lang = rng.choice(["fr", "fr", "en"])
        else:
            lang = rng.choice(["en", "en", "fr"])
        needs_text = PROFILE_NEEDS_FR[sector] if lang == "fr" else PROFILE_NEEDS_EN[sector]
        past_funding = rng.choice([0, 10_000, 50_000, 120_000])
        profiles.append({
            "id": f"P{i+1:02d}",
            "sector": sector,
            "country": country,
            "employees": employees,
            "languages": [lang, "en"] if lang == "fr" else [lang],
            "needs_text": needs_text,
            "past_funding": past_funding,
        })
    return profiles


# --- Gold matches ------------------------------------------------------------

def gen_gold_matches(profiles: list[dict], tenders: list[dict]) -> list[tuple[str, str, int]]:
    """
    For each profile, pick 3 tenders judged 'most relevant':
      - sector must match (hard filter)
      - prefer budget fit vs. past_funding size
      - prefer matching region-ish language family
      - tie-break deterministically by tender id
    """
    rows = []
    for p in profiles:
        candidates = [t for t in tenders if t["sector"] == p["sector"]]

        def score(t):
            s = 0
            # Budget fit: closer to 3x-10x past_funding is "right size"
            target = max(p["past_funding"] * 5, 50_000)
            s += -abs(t["budget"] - target) / 1e5
            # Language match is a bonus (entrepreneur's primary lang)
            if t["lang"] == p["languages"][0]:
                s += 1.0
            # Deadline: further away = more realistic to apply
            s += 0.001 * int(t["deadline"].replace("-", ""))
            return s

        ranked = sorted(candidates, key=score, reverse=True)[:3]
        for rank, t in enumerate(ranked, start=1):
            rows.append((p["id"], t["id"], rank))
    return rows


# --- Orchestration -----------------------------------------------------------

def main():
    rng = random.Random(SEED)
    TENDERS_DIR.mkdir(exist_ok=True, parents=True)
    DATA_DIR.mkdir(exist_ok=True, parents=True)

    # Clean old tender files
    for p in TENDERS_DIR.glob("T*"):
        p.unlink()

    tenders = [gen_tender(i, rng) for i in range(1, 41)]

    # Distribute formats: ~24 .txt, ~12 .html, ~4 .pdf
    format_plan = (["txt"] * 24) + (["html"] * 12) + (["pdf"] * 4)
    rng.shuffle(format_plan)

    for tender, fmt in zip(tenders, format_plan):
        path = TENDERS_DIR / f"{tender['id']}.{fmt}"
        if fmt == "txt":
            write_txt(tender, path)
        elif fmt == "html":
            write_html(tender, path)
        else:
            write_pdf(tender, path)
        tender["_path"] = str(path.relative_to(ROOT))
        tender["_format"] = fmt

    # Write tender index for evaluation convenience
    index = [{k: v for k, v in t.items() if k != "body"} for t in tenders]
    (DATA_DIR / "tender_index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Profiles
    profiles = gen_profiles(rng)
    (DATA_DIR / "profiles.json").write_text(
        json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Gold matches
    gold = gen_gold_matches(profiles, tenders)
    with (DATA_DIR / "gold_matches.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["profile_id", "tender_id", "rank"])
        w.writerows(gold)

    # Summary
    lang_counts = {"en": sum(1 for t in tenders if t["lang"] == "en"),
                   "fr": sum(1 for t in tenders if t["lang"] == "fr")}
    fmt_counts = {f: format_plan.count(f) for f in ("txt", "html", "pdf")}
    print(f"Generated {len(tenders)} tenders  (EN={lang_counts['en']}, FR={lang_counts['fr']})")
    print(f"Formats: {fmt_counts}")
    print(f"Profiles: {len(profiles)}  Gold matches: {len(gold)}")
    print(f"Output: {TENDERS_DIR}, {DATA_DIR}")


if __name__ == "__main__":
    main()
