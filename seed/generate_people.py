"""Grow Brambleworks from 25 to 120 people.

Additive on purpose: E01 to E25 keep their IDs, names, roles and reporting
lines, because employee_interface/users.csv logs people in by ID and
idea_store.employee_name() resolves the author from employees.csv. New hires
hang off the existing leads, so no committed row changes.

Deterministic: fixed seed, same output on every run.
"""

import csv
import random
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PEOPLE = ROOT / "knowledge-base" / "people"
EMPLOYEES_CSV = PEOPLE / "employees.csv"
CAPACITY_CSV = PEOPLE / "capacity.csv"

SEED = 20261126
LAST_UPDATED = "2026-11-26"

DEPARTMENT_TITLES = {
    "management": "Management",
    "engineering": "Product & Engineering",
    "data-it": "Data & IT",
    "sales": "Sales",
    "marketing": "Marketing",
    "support": "Customer Success & Support",
    "operations": "Operations",
    "quality-compliance": "Quality & Regulatory",
    "finance-people": "Finance, People & Administration",
}

# Order here is the order IDs are handed out, and the order the directory reads.
DEPARTMENT_ORDER = list(DEPARTMENT_TITLES)

SITES = ["Aachen", "Eindhoven", "Vienna"]

FIRST_NAMES = [
    "Annika", "Bastian", "Carla", "Daniel", "Elif", "Florian", "Greta", "Henrik",
    "Iris", "Jakob", "Kerstin", "Lennart", "Marta", "Niklas", "Oskar", "Pia",
    "Quirin", "Rebecca", "Simon", "Theresa", "Ulrich", "Valentina", "Wiebke",
    "Yannick", "Zofia", "Ahmet", "Bianca", "Cedric", "Dorothea", "Emre",
    "Fiona", "Gustav", "Helena", "Ivo", "Johanna", "Kasper", "Linnea",
    "Matthias", "Noor", "Olga", "Piotr", "Rahel", "Sanne", "Tobias", "Ursula",
    "Vincent", "Wanda", "Xenia", "Yusuf", "Zara", "Arjun", "Beatrix", "Casper",
    "Dilara", "Eduard", "Femke", "Gregor", "Hannes", "Ingeborg", "Joost",
    "Katrin", "Lars", "Mira", "Nikolas", "Ottilie", "Petra", "Rafael", "Sibel",
    "Tomas", "Ulrike", "Veronika", "Willem", "Amara", "Bruno", "Chiara",
    "Dmitri", "Esra", "Fabian", "Gloria", "Hugo", "Ilse", "Janek", "Konrad",
    "Leonie", "Mehmet", "Nadia", "Orhan", "Paulina", "Reinhard", "Svenja",
    "Teresa", "Uwe", "Viktor", "Wilhelmina", "Yara", "Zeynep", "Adrian",
    "Birgit", "Corneliu", "Dagmar", "Erkan", "Franka", "Gideon", "Hedwig",
    "Ismail", "Jolanda", "Kilian", "Lucia", "Magnus", "Nora", "Oliver",
    "Philippa", "Roman", "Stefanie", "Timo", "Ute", "Vera", "Wolfram",
]

LAST_NAMES = [
    "Baumann", "Cremers", "Dietrich", "Engel", "Fuchs", "Gerber", "Hoffmann",
    "Jansen", "Keller", "Lindner", "Maier", "Neumann", "Oosterhuis", "Pfeiffer",
    "Richter", "Schmitt", "Thiele", "Ueberall", "Vermeulen", "Wagner",
    "Zimmermann", "Arslan", "Bakker", "Conrad", "Dubois", "Eriksen", "Falk",
    "Grabowski", "Hartwig", "Ipek", "Jurgens", "Kowalczyk", "Lorenz", "Mertens",
    "Novak", "Osei", "Petrov", "Quast", "Reinhardt", "Stadler", "Tillmann",
    "Urban", "Visser", "Weiss", "Zielinski", "Abate", "Brands", "Czerny",
    "Dahl", "Ebner", "Fontaine", "Gruber", "Haas", "Iversen", "Jakobsen",
    "Kuipers", "Lammers", "Moser", "Nowicki", "Ortmann", "Pollmann", "Rosenberg",
    "Sauer", "Tanner", "Unger", "Voigt", "Wiemer", "Zeller", "Adeyemi",
    "Bruggeman", "Chernov", "Dekker", "Esposito", "Frey", "Geiger", "Huber",
    "Ilhan", "Janssens", "Kappler", "Leclerc", "Mohr", "Niemeyer", "Oppenheim",
    "Pernkopf", "Riedel", "Steinbach", "Toth", "Ullmann", "Vogt", "Wendler",
    "Zajac", "Albrecht", "Bergmann", "Clement", "Donnersmarck", "Eichhorn",
    "Feldmann", "Grimm", "Hennig", "Isler", "Jost", "Kraus", "Linden",
]

