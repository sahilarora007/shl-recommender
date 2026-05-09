"""
SHL Product Catalog Scraper
Scrapes Individual Test Solutions from https://www.shl.com/solutions/products/product-catalog/
Uses plain requests + BeautifulSoup (no headless browser needed — data is in the HTML).

Pagination: ?start=0&type=1  (type=1 = Individual Tests, 12 per page)
Detail page: /products/product-catalog/view/<slug>/
"""

import json
import os
import time
import re
import requests
from bs4 import BeautifulSoup

BASE = "https://www.shl.com"
LIST_URL = BASE + "/solutions/products/product-catalog/?start={start}&type=1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

TEST_TYPE_LABELS = {
    "A": "Ability & Aptitude",
    "B": "Biodata & Situational Judgement",
    "C": "Competencies",
    "D": "Development & 360",
    "E": "Assessment Exercises",
    "K": "Knowledge & Skills",
    "O": "Occupational Personality",
    "P": "Personality & Behavior",
    "S": "Simulations",
}

ROLE_TAGS = {
    "java": ["java", "programming", "backend", "software engineer", "developer"],
    "python": ["python", "programming", "backend", "software engineer", "developer"],
    ".net": ["dotnet", "programming", "backend", "software engineer", "developer"],
    "c++": ["cpp", "programming", "software engineer", "developer"],
    "sql": ["sql", "database", "data", "developer"],
    "numerical": ["numerical", "math", "data analysis", "finance", "analyst"],
    "verbal": ["verbal", "comprehension", "communication", "reading"],
    "personality": ["personality", "behavior", "culture fit", "leadership"],
    "situational": ["situational judgement", "judgment", "scenario"],
    "sales": ["sales", "customer", "negotiation", "business development"],
    "leadership": ["leadership", "management", "executive", "strategy"],
    "customer service": ["customer service", "support", "call center"],
    "simulation": ["simulation", "interactive", "scenario"],
    "cognitive": ["cognitive", "aptitude", "reasoning", "critical thinking"],
    "mechanical": ["mechanical", "engineering", "technical"],
    "administrative": ["administrative", "clerical", "office"],
    "graduate": ["graduate", "entry level", "early career"],
    "executive": ["executive", "senior", "director", "c-suite"],
}


def get_page(url: str, retries=3) -> BeautifulSoup | None:
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            print(f"  Retry {attempt+1}/{retries} for {url}: {e}")
            time.sleep(2)
    return None


def infer_tags(name: str, description: str) -> list[str]:
    """Infer semantic tags from name and description for better retrieval."""
    combined = (name + " " + description).lower()
    tags = []
    for keyword, tag_list in ROLE_TAGS.items():
        if keyword in combined:
            tags.extend(tag_list)
    # Add the name words themselves as tags
    tags.extend(re.sub(r"[^\w\s]", "", name.lower()).split())
    return list(dict.fromkeys(tags))  # deduplicate preserving order


def scrape_detail(slug_url: str) -> dict:
    """Scrape a single product detail page for description, duration, levels, etc."""
    full_url = BASE + slug_url
    soup = get_page(full_url)
    if not soup:
        return {}

    result = {}

    # Description — look for the first descriptive paragraph
    desc_el = soup.find("div", class_=re.compile(r"product|description|content|overview", re.I))
    if not desc_el:
        desc_el = soup.find("main")
    if desc_el:
        paras = desc_el.find_all("p")
        for p in paras:
            text = p.get_text(strip=True)
            if len(text) > 60:
                result["description"] = text[:400]
                break

    # Duration
    duration_match = re.search(r"(\d+)\s*(?:min|minute)", soup.get_text(), re.I)
    if duration_match:
        result["duration_minutes"] = int(duration_match.group(1))

    # Job levels
    text = soup.get_text(" ", strip=True).lower()
    levels = []
    if any(w in text for w in ["graduate", "entry", "early career"]):
        levels.append("Entry-Level")
    if any(w in text for w in ["mid", "professional", "experienced"]):
        levels.append("Mid-Professional")
    if any(w in text for w in ["senior", "manager", "director"]):
        levels.append("Senior")
    if any(w in text for w in ["executive", "c-suite", "vp ", "ceo", "cto"]):
        levels.append("Executive")
    result["job_levels"] = levels if levels else ["Mid-Professional"]

    # Remote testing
    result["remote_testing"] = "remote" in text or "online" in text

    # Adaptive
    result["adaptive"] = "adaptive" in text

    # Languages
    lang_match = re.findall(r"\b(English|Spanish|French|German|Dutch|Chinese|Arabic|Portuguese|Italian)\b", soup.get_text())
    result["languages"] = list(dict.fromkeys(lang_match)) if lang_match else ["English"]

    return result


