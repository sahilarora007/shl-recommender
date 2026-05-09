import json
import os
from typing import List, Dict

def load_catalog(filepath: str = "catalog.json") -> List[Dict]:
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def format_catalog_context(candidates: List[Dict]) -> str:
    lines = []
    for c in candidates:
        levels = ", ".join(c.get("job_levels", []))
        duration = c.get("duration_minutes", "?")
        desc = c.get("description", "")
        # Truncate description slightly for prompt space
        if len(desc) > 120:
            desc = desc[:117] + "..."
        lines.append(
            f'- {c["name"]} | Type: {c.get("test_type_label", "")} ({c.get("test_type", "")}) '
            f'| URL: {c["url"]} | Levels: {levels} '
            f'| Duration: {duration}min '
            f'| {desc}'
        )
    return "\n".join(lines)