# (role, manager_id, department, seniority, skills, responsibilities, work_mode)
# manager_id "" means it is filled in later from the lead created in the same block.
NEW_ROLES: list[tuple] = [
    # --- Management: staff roles under the CEO. No existing line is re-pointed.
    ("Head of Strategy & AI Portfolio", "E01", "management", "lead",
     "Portfolio management; business cases; AI governance",
     "Internal AI portfolio, investment cases, AI Act readiness", "hybrid"),
    ("Chief of Staff", "E01", "management", "lead",
     "Programme management; reporting; board preparation",
     "Company goals, leadership reporting, cross-team programmes", "hybrid"),
    ("Executive Assistant", "E01", "management", "mid",
     "Scheduling; travel; board logistics",
     "Executive calendars, travel, board meeting logistics", "office"),

    # --- Product & Engineering
    ("Engineering Manager, Software", "E02", "engineering", "lead",
     "People management; delivery planning; Python",
     "Canopy software delivery, software hiring", "hybrid"),
    ("Senior Backend Developer", "@EM_SW", "engineering", "senior",
     "Python; PostgreSQL; event streaming", "Canopy ingestion pipeline", "remote"),
    ("Backend Developer", "@EM_SW", "engineering", "mid",
     "Python; FastAPI; AWS", "Canopy API endpoints", "hybrid"),
    ("Backend Developer", "@EM_SW", "engineering", "mid",
     "Python; PostgreSQL; testing", "Alerting and notifications service", "remote"),
    ("Senior Backend Developer", "@EM_SW", "engineering", "senior",
     "Go; Kubernetes; API design", "Public API v2, rate limiting", "remote"),
    ("Backend Developer", "@EM_SW", "engineering", "mid",
     "Python; integrations", "Third-party integrations", "hybrid"),
    ("Senior Frontend Developer", "@EM_SW", "engineering", "senior",
     "TypeScript; React; design systems", "Canopy dashboard architecture", "remote"),
    ("Frontend Developer", "@EM_SW", "engineering", "mid",
     "TypeScript; React; accessibility", "Dashboard components, WCAG compliance", "remote"),
    ("Frontend Developer", "@EM_SW", "engineering", "mid",
     "TypeScript; React; charting", "Measurement charts and reports view", "hybrid"),
    ("QA Engineer", "@EM_SW", "engineering", "mid",
     "Test automation; Playwright", "Automated regression suite", "hybrid"),
    ("Product Manager, Canopy", "E02", "engineering", "senior",
     "Roadmapping; analytics; interviews", "Canopy roadmap and release scope", "hybrid"),
    ("Product Designer", "E02", "engineering", "senior",
     "Interaction design; prototyping; research", "Canopy UX, design system", "remote"),
    ("Technical Writer", "E02", "engineering", "mid",
     "Documentation; API reference", "Product documentation and API reference", "remote"),
    ("Hardware Engineer", "E04", "engineering", "senior",
     "PCB design; RF; EMC", "Sprig Pro 2 mainboard", "office"),
    ("Hardware Engineer", "E04", "engineering", "mid",
     "Schematic capture; bring-up", "Sensor carrier boards", "office"),
    ("Hardware Engineer", "E04", "engineering", "mid",
     "Power electronics; battery systems", "Battery life and power budget", "office"),
    ("Mechanical Engineer", "E04", "engineering", "mid",
     "CAD; injection moulding; tolerance", "Enclosures and mounting hardware", "office"),
    ("Test Engineer", "E04", "engineering", "mid",
     "Test rigs; measurement automation", "End-of-line and calibration rigs", "office"),
    ("Firmware Engineer", "E06", "engineering", "senior",
     "C; RTOS; LoRaWAN", "Gateway firmware, radio stack", "hybrid"),
    ("Firmware Engineer", "E06", "engineering", "mid",
     "C; embedded Linux; OTA", "Over-the-air update pipeline", "hybrid"),
    ("Firmware Engineer", "E06", "engineering", "mid",
     "C; sensor drivers", "Sensor drivers and self-calibration", "office"),
    ("Site Reliability Engineer", "E09", "engineering", "senior",
     "AWS; Terraform; observability", "Production reliability, on-call", "hybrid"),
    ("Site Reliability Engineer", "E09", "engineering", "mid",
     "Kubernetes; monitoring; incident response", "Monitoring and alerting, runbooks", "remote"),

    # --- Data & IT
    ("Head of Data & IT", "E02", "data-it", "lead",
     "Data platform; IT operations; governance",
     "Data warehouse, BI, internal IT, system integrations", "hybrid"),
    ("Data Engineer", "@HEAD_DATA", "data-it", "senior",
     "dbt; Python; data modelling", "Data warehouse models and pipelines", "hybrid"),
    ("Data Analyst", "@HEAD_DATA", "data-it", "mid",
     "SQL; dashboards; statistics", "Company KPI dashboards", "remote"),
    ("Data Analyst", "@HEAD_DATA", "data-it", "mid",
     "SQL; product analytics", "Product usage and churn analysis", "hybrid"),
    ("BI Developer", "@HEAD_DATA", "data-it", "mid",
     "BI tooling; data visualisation", "Self-service reporting", "remote"),
    ("IT Support Specialist", "@HEAD_DATA", "data-it", "mid",
     "Device management; identity; helpdesk", "Laptops, accounts, internal helpdesk", "office"),
    ("IT Support Specialist", "@HEAD_DATA", "data-it", "junior",
     "Helpdesk; onboarding setup", "Account setup, first-line internal IT", "office"),

    # --- Sales
    ("Sales Manager, DACH", "E10", "sales", "lead",
     "Team leadership; public tenders; forecasting",
     "Germany, Austria and Switzerland revenue", "hybrid"),
    ("Account Executive, Education", "@SM_DACH", "sales", "senior",
     "Schools and municipalities; tenders", "Education accounts, DACH", "remote"),
    ("Account Executive, Education", "@SM_DACH", "sales", "mid",
     "Public sector; framework agreements", "Municipal accounts, DACH", "remote"),
    ("Account Executive, Offices & Industry", "@SM_DACH", "sales", "senior",
     "Facility management; industrial accounts", "Commercial accounts, DACH", "hybrid"),
    ("Account Executive, Offices & Industry", "@SM_DACH", "sales", "mid",
     "Office portfolios; resellers", "Reseller channel, DACH", "hybrid"),
    ("Sales Development Representative", "@SM_DACH", "sales", "junior",
     "Outreach; qualification", "Inbound and outbound qualification", "office"),
    ("Sales Manager, Benelux", "E10", "sales", "lead",
     "Team leadership; channel sales", "Netherlands and Belgium revenue", "hybrid"),
    ("Account Executive, Education", "@SM_BNL", "sales", "senior",
     "Dutch education sector; tenders", "Education accounts, Benelux", "hybrid"),
    ("Account Executive, Offices & Industry", "@SM_BNL", "sales", "mid",
     "Facility managers; resellers", "Commercial accounts, Benelux", "hybrid"),
    ("Partner Manager", "@SM_BNL", "sales", "senior",
     "Channel partners; enablement", "Reseller programme, Benelux", "remote"),
    ("Sales Development Representative", "@SM_BNL", "sales", "junior",
     "Outreach; qualification", "Lead qualification, Benelux", "office"),
    ("Sales Operations Analyst", "E10", "sales", "mid",
     "CRM administration; forecasting; reporting",
     "HubSpot data quality, pipeline reporting", "hybrid"),

    # --- Marketing
    ("Demand Generation Manager", "E14", "marketing", "senior",
     "Paid campaigns; marketing automation", "Campaigns and lead generation", "hybrid"),
    ("Product Marketing Manager", "E14", "marketing", "senior",
     "Positioning; competitive analysis", "Messaging, launch material", "remote"),
    ("Graphic Designer", "E14", "marketing", "mid",
     "Brand design; print; motion", "Brand assets, data sheets", "remote"),
    ("Events Manager", "E14", "marketing", "mid",
     "Trade fairs; webinars; logistics", "Trade fairs and webinar programme", "office"),
    ("Content Specialist", "E14", "marketing", "mid",
     "Copywriting; case studies; German and English",
     "Case studies, newsletter, translations", "remote"),
    ("Marketing Operations Specialist", "E14", "marketing", "mid",
     "Marketing automation; analytics", "Campaign tracking and attribution", "hybrid"),

    # --- Customer Success & Support
    ("Support Team Lead", "E16", "support", "lead",
     "Queue management; escalations; coaching",
     "Ticket queue, SLA performance, shift planning", "hybrid"),
    ("Support Specialist", "@SUP_LEAD", "support", "senior",
     "Troubleshooting; LoRaWAN; escalations", "Second-line tickets", "hybrid"),
    ("Support Specialist", "@SUP_LEAD", "support", "mid",
     "Troubleshooting; knowledge articles", "Ticket queue, help centre", "office"),
    ("Support Specialist", "@SUP_LEAD", "support", "mid",
     "Troubleshooting; Dutch and English", "Benelux ticket queue", "remote"),
    ("Support Specialist", "@SUP_LEAD", "support", "mid",
     "Troubleshooting; German and English", "DACH ticket queue", "hybrid"),
    ("Support Specialist", "@SUP_LEAD", "support", "junior",
     "First-line triage", "Ticket triage and categorisation", "office"),
    ("Support Specialist", "@SUP_LEAD", "support", "junior",
     "First-line triage; logins", "Account and login questions", "office"),
    ("Support Specialist", "@SUP_LEAD", "support", "mid",
     "Troubleshooting; returns intake", "Returns intake, RMA numbers", "office"),
    ("Support Specialist", "@SUP_LEAD", "support", "junior",
     "First-line triage; training", "Ticket queue, customer webinars", "hybrid"),
    ("Knowledge Manager", "E16", "support", "mid",
     "Technical writing; taxonomy", "Help centre content and structure", "remote"),
    ("Customer Success Manager", "E16", "support", "senior",
     "Onboarding; renewals; QBRs", "Key accounts, DACH", "hybrid"),
    ("Customer Success Manager", "E16", "support", "mid",
     "Onboarding; adoption", "Mid-market accounts, DACH", "hybrid"),
    ("Customer Success Manager", "E16", "support", "mid",
     "Onboarding; adoption; Dutch", "Accounts, Benelux", "remote"),
    ("Customer Success Manager", "E16", "support", "mid",
     "Renewals; churn prevention", "Renewals and at-risk accounts", "hybrid"),
    ("Field Installation Technician", "E19", "support", "mid",
     "Site surveys; installation; LoRaWAN", "Installations, DACH south", "field"),
    ("Field Installation Technician", "E19", "support", "mid",
     "Site surveys; installation", "Installations, DACH north", "field"),
    ("Field Installation Technician", "E19", "support", "mid",
     "Site surveys; installation", "Installations, Benelux", "field"),
    ("Field Installation Technician", "E19", "support", "junior",
     "Installation; commissioning", "Installations, Austria", "field"),

    # --- Operations
    ("Production Lead", "E20", "operations", "lead",
     "Production planning; lean; quality",
     "Assembly line, output and yield", "office"),
    ("Assembly Technician", "@PROD_LEAD", "operations", "technician",
     "Assembly; soldering", "Sensor assembly", "office"),
    ("Assembly Technician", "@PROD_LEAD", "operations", "technician",
     "Assembly; end-of-line test", "Sensor assembly and test", "office"),
    ("Assembly Technician", "@PROD_LEAD", "operations", "technician",
     "Assembly; gateway build", "Gateway assembly", "office"),
    ("Assembly Technician", "@PROD_LEAD", "operations", "technician",
     "Assembly; rework", "Assembly and rework", "office"),
    ("Assembly Technician", "@PROD_LEAD", "operations", "technician",
     "Assembly; packaging", "Assembly and packing", "office"),
    ("Quality Technician", "@PROD_LEAD", "operations", "technician",
     "End-of-line test; calibration", "Final test and calibration", "office"),
    ("Quality Technician", "@PROD_LEAD", "operations", "technician",
     "Repair; fault analysis", "Repairs and fault codes", "office"),
    ("Production Planner", "E20", "operations", "mid",
     "Demand planning; scheduling", "Production schedule, material planning", "office"),
    ("Procurement Specialist", "E21", "operations", "mid",
     "Purchasing; supplier negotiation", "Component purchasing", "office"),
    ("Supplier Quality Manager", "E20", "operations", "senior",
     "Supplier audits; incoming inspection", "Supplier quality and audits", "hybrid"),
    ("Logistics Coordinator", "E21", "operations", "mid",
     "Shipping; customs; carriers", "Outbound shipping, DACH", "office"),
    ("Logistics Coordinator", "E21", "operations", "mid",
     "Shipping; returns logistics", "Outbound shipping, Benelux and returns", "office"),
    ("Warehouse Lead", "E21", "operations", "technician",
     "Stock control; goods receipt", "Warehouse, stock counts", "office"),
    ("Inventory Controller", "E21", "operations", "mid",
     "Stock accuracy; cycle counting", "Stock records and reconciliation", "office"),

    # --- Quality & Regulatory
    ("Head of Quality & Regulatory", "E01", "quality-compliance", "lead",
     "Quality management; CE marking; audits",
     "Quality system, product compliance, certification", "hybrid"),
    ("Quality Management Systems Manager", "@HEAD_QA", "quality-compliance", "senior",
     "ISO 9001; ISO 27001; process audits", "Quality system, ISO 27001 readiness", "hybrid"),
    ("Regulatory Affairs Specialist", "@HEAD_QA", "quality-compliance", "senior",
     "CE marking; radio regulation; product standards",
     "Product certification and declarations", "hybrid"),
    ("Data Protection Officer", "@HEAD_QA", "quality-compliance", "senior",
     "GDPR; data processing agreements; DPIA",
     "Data protection, subject requests, DPIAs", "hybrid"),
    ("Information Security Officer", "@HEAD_QA", "quality-compliance", "senior",
     "Information security; risk assessment; ISO 27001",
     "Security policy, risk register, access reviews", "hybrid"),
    ("Compliance Analyst", "@HEAD_QA", "quality-compliance", "mid",
     "Policy documentation; evidence collection",
     "Audit evidence, policy upkeep, AI Act register", "remote"),

    # --- Finance, People & Administration
    ("Controller", "E23", "finance-people", "senior",
     "Controlling; budgeting; reporting", "Budgets, forecasts, management reporting", "hybrid"),
    ("Accounts Payable Clerk", "E24", "finance-people", "junior",
     "Invoice processing; reconciliation", "Supplier invoices and payment runs", "office"),
    ("Recruiter", "E25", "finance-people", "mid",
     "Technical recruiting; employer branding", "Hiring pipeline, interviews", "remote"),
    ("People Operations Specialist", "E25", "finance-people", "mid",
     "HR administration; payroll preparation; Personio",
     "Contracts, leave, payroll input", "hybrid"),
    ("Office Manager", "E25", "finance-people", "mid",
     "Facilities; suppliers; events", "Office, facilities, supplies", "office"),
]

