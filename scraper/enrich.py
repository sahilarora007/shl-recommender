"""
Enrich catalog.json descriptions using Groq LLM.
Generates professional assessment descriptions based on name + test type + tags.
Run once: python -m scraper.enrich
"""
import json
import os
import time
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

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

BAD_DESC = "if you choose to continue with your current browser"

def generate_description(name: str, test_type: str, tags: list[str], job_levels: list[str]) -> str:
    type_label = TEST_TYPE_LABELS.get(test_type, "Assessment")
    tags_str = ", ".join(tags[:8])
    levels_str = ", ".join(job_levels)

    prompt = (
        f"Write a single concise professional description (1-2 sentences, max 180 characters) "
        f"for this SHL assessment:\n"
        f"Name: {name}\n"
        f"Type: {type_label}\n"
        f"Job Levels: {levels_str}\n"
        f"Tags: {tags_str}\n\n"
        f"Respond with ONLY the description text. No quotes, no extra text."
    )
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=100,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"  LLM error for {name}: {e}")
        time.sleep(5)
        return f"SHL {type_label} assessment evaluating {name} competencies."


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    catalog_path = os.path.join(root, "catalog.json")

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    needs_update = [i for i, e in enumerate(catalog)
                    if BAD_DESC in e.get("description", "").lower()]
    print(f"Found {len(needs_update)} entries needing description enrichment.")

    for count, idx in enumerate(needs_update, 1):
        entry = catalog[idx]
        print(f"  [{count}/{len(needs_update)}] {entry['name']}")
        desc = generate_description(
            entry["name"],
            entry.get("test_type", "K"),
            entry.get("tags", []),
            entry.get("job_levels", []),
        )
        catalog[idx]["description"] = desc
        time.sleep(0.15)  # stay under TPM limit

        # Save every 20 items so we don't lose progress
        if count % 20 == 0:
            with open(catalog_path, "w", encoding="utf-8") as f:
                json.dump(catalog, f, indent=2, ensure_ascii=False)
            print(f"  Saved checkpoint at {count} items.")

    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    print(f"\nDone. Enriched {len(needs_update)} descriptions in {catalog_path}")


if __name__ == "__main__":
    main()
