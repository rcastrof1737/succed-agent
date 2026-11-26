"""Generate the SYNTHETIC demo dataset (fictitious companies). Seeded for reproducibility."""
import csv, json, random
from pathlib import Path

random.seed(7)
OUT = Path(__file__).resolve().parent.parent / "data" / "sample"
OUT.mkdir(parents=True, exist_ok=True)
names = ["Cóndor","Puma","Ceibo","Quetzal","Araucaria","Colibrí","Lince","Olivo","Roble","Halcón","Nogal",
         "Alerce","Tucán","Jaguar","Pehuén","Cedro","Llama","Cardón","Delta","Faro","Brújula","Ancla","Vértice",
         "Atlas","Orion","Sierra","Pampa","Mistral","Boreal","Aurora","Lago","Volcán","Bahía","Cumbre","Prisma",
         "Altair","Sol","Luna","Norte","Andes"]
countries = ["US","US","US","ES","ES","CL","MX","CO","PE"]
sectors = [("b2b_services","Facility maintenance services under multi-year contracts"),
           ("software","Vertical SaaS for logistics operators"),
           ("distribution","Specialty industrial parts distribution"),
           ("education","Corporate training and certification"),
           ("healthcare_services","Outpatient dental and imaging network"),
           ("testing_inspection","Environmental testing laboratory"),
           ("manufacturing","Packaging manufacturing with heavy presses"),
           ("b2b_services","IT managed services for mid-market firms")]
levers = ["sales","pricing","digital","ops","m&a"]
rows = []
for i, n in enumerate(names):
    sec, desc = sectors[i % len(sectors)]
    ebitda = round(random.choice([0.6, 1.2, 1.8, 2.2, 2.6, 3.1, 3.8, 4.5, 6.5]) * random.uniform(0.9, 1.1), 2)
    margin = round(random.uniform(8, 30), 1)
    rev = round(ebitda / (margin / 100), 2)
    mult = random.uniform(5.0, 7.5)
    known = random.random()
    r = {
        "company_id": f"c-{i+1:03d}", "alias": f"Proyecto {n}", "country": countries[i % len(countries)],
        "sector": sec, "business_model": sec, "description": desc + " (synthetic demo company)",
        "source": random.choice(["partner:demo_marketplace", "registry", "off_market_agent"]),
        "revenue_usd_m": rev, "ebitda_usd_m": ebitda,
        "ev_usd_m": round(ebitda * mult, 1) if known > 0.25 else "",
        "ebitda_margin_pct": margin,
        "fcf_conversion_pct": round(random.uniform(45, 90), 0) if known > 0.15 else "",
        "recurring_revenue_pct": round(random.uniform(10, 90), 0),
        "top_customer_pct": round(random.choice([6, 9, 12, 18, 25, 35]), 0),
        "capex_pct_revenue": 11 if sec == "manufacturing" else round(random.uniform(1, 6), 1),
        "revenue_growth_pct": round(random.uniform(-3, 14), 1),
        "years_of_financials": random.choice([2, 3, 3, 5]) if known > 0.2 else "",
        "second_tier_management": random.choice(["true", "true", "false"]) if known > 0.3 else "",
        "owner_transition_months": random.choice([3, 6, 12, 12]) if known > 0.3 else "",
        "owner_age": random.choice([48, 56, 61, 64, 68]),
        "defensibility_rating": random.choice([2, 3, 3.5, 4]),
        "improvement_levers": "|".join(random.sample(levers, 2)),
        "flag_heavily_regulated": "true" if sec == "healthcare_services" else "",
        "flag_distressed": "true" if i == 13 else "",
        "flag_owner_holds_all_relationships": "true" if i % 11 == 5 else "",
    }
    rows.append(r)
with open(OUT / "companies.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
print("companies:", len(rows))