# Where a role's manager is a lead created in this same list, the placeholder is
# resolved once that lead has an ID.
LEAD_PLACEHOLDERS = {
    "@EM_SW": "Engineering Manager, Software",
    "@HEAD_DATA": "Head of Data & IT",
    "@SM_DACH": "Sales Manager, DACH",
    "@SM_BNL": "Sales Manager, Benelux",
    "@SUP_LEAD": "Support Team Lead",
    "@PROD_LEAD": "Production Lead",
    "@HEAD_QA": "Head of Quality & Regulatory",
}

COST_PER_DAY = {
    "exec": (820, 980),
    "lead": (620, 780),
    "senior": (520, 620),
    "mid": (420, 520),
    "junior": (320, 410),
    "technician": (280, 370),
}

# Leads keep less free time than individual contributors.
CAPACITY_RANGE = {
    "exec": (5, 15),
    "lead": (10, 25),
    "senior": (15, 35),
    "mid": (20, 45),
    "junior": (25, 50),
    "technician": (10, 25),
}

# Decision board: these people see the AI evaluation results.
ADMIN_IDS = {"E01", "E02", "E23"}
# Matched on the role title, so the board survives a change in ID order.
ADMIN_ROLE_HINTS = ("Head of Strategy & AI Portfolio",)
# Department heads and compliance roles: review queue plus their own department.
REVIEWER_ROLE_HINTS = (
    "Head of", "Lead", "Manager, DACH", "Manager, Benelux", "Chief of Staff",
    "Product Manager", "Data Protection Officer", "Information Security Officer",
)

