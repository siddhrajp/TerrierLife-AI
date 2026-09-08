"""
Scrape BU public resource pages and save to data/bu_resources.json.
Run from the backend/ directory: python scripts/scrape_bu_resources.py
"""
import hashlib
import json
import os

import httpx
from bs4 import BeautifulSoup

BU_PAGES = [
    # Career
    {"url": "https://www.bu.edu/careers/", "category": "career", "title": "BU Career Development"},
    {"url": "https://www.bu.edu/careers/find-a-job/internships/", "category": "career", "title": "BU Internship Resources"},
    {"url": "https://www.bu.edu/careers/explore-careers/", "category": "career", "title": "BU Career Exploration"},
    {"url": "https://www.bu.edu/careers/find-a-job/", "category": "career", "title": "BU Job Search Resources"},
    {"url": "https://www.bu.edu/careers/build-skills/resume-cover-letter/", "category": "career", "title": "BU Resume & Cover Letter Help"},

    # International students
    {"url": "https://www.bu.edu/isso/", "category": "international", "title": "International Students & Scholars (ISSO)"},
    {"url": "https://www.bu.edu/isso/employment/opt/", "category": "international", "title": "OPT - Optional Practical Training"},
    {"url": "https://www.bu.edu/isso/international-students/off-campus-student-employment-training/curricular-practical-training-cpt/", "category": "international", "title": "CPT - Curricular Practical Training"},
    {"url": "https://www.bu.edu/isso/travel/", "category": "international", "title": "ISSO Travel & Visa Signatures"},
    {"url": "https://www.bu.edu/isso/international-students/", "category": "international", "title": "F-1 Student Status Basics"},
    {"url": "https://www.bu.edu/isso/international-students/off-campus-student-employment-training/", "category": "international", "title": "ISSO Off-Campus Employment & Training"},

    # Academic advising
    {"url": "https://www.bu.edu/cas/academics/advising/", "category": "advising", "title": "CAS Academic Advising"},
    {"url": "https://www.bu.edu/reg/", "category": "registrar", "title": "University Registrar"},
    {"url": "https://www.bu.edu/reg/registration/", "category": "registrar", "title": "BU Course Registration"},
    {"url": "https://www.bu.edu/reg/calendars/", "category": "registrar", "title": "BU Academic Calendar"},
    {"url": "https://www.bu.edu/reg/grades/", "category": "registrar", "title": "BU Grades & Transcripts"},
    {"url": "https://www.bu.edu/reg/graduation/", "category": "registrar", "title": "BU Graduation & Diplomas"},

    # Tutoring & academic support
    # The old /tutoring/* URLs all 404; ERC now lives under /advising/ and the
    # former sub-pages all redirect to this single page.
    {"url": "https://www.bu.edu/advising/educational-resource-center/", "category": "tutoring", "title": "Educational Resource Center (ERC)"},
    {"url": "https://www.bu.edu/advising/", "category": "advising", "title": "BU Undergraduate Advising"},

    # Health & wellness
    {"url": "https://www.bu.edu/shs/", "category": "health", "title": "Student Health Services"},
    {"url": "https://www.bu.edu/shs/medical/", "category": "health", "title": "BU Medical Services"},
    {"url": "https://www.bu.edu/shs/behavioral-medicine/", "category": "health", "title": "BU Behavioral Medicine & Counseling"},
    {"url": "https://www.bu.edu/wellness/", "category": "wellness", "title": "Student Wellness & Prevention Services"},
    {"url": "https://www.bu.edu/shs/immunizations/", "category": "health", "title": "BU Health Immunization Requirements"},

    # Library
    {"url": "https://www.bu.edu/library/", "category": "library", "title": "BU Libraries"},
    {"url": "https://www.bu.edu/library/mugar-memorial/", "category": "library", "title": "Mugar Memorial Library"},
    {"url": "https://www.bu.edu/library/research/", "category": "library", "title": "BU Library Research Help"},
    {"url": "https://www.bu.edu/library/services/", "category": "library", "title": "BU Library Services"},
    {"url": "https://www.bu.edu/library/about/hours/", "category": "library", "title": "BU Library Hours"},

    # Financial aid (the /financialaid/* paths 404; the live site is /finaid/)
    {"url": "https://www.bu.edu/finaid/", "category": "financial_aid", "title": "Financial Aid & Scholarships"},
    {"url": "https://www.bu.edu/finaid/undergraduate-students/", "category": "financial_aid", "title": "How to Apply for Financial Aid at BU"},
    {"url": "https://www.bu.edu/finaid/how-aid-works/types-of-aid/", "category": "financial_aid", "title": "Types of Financial Aid at BU"},
    {"url": "https://www.bu.edu/finaid/how-aid-works/", "category": "financial_aid", "title": "How Financial Aid Works at BU"},

    # Housing
    {"url": "https://www.bu.edu/housing/", "category": "housing", "title": "BU Housing"},
    {"url": "https://www.bu.edu/housing/undergrad/", "category": "housing", "title": "BU Undergraduate Housing"},
    {"url": "https://www.bu.edu/housing/dining/", "category": "housing", "title": "BU Housing & Dining Plans"},

    # Accessibility
    {"url": "https://www.bu.edu/disability/", "category": "accessibility", "title": "Disability & Access Services"},
    {"url": "https://www.bu.edu/disability/accommodations/", "category": "accessibility", "title": "BU Academic Accommodations"},

    # Dining
    {"url": "https://www.bu.edu/dining/", "category": "dining", "title": "BU Dining"},
    {"url": "https://www.bu.edu/dining/plans-points/", "category": "dining", "title": "BU Meal Plans"},

    # IT & tech support
    {"url": "https://www.bu.edu/tech/", "category": "it", "title": "BU Information Services & Technology"},
    {"url": "https://www.bu.edu/tech/support/", "category": "it", "title": "BU Tech Support & Help Desk"},

    # Study abroad & fellowships
    {"url": "https://www.bu.edu/abroad/", "category": "study_abroad", "title": "Study Abroad"},
    {"url": "https://www.bu.edu/bufellow/", "category": "fellowships", "title": "BU Office of Fellowships"},

    # Student life & activities
    {"url": "https://www.bu.edu/studentactivities/", "category": "student_life", "title": "BU Student Activities"},
    {"url": "https://www.bu.edu/safety/", "category": "safety", "title": "BU Campus Safety & Security"},
    {"url": "https://www.bu.edu/transportation/", "category": "transportation", "title": "BU Transportation & Parking"},
]


