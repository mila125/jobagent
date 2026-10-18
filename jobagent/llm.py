"""LLM calls through Claude Code in non-interactive mode (`claude -p`), so no API key is needed."""
import json
import os
import re
import shutil
import subprocess
import tempfile

import yaml
from google import genai
from google.genai import types

def ask_gemini_json(prompt, model=None):
    """Consulta Gemini y devuelve un diccionario JSON."""
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Falta GEMINI_API_KEY. Configúrala en CMD."
        )

    model = os.environ.get(
        "GEMINI_MODEL", "gemini-3.5-flash-lite"
    )

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )

    if not response.text:
        raise RuntimeError("Gemini no devolvió contenido.")

    data = json.loads(response.text)

    if not isinstance(data, dict):
        raise ValueError("Gemini no devolvió un objeto JSON.")

    return data

def _claude_exe():
    for name in ("claude.cmd", "claude.exe", "claude"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError('Claude Code ("claude" command) not found. Is it installed?')


def extract_json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def ask_json(prompt, model="sonnet", attempts=2):
    """Sends the prompt to Claude and returns the JSON in its answer, or None."""
    if os.environ.get("JOBAGENT_LLM") == "gemini":
        return ask_gemini_json(prompt, model)
    exe = _claude_exe()
    for _ in range(attempts):
        try:
            r = subprocess.run(
                [exe, "-p", "--model", model, "--tools", "", "--no-session-persistence",
                 "--output-format", "text"],
                input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=tempfile.gettempdir(), timeout=300,
            )
        except subprocess.TimeoutExpired:
            continue
        data = extract_json(r.stdout)
        if data is not None:
            return data
    return None


def score_offer(offer, profile_text, cvs, rules, model):
    """Returns {"fit", "cv", "company", "title", "reason"} or None."""
    if _fake():
        return _fake_score(offer, cvs)
    cv_list = "\n".join(f'- "{c["file"]}": {c["use_for"]}' for c in cvs)
    rule_list = "\n".join(f"- {r}" for r in rules)
    prompt = f"""Decide whether this job offer fits the candidate. Be strict and realistic.

CANDIDATE PROFILE (YAML):
{profile_text}

AVAILABLE CVS:
{cv_list}

OFFER (source: {offer.site}, link: {offer.url}):
Title: {offer.title}
Company: {offer.company}
Text:
{offer.text[:7000]}

Candidate-specific rules:
{rule_list}

General rules:
- Salary is NOT a reason to lower the fit (the candidate decides that).
- Judge like a recruiter: Prioritize junior, entry-level and recent graduate positions.
- Jobs requiring 0-1 years of experience are preferred.
- Jobs requiring 2-3 years may be considered if the main
  technical requirements match the candidate's skills.
- Jobs requiring 4+ years of professional experience
  should receive fit at most 3.
- Senior, lead, principal and architect positions
  should receive fit at most 2.
- Academic projects and internships demonstrate skills,
  but do not count as full-time professional employment.
-  Transferable skills may increase job compatibility,
  but never count as direct professional experience.
- Academic projects are not professional employment.
- Do not claim production experience without evidence. (n8n ≈ Zapier/Make/Workato; Salesforce ≈ other CRMs;
  Odoo ≈ other ERPs; PHP/Python/Java ≈ backend in general).
- Do not require ALL requirements: if the main ones are met and the offer is compatible, 5-7.
- Pick the most suitable CV; if the offer is written in Spanish, use the Spanish CV.
- Prefer positions located in Concepción or the Biobío Region.
- Prefer remote positions that explicitly accept residents of Chile.
- Consider positions in Santiago if relocation is feasible.
- Do not reject a technically suitable job solely because
  it is located outside Concepción.
- If a job requires residence or work authorization in
  another country that the candidate does not have,
  assign fit at most 2.
- Do not assume that "remote" means worldwide remote.
- Exclude job offers that requires residement in another country 

Reply ONLY with JSON:
{{"fit": <1-10>, "cv": "<exact file name>", "company": "<company>", "title": "<title>", "reason": "<max 20 words>"}}"""
    return ask_json(prompt, model)


def answer_fields(fields, profile_text, offer, model):
    """Returns {"answers": {id: value}, "unknown": [ids]} or None."""
    if _fake():
        return _fake_answers(fields, profile_text)
    prompt = f"""You are a candidate's application assistant. Answer the fields of an application form
with TRUE answers based only on their profile.

CANDIDATE PROFILE (YAML):
{profile_text}

OFFER: {offer.title} at {offer.company} ({offer.site})

FIELDS (JSON):
{json.dumps(fields, ensure_ascii=False, indent=1)}

Rules:
- Never invent or inflate experience. For "years of experience with X" use years_of_experience from the
  profile; For years of experience, use only verified values
  from years_of_experience.
- If the relevant experience is not specified,
  put the field id in "unknown".
- Never infer professional years from academic projects.
- Do not invent salary expectations or convert salaries
  without knowing the currency and period.
- Numeric fields: only the number.
- Salary / expectation / rate / amount (even in a text field): ONLY the number, no currency or words,
  derived from the profile's expected salary (monthly, yearly or hourly as asked).
- select/radio: answer EXACTLY the text of one of the options.
- For terms, privacy consent, declarations, or legal agreements:
  put the field id in "unknown" for manual review.
- Never accept agreements automatically.
- Answer in the language of the question.
- Open questions (motivation, why this job, cover letter): 2-4 concrete first-person sentences
  based on the profile and the offer.
- If a field asks for data NOT in the profile that cannot be honestly deduced
  (e.g. ID number, references), put its id in "unknown".
- Leave out optional fields that don't apply.
- Evaluate the candidate against the core responsibilities
  and mandatory technical requirements.
- Distinguish mandatory requirements from preferred skills.
- Do not treat unrelated programming languages as equivalent.
- Give credit for demonstrated academic projects,
  internships and transferable skills.
- Never invent certifications, professional experience,
  cloud deployments or production ML experience.
- If essential information is missing, explain the uncertainty.
- Base the fit score on actual evidence, not merely
  keyword overlap.

Reply ONLY with JSON: {{"answers": {{"<id>": <value>}}, "unknown": ["<id>"]}}"""
    return ask_json(prompt, model)


# Fake backend (JOBAGENT_LLM=fake): fixed rules, no network. Used by the demo and by CI.
def _fake():
    return os.environ.get("JOBAGENT_LLM") == "fake"


def _fake_score(offer, cvs):
    onsite = re.search(r"on-site|onsite|hybrid|presencial|h[ií]brido", offer.text, re.I)
    return {"fit": 2 if onsite else 8, "cv": cvs[0]["file"], "company": offer.company, "title": offer.title,
            "reason": "on-site" if onsite else "remote and matching keywords"}


def _fake_answers(fields, profile_text):
    profile = yaml.safe_load(profile_text) or {}
    years = profile.get("years_of_experience") or {}
    answers, unknown = {}, []
    for f in fields:
        words = set(re.findall(r"\w+", f["question"].lower()))
        if "years" in words or "años" in words:
            answers[f["id"]] = str(next((v for k, v in years.items() if set(k.split("_")) & words), 0))
        elif f["type"] == "textarea":
            answers[f["id"]] = profile.get("summary", "").strip()
        elif f["type"] == "checkbox":
            unknown.append(f["id"])
        else:
            unknown.append(f["id"])
    return {"answers": answers, "unknown": unknown}