EXISTING_SENIORITY = {
    "E01": "exec", "E02": "exec", "E03": "senior", "E04": "lead", "E05": "mid",
    "E06": "senior", "E07": "senior", "E08": "mid", "E09": "senior",
    "E10": "lead", "E11": "senior", "E12": "mid", "E13": "junior",
    "E14": "lead", "E15": "mid", "E16": "lead", "E17": "mid", "E18": "mid",
    "E19": "mid", "E20": "lead", "E21": "mid", "E22": "technician",
    "E23": "lead", "E24": "mid", "E25": "mid",
}

# Aachen is the plant and HQ, so assembly and lab roles stay there.
AACHEN_ONLY = ("Assembly", "Quality Technician", "Warehouse", "Hardware",
               "Mechanical", "Test Engineer", "Production", "Executive Assistant")


def slugify(text: str) -> str:
    """Email-safe form of a name: Krüger -> krueger, El-Amrani -> el-amrani."""
    replacements = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                    "é": "e", "è": "e", "ç": "c", "ø": "oe", "å": "aa"}
    lowered = text.lower()
    for source, target in replacements.items():
        lowered = lowered.replace(source, target)
    stripped = unicodedata.normalize("NFKD", lowered)
    stripped = "".join(c for c in stripped if not unicodedata.combining(c))
    return "".join(c for c in stripped if c.isalnum() or c in "-'").replace("'", "")