# A page that 404s still returns parseable HTML, so without these checks the
# error page itself gets indexed as a BU resource.
MIN_CONTENT_CHARS = 400
ERROR_MARKERS = ("page not found", "couldn't find that", "yikes")


def scrape_page(url: str) -> str:
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True)
    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return ""

    if r.status_code != 200:
        print(f"  Skipped (HTTP {r.status_code}): {url}")
        return ""

    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)[:8000]

    lowered = text.lower()
    if any(marker in lowered for marker in ERROR_MARKERS):
        print(f"  Skipped (soft 404): {url}")
        return ""

    if len(text) < MIN_CONTENT_CHARS:
        print(f"  Skipped (only {len(text)} chars, likely nav-only): {url}")
        return ""

    return text


results = []
# Several listed URLs redirect to a common landing page (all five /careers/*
# paths resolve to careers.bu.edu). Indexing each copy wastes retrieval slots:
# one query can fill k with duplicates of a single page and crowd out other
# sources. Deduplicate on content so only the first occurrence is kept.
seen_content: dict[str, str] = {}
for page in BU_PAGES:
    print(f"Scraping: {page['url']}")
    content = scrape_page(page["url"])
    if not content:
        continue

    fingerprint = hashlib.md5(content.encode()).hexdigest()
    if fingerprint in seen_content:
        print(f"  Skipped (duplicate of {seen_content[fingerprint]})")
        continue

    seen_content[fingerprint] = page["url"]
    results.append({**page, "content": content})
    print(f"  OK ({len(content)} chars)")

out_path = os.path.join(os.path.dirname(__file__), "../../data/bu_resources.json")
with open(out_path, "w") as f:
    json.dump(results, f, indent=2)

print(f"\nDone. Scraped {len(results)}/{len(BU_PAGES)} pages → data/bu_resources.json")
