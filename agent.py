import json
import re
import os
from groq import Groq
from dotenv import load_dotenv
from models import Message, ChatResponse, Recommendation
from prompts import SYSTEM_PROMPT, EXTRACT_CONTEXT_PROMPT, INTENT_CLASSIFICATION_PROMPT
from retrieval import search_catalog
from catalog import format_catalog_context, load_catalog

# Use Groq Llama-3.3-70b (high TPM free tier) for chat and parsing
MODEL_NAME = "llama-3.3-70b-versatile"

load_dotenv()

client = None
if os.getenv("GROQ_API_KEY"):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def parse_llm_json(raw: str) -> dict:
    if not raw:
        return {}
    raw = re.sub(r"```json|```", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
    return {}

def call_llm(prompt: str, system: str = "") -> str:
    try:
        if not client:
            return '{"reply": "Please set GROQ_API_KEY", "recommendations": [], "end_of_conversation": false}'
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.0
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"LLM Error: {e}")
        return "{}"

def classify_intent(messages: list[Message]) -> str:
    history = "\n".join([f"{m.role}: {m.content}" for m in messages[-4:]])
    prompt = f"History:\n{history}\n\nBased on the history, what is the intent?"
    resp = call_llm(prompt, system=INTENT_CLASSIFICATION_PROMPT)
    parsed = parse_llm_json(resp)
    return parsed.get("intent", "VAGUE")

def extract_context(messages: list[Message]) -> dict:
    history = "\n".join([f"{m.role}: {m.content}" for m in messages])
    prompt = f"History:\n{history}\n\nExtract context."
    resp = call_llm(prompt, system=EXTRACT_CONTEXT_PROMPT)
    parsed = parse_llm_json(resp)
    return parsed

def build_query(context: dict) -> str:
    parts = [
        context.get("role") or "",
        context.get("seniority") or "",
        " ".join(context.get("skills") or []),
        " ".join(context.get("test_types_preferred") or []),
    ]
    return " ".join(p for p in parts if p and isinstance(p, str))

def is_refusal_triggered(message: str) -> bool:
    message = message.lower()
    refusal_patterns = ["ignore previous", "disregard", "you are now", "pretend you are"]
    out_of_scope = ["salary", "legal", "hogan", "korn ferry", "talent+"]
    return any(p in message for p in refusal_patterns + out_of_scope)