def scrape_list_page(start: int) -> list[dict]:
    """Scrape one page of the catalog listing."""
    url = LIST_URL.format(start=start)
    soup = get_page(url)
    if not soup:
        return []

    items = []
    for row in soup.find_all("tr", attrs={"data-entity-id": True}):
        link_el = row.find("a", href=True)
        if not link_el:
            continue
        href = link_el["href"]

        name = link_el.get_text(strip=True)
        # Normalize URL path — SHL uses /products/... (without /solutions prefix)
        if href.startswith("/solutions"):
            url_path = href
        elif href.startswith("/products"):
            url_path = "/solutions" + href
        else:
            continue

        # Extract test type codes from the row
        type_spans = row.find_all("span", class_="product-catalogue__key")
        test_types = [s.get_text(strip=True) for s in type_spans if s.get_text(strip=True)]

        # Remote testing + adaptive indicators (first circle = remote, second = adaptive)
        circles = row.find_all("span", class_=re.compile(r"catalogue__circle"))
        remote = len(circles) >= 1 and "-yes" in circles[0].get("class", [])
        adaptive = len(circles) >= 2 and "-yes" in circles[1].get("class", [])

        items.append({
            "name": name,
            "url": BASE + url_path,
            "test_types": test_types,
            "remote_testing": remote,
            "adaptive": adaptive,
        })

    return items


def get_total_pages(soup: BeautifulSoup) -> int:
    """Find the last page number from pagination."""
    pagination = soup.find("ul", class_="pagination")
    if not pagination:
        return 1
    page_items = pagination.find_all("a", class_="pagination__link")
    max_start = 0
    for a in page_items:
        href = a.get("href", "")
        m = re.search(r"start=(\d+)", href)
        if m:
            max_start = max(max_start, int(m.group(1)))
    return max_start // 12 + 1 if max_start else 1


def main():
    print("Starting SHL catalog scrape...")
    print("Fetching first page to get total count...")

    first_soup = get_page(LIST_URL.format(start=0))
    if not first_soup:
        print("ERROR: Could not fetch catalog page.")
        return

    total_pages = get_total_pages(first_soup)
    print(f"Found {total_pages} pages ({total_pages * 12} estimated items)")

    # Collect all list entries
    all_entries_raw = []
    for page in range(total_pages):
        start = page * 12
        print(f"  Scraping list page {page+1}/{total_pages} (start={start})...")
        entries = scrape_list_page(start)
        all_entries_raw.extend(entries)
        time.sleep(0.5)  # polite delay

    print(f"Found {len(all_entries_raw)} entries in listing. Fetching detail pages...")

    # Build full catalog
    catalog = []
    for i, entry in enumerate(all_entries_raw):
        print(f"  [{i+1}/{len(all_entries_raw)}] {entry['name']}")
        detail = scrape_detail(entry["url"].replace(BASE, "").replace("/solutions", ""))
        
        # Determine primary test_type (first one listed)
        test_types = entry.get("test_types", ["K"])
        primary_type = test_types[0] if test_types else "K"

        desc = detail.get("description", f"SHL assessment: {entry['name']}")

        item = {
            "name": entry["name"],
            "url": entry["url"],
            "description": desc,
            "test_type": primary_type,
            "test_type_label": TEST_TYPE_LABELS.get(primary_type, "Knowledge & Skills"),
            "job_levels": detail.get("job_levels", ["Mid-Professional"]),
            "languages": detail.get("languages", ["English"]),
            "duration_minutes": detail.get("duration_minutes", 30),
            "remote_testing": entry.get("remote_testing", True),
            "adaptive": entry.get("adaptive", False),
            "tags": infer_tags(entry["name"], desc),
        }
        catalog.append(item)
        time.sleep(0.3)  # polite delay between detail pages

    # Write output
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(root_dir, "catalog.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Wrote {len(catalog)} items to {out_path}")


if __name__ == "__main__":
    main()