def read_existing() -> tuple[list[dict], list[str]]:
    """The original 25 employees, whatever the file currently holds.

    Keeps the generator idempotent: run it twice and you get the same 120
    people, not 215. Only E01 to E25 are preserved; everyone above that is
    regenerated from NEW_ROLES on every run.
    """
    with EMPLOYEES_CSV.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = list(reader.fieldnames)
    return [r for r in rows if r["id"] in EXISTING_SENIORITY], fieldnames


def pick_site(rng: random.Random, employee_id: str, role: str, department: str) -> str:
    # The first 25 predate Eindhoven and Vienna, so they sit at the Aachen HQ.
    if employee_id in EXISTING_SENIORITY:
        return "Aachen"
    if any(hint in role for hint in AACHEN_ONLY) or department == "management":
        return "Aachen"
    if "Benelux" in role or "Dutch" in role:
        return "Eindhoven"
    if "Austria" in role:
        return "Vienna"
    return rng.choices(SITES, weights=[58, 24, 18])[0]


def access_role(employee_id: str, role: str) -> str:
    if employee_id in ADMIN_IDS or any(h in role for h in ADMIN_ROLE_HINTS):
        return "admin"
    if any(hint in role for hint in REVIEWER_ROLE_HINTS):
        return "reviewer"
    return "employee"


