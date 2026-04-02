"""
Scrape BU public resource pages and save to data/bu_resources.json.
Run from the backend/ directory: python scripts/scrape_bu_resources.py
"""
import httpx
from bs4 import BeautifulSoup
import json
import os

BU_PAGES = [
    {"url": "https://www.bu.edu/careers/", "category": "career", "title": "BU Career Development"},
    {"url": "https://www.bu.edu/isso/", "category": "international", "title": "International Students & Scholars (ISSO)"},
    {"url": "https://www.bu.edu/cas/academics/advising/", "category": "advising", "title": "CAS Academic Advising"},
    {"url": "https://www.bu.edu/tutoring/", "category": "tutoring", "title": "Educational Resource Center (ERC)"},
    {"url": "https://www.bu.edu/shs/", "category": "health", "title": "Student Health Services"},
    {"url": "https://www.bu.edu/library/", "category": "library", "title": "BU Libraries"},
    {"url": "https://www.bu.edu/reg/", "category": "registrar", "title": "University Registrar"},
    {"url": "https://www.bu.edu/financialaid/", "category": "financial_aid", "title": "Financial Aid & Scholarships"},
    {"url": "https://www.bu.edu/housing/", "category": "housing", "title": "BU Housing"},
    {"url": "https://www.bu.edu/disability/", "category": "accessibility", "title": "Disability & Access Services"},
    {"url": "https://www.bu.edu/dining/", "category": "dining", "title": "BU Dining"},
    {"url": "https://www.bu.edu/wellness/", "category": "wellness", "title": "Student Wellness & Prevention Services"},
    {"url": "https://www.bu.edu/rit/", "category": "it", "title": "Research & IT Help"},
    {"url": "https://www.bu.edu/bufellow/", "category": "fellowships", "title": "BU Office of Fellowships"},
    {"url": "https://www.bu.edu/abroad/", "category": "study_abroad", "title": "Study Abroad"},
]


def scrape_page(url: str) -> str:
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:4000]
    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return ""


results = []
for page in BU_PAGES:
    print(f"Scraping: {page['url']}")
    content = scrape_page(page["url"])
    if content:
        results.append({**page, "content": content})
        print(f"  OK ({len(content)} chars)")

out_path = os.path.join(os.path.dirname(__file__), "../../data/bu_resources.json")
with open(out_path, "w") as f:
    json.dump(results, f, indent=2)

print(f"\nDone. Scraped {len(results)}/{len(BU_PAGES)} pages → data/bu_resources.json")