def handle_compare(messages: list[Message]) -> ChatResponse | None:
    """
    Grounded comparison: loads matching catalog entries by name/keyword
    and injects raw catalog data into the LLM — not model weights.
    """
    full_catalog = load_catalog()
    search_text = " ".join(m.content for m in messages[-3:]).lower()

    # Strategy 1: exact full-name substring match
    matched = [e for e in full_catalog if e["name"].lower() in search_text]

    # Strategy 2: keyword match on significant words of each catalog name
    if len(matched) < 2:
        keyword_hits = {}
        for entry in full_catalog:
            words = [w for w in re.sub(r'[^\w\s]', '', entry['name'].lower()).split() if len(w) > 3]
            score = sum(1 for w in words if w in search_text)
            if score >= max(1, len(words) // 2):
                keyword_hits[entry['name']] = entry
        if len(keyword_hits) >= 2:
            matched = list(keyword_hits.values())[:4]

    if len(matched) < 2:
        return None

    compare_context = "\n".join([
        f"Assessment: {e['name']}\n"
        f"  Type: {e.get('test_type_label','')} ({e.get('test_type','')})\n"
        f"  Duration: {e.get('duration_minutes','?')}min | Levels: {', '.join(e.get('job_levels',[]))}\n"
        f"  Description: {e.get('description','')}\n"
        f"  URL: {e['url']}"
        for e in matched
    ])
    system = (
        "You are an SHL assessment advisor. Compare the following assessments "
        "using ONLY the data provided. Do not invent attributes. "
        "Respond ONLY in valid JSON: "
        '{"reply": "<comparison text>", "recommendations": [], "end_of_conversation": false}\n\n'
        f"CATALOG DATA:\n{compare_context}"
    )
    history_str = "\n".join([f"{m.role}: {m.content}" for m in messages])
    raw = call_llm(f"CONVERSATION:\n{history_str}\n\nCompare these assessments.", system=system)
    parsed = parse_llm_json(raw)
    reply = parsed.get("reply", "Here is a comparison based on catalog data.")
    return ChatResponse(reply=reply, recommendations=[], end_of_conversation=False)

async def run_agent(messages: list[Message]) -> ChatResponse:
    if len(messages) == 0:
        return ChatResponse(reply="How can I help you?", recommendations=[], end_of_conversation=False)

    last_msg = messages[-1].content.lower()

    if is_refusal_triggered(last_msg):
        return ChatResponse(
            reply="I'm designed to help with SHL assessment selection only. I can't help with that, but I'd be happy to help you find the right SHL assessment for your role.",
            recommendations=[],
            end_of_conversation=False
        )

    intent = classify_intent(messages)
    should_force_recommend = len(messages) >= 6

    if intent == "OFF_TOPIC":
        return ChatResponse(
            reply="I'm designed to help with SHL assessment selection only. I can't help with that.",
            recommendations=[],
            end_of_conversation=False
        )

    # ── COMPARE: grounded catalog comparison ─────────────────────────────────
    if intent == "COMPARE":
        result = handle_compare(messages)
        if result:
            return result
        # fallthrough if names couldn't be matched

    # ── Context extraction (used by both SPECIFIC and REFINE) ─────────────────
    context = extract_context(messages)

    if intent == "VAGUE" and not should_force_recommend:
        catalog_context_str = "No catalog retrieved yet."
    else:
        query = build_query(context)
        # Blend last user message to catch keywords the extractor missed
        query = (query + " " + last_msg).strip()
        if len(query.strip()) < 3:
            query = last_msg
        candidates = search_catalog(query, k=15)
        catalog_context_str = format_catalog_context(candidates)

    system_prompt = SYSTEM_PROMPT.format(catalog_context=catalog_context_str)
    history_str = "\n".join([f"{m.role}: {m.content}" for m in messages])

    # ── REFINE: explicitly acknowledge the updated constraint ─────────────────
    if intent == "REFINE":
        extra_instruction = (
            "\nIMPORTANT: The user has updated a constraint. "
            "In your reply, explicitly acknowledge the change (e.g., 'Updated your shortlist to reflect…') "
            "and return a fresh set of recommendations based on the full accumulated context."
        )
        prompt = (
            f"CONVERSATION HISTORY:\n{history_str}\n"
            f"{extra_instruction}\n\nPlease generate your JSON response."
        )
    else:
        prompt = f"CONVERSATION HISTORY:\n{history_str}\n\nPlease generate your JSON response."

    raw_response = call_llm(prompt, system=system_prompt)
    parsed = parse_llm_json(raw_response)

    reply = parsed.get("reply", "I can help you find assessments for this role.")
    recs_raw = parsed.get("recommendations", [])
    end_conv = parsed.get("end_of_conversation", False)

    # ── URL integrity: only allow URLs that exist in catalog ──────────────────
    valid_urls = {e["url"] for e in load_catalog()}
    valid_recs = []
    if isinstance(recs_raw, list):
        for r in recs_raw:
            if isinstance(r, dict) and "name" in r and "url" in r and "test_type" in r:
                if r["url"] not in valid_urls:
                    continue  # drop hallucinated URLs silently
                t = r["test_type"]
                if t not in ["A", "B", "C", "D", "E", "K", "O", "P", "S"]:
                    t = "K"
                valid_recs.append(Recommendation(name=r["name"], url=r["url"], test_type=t))

    if should_force_recommend and len(messages) >= 8:
        end_conv = True

    return ChatResponse(
        reply=reply,
        recommendations=valid_recs,
        end_of_conversation=end_conv
    )