def generate() -> None:
    rng = random.Random(SEED)
    existing, fieldnames = read_existing()
    taken_names = {row["name"] for row in existing}

    # Unique name pool, shuffled once so output is stable.
    combinations = [(first, last) for first in FIRST_NAMES for last in LAST_NAMES]
    rng.shuffle(combinations)
    name_pool = iter(combinations)

    rows: list[dict] = []
    lead_ids: dict[str, str] = {}
    next_number = max(int(row["id"][1:]) for row in existing) + 1

    for role, manager, department, seniority, skills, duties, mode in NEW_ROLES:
        while True:
            first, last = next(name_pool)
            name = f"{first} {last}"
            if name not in taken_names:
                taken_names.add(name)
                break

        employee_id = f"E{next_number:02d}"
        next_number += 1

        email = f"{slugify(first)}.{slugify(last)}@brambleworks.example"
        # New hires joined after the role existed; spread across 2021-2026.
        year = rng.choice([2021, 2022, 2023, 2023, 2024, 2024, 2025, 2025, 2026])
        start = f"{year}-{rng.randint(1, 12):02d}-{rng.choice([1, 15]):02d}"

        rows.append({
            "id": employee_id, "name": name, "email": email, "role": role,
            "department": department, "manager_id": manager, "work_mode": mode,
            "start_date": start, "skills": skills, "responsibilities": duties,
            "deputy_id": "",
            # Not written to employees.csv; used for capacity.csv below.
            "_seniority": seniority,
        })

        if role in LEAD_PLACEHOLDERS.values():
            placeholder = next(k for k, v in LEAD_PLACEHOLDERS.items() if v == role)
            lead_ids.setdefault(placeholder, employee_id)

    # Resolve "@LEAD" managers now that every lead has an ID.
    for row in rows:
        if row["manager_id"].startswith("@"):
            row["manager_id"] = lead_ids[row["manager_id"]]

    # Deputy: a colleague in the same department with the same manager where
    # possible, otherwise the manager. Keeps the existing directory convention.
    by_manager: dict[str, list[dict]] = {}
    for row in rows:
        by_manager.setdefault(row["manager_id"], []).append(row)
    for row in rows:
        peers = [p for p in by_manager[row["manager_id"]] if p["id"] != row["id"]]
        row["deputy_id"] = peers[0]["id"] if peers else row["manager_id"]

    all_rows = existing + [{k: v for k, v in r.items() if not k.startswith("_")}
                           for r in rows]

    with EMPLOYEES_CSV.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    # capacity.csv carries what the feasibility agent needs and what the board
    # filters on: who is available, what a day of their time costs, who may see
    # the evaluation results.
    seniority_by_id = {r["id"]: r["_seniority"] for r in rows} | EXISTING_SENIORITY
    role_by_id = {r["id"]: r["role"] for r in all_rows}
    department_by_id = {r["id"]: r["department"] for r in all_rows}

    capacity_rows = []
    for employee_id in [r["id"] for r in all_rows]:
        seniority = seniority_by_id[employee_id]
        low, high = COST_PER_DAY[seniority]
        cap_low, cap_high = CAPACITY_RANGE[seniority]
        capacity_rows.append({
            "employee_id": employee_id,
            "department": department_by_id[employee_id],
            "site": pick_site(rng, employee_id, role_by_id[employee_id],
                              department_by_id[employee_id]),
            "seniority": seniority,
            "fte": "1.0" if rng.random() > 0.12 else "0.8",
            "capacity_pct_available": rng.randint(cap_low, cap_high),
            "cost_per_day_eur": rng.randrange(low, high, 10),
            "access_role": access_role(employee_id, role_by_id[employee_id]),
        })

    with CAPACITY_CSV.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(capacity_rows[0]))
        writer.writeheader()
        writer.writerows(capacity_rows)

    # Summary, so a mismatch against the knowledge base is obvious immediately.
    print(f"employees.csv: {len(all_rows)} rows "
          f"({len(existing)} preserved, {len(rows)} added)")
    counts: dict[str, int] = {}
    for row in all_rows:
        counts[row["department"]] = counts.get(row["department"], 0) + 1
    for department in DEPARTMENT_ORDER:
        print(f"  {DEPARTMENT_TITLES[department]:<34} {counts.get(department, 0):>3}")
    sites: dict[str, int] = {}
    roles: dict[str, int] = {}
    for row in capacity_rows:
        sites[row["site"]] = sites.get(row["site"], 0) + 1
        roles[row["access_role"]] = roles.get(row["access_role"], 0) + 1
    print(f"  sites: {sites}")
    print(f"  access roles: {roles}")


if __name__ == "__main__":
    generate()
