"""Preliminary EU AI Act screening.

Advisory triage, not legal advice and not a conformity assessment. Three
guarantees the dashboard relies on:

  1. Every verdict cites an article or annex point, including `minimal`.
  2. `minimal` is never returned when a field needed to decide is missing;
     that case returns `insufficient_information` and raises a review item.
  3. The business score cannot clear a gate. Article 5 blocks selection
     outright; high-risk blocks it until a qualified human has reviewed it.

The decision tree lives in config/risk/eu-ai-act.yaml so it can be changed
without touching this code.
"""

from __future__ import annotations

import sqlite3

from .. import config, llm
from ..kg import query
from ..records import UseCaseRecord

OVERALL = ["prohibited", "high_risk", "high_risk_candidate", "minimal",
           "insufficient_information"]

SYSTEM = """\
You perform a preliminary EU AI Act (Regulation (EU) 2024/1689) screening of a
proposed internal use case. You are a triage step before qualified human review,
never a substitute for it.

Return JSON only:
{
  "article_5": {"verdict": "prohibited"|"none", "matched_check": "art5_1_a..h"|null,
                "citation": "Article 5(1)(x)"|null, "rationale": "..."},
  "high_risk": {"verdict": "high_risk"|"high_risk_candidate"|"minimal"|"insufficient_information",
                "route": "annex_i"|"annex_iii"|"none",
                "matched_point": "Annex III, point N"|null,
                "derogation_applied": true|false,
                "derogation_condition": "..."|null,
                "citation": "Article 6(x)...",
                "rationale": "..."},
  "article_50": {"applies": true|false, "matched_checks": ["art50_1"],
                 "obligation": "...", "citation": "Article 50(x)"},
  "overall": "prohibited"|"high_risk"|"high_risk_candidate"|"minimal"|"insufficient_information",
  "evidence": ["direct quotes from the submitted answers"],
  "gaps": ["fields whose absence limited this screening"],
  "local_policy": ["company rules that apply, separately from the Act"],
  "human_review": {"required": true|false, "who": ["E113"], "why": "..."}
}

Order of checks:
1. Article 5 prohibited practices. Check first and absolutely. The most common
   trap for an internal productivity idea is Article 5(1)(f): inferring
   emotions of a person in the workplace. The medical and safety exception is
   narrow and does not cover wellbeing or productivity monitoring.
2. Article 6(1) with Annex I: is the AI a safety component of a regulated
   product requiring third-party conformity assessment?
3. Article 6(2) with Annex III. Point 4 covers employment and worker
   management: recruitment, filtering applications, evaluating candidates,
   promotion or termination decisions, task allocation based on personal
   traits, and monitoring or evaluating performance.
4. Article 6(3) derogation. An Annex III system is NOT high-risk if it only
   performs a narrow procedural task, improves a completed human activity,
   detects patterns without replacing human assessment, or performs a
   preparatory task. The derogation NEVER applies if the system profiles
   natural persons. If you apply it, name the condition.
5. Article 50 transparency, as a SEPARATE flag. It can apply on top of any risk
   level and never cancels one.

Hard rules:
- Quote the submitter's own words as evidence. Do not paraphrase into certainty.
- If intended purpose, affected people or human oversight are missing, you
  cannot conclude `minimal`. Return `insufficient_information` and list what is
  missing.
- Conventional automation is not an AI system under Article 3(1). If told the
  AI-fit verdict was conventional_automation, say the Act imposes no obligation
  and why.
- State company policy positions separately from the Act. They are independent
  grounds.

Worked examples:

"Detect when staff are stressed from their webcam so managers can help."
-> article_5 prohibited, matched art5_1_f, citation "Article 5(1)(f)",
   rationale naming workplace emotion inference and that the medical/safety
   exception does not apply to wellbeing monitoring. overall "prohibited".
   local_policy notes the company AI usage policy forbids it independently.

"Screen incoming CVs and rank the top ten candidates for the recruiter."
-> high_risk, route annex_iii, matched_point "Annex III, point 4",
   citation "Article 6(2) and Annex III, point 4(a)", derogation_applied false
   because ranking candidates influences the human assessment and profiles
   natural persons. overall "high_risk". local_policy notes AI people decisions
   are forbidden by company policy and the decision log of 2026-09-21.

"Classify incoming support tickets by topic and route them to the right queue."
-> article_5 none. high_risk minimal: no Annex III area is engaged; routing a
   ticket is not a decision about a person. Article 50 applies if a customer
   sees the output. overall "minimal" with the citation for why.
"""

# --------------------------------------------------------------------------- #
# offline keyword rules
# --------------------------------------------------------------------------- #
PEOPLE = {"employee", "employees", "staff", "worker", "workers", "colleague",
          "colleagues", "team", "candidate", "candidates", "applicant",
          "applicants", "person", "people", "pupil", "pupils", "student",
          "students"}

EMOTION = {"emotion", "emotions", "emotional", "mood", "stress", "stressed",
           "sentiment", "engagement", "fatigue", "wellbeing", "well-being",
           "burnout", "morale", "feeling", "feelings", "attention",
           "distracted", "distraction"}

BIOMETRIC_SENSOR = {"webcam", "camera", "cameras", "microphone", "voice",
                    "keystroke", "keystrokes", "keyboard", "wearable", "face",
                    "facial", "biometric", "fingerprint", "eye", "gaze"}

HIRING = {"cv", "cvs", "resume", "resumes", "application", "applications",
          "applicant", "applicants", "candidate", "candidates", "recruit",
          "recruiting", "recruitment", "hiring", "hire", "shortlist",
          "interview", "job ad", "vacancy"}

WORKER_MANAGEMENT = {"performance", "appraisal", "promotion", "promote",
                     "dismissal", "dismiss", "termination", "fire", "bonus",
                     "productivity", "monitor", "monitoring", "surveillance",
                     "task allocation", "allocate", "shift", "roster"}

ASSESS = {"rank", "ranking", "ranked", "score", "scoring", "screen",
          "screening", "filter", "filtering", "shortlist", "evaluate",
          "evaluating", "evaluation", "assess", "assessment", "select",
          "selection", "sort", "prioritise", "prioritize", "classify",
          "profile", "profiling", "predict"}

CREDIT = {"credit", "creditworthiness", "credit-worthiness", "scoring",
          "solvency", "payment terms", "insurance", "premium", "eligibility",
          "benefit", "benefits"}

EDUCATION_ASSESS = {"pupil", "pupils", "student", "students", "learning",
                    "exam", "exams", "grade", "grades", "admission"}

CRITICAL_INFRA = {"ventilation", "hvac", "actuate", "actuates", "control",
                  "controls", "controlling", "plant", "grid", "electricity",
                  "water", "gas", "heating", "traffic"}

CUSTOMER_FACING = {"customer", "customers", "client", "clients", "chatbot",
                   "chat", "self-service", "portal", "website", "public",
                   "visitor", "visitors", "caller", "end user"}

INTERACTS = {"chatbot", "chat", "assistant", "conversation", "conversational",
             "reply", "replies", "respond", "responds", "answer", "answers",
             "ask", "asks", "dialogue", "talk", "speaks"}

GENERATES = {"draft", "drafts", "drafting", "generate", "generates",
             "generated", "write", "writes", "writing", "translate",
             "translated", "translation", "summarise", "summarize",
             "summary", "content", "copy", "article", "articles", "image",
             "images", "case study", "case studies", "post", "newsletter"}

PUBLISHED = {"website", "publish", "published", "newsletter", "press",
             "social", "marketing", "blog", "public", "customer", "customers"}

PROFILING = {"profile", "profiling", "individual", "individuals", "per person",
             "per employee", "personal traits", "behaviour", "behavior"}

NARROW_TASK = {"categorise", "categorize", "classify", "route", "routing",
               "tag", "tagging", "extract", "extraction", "format",
               "formatting", "sort", "deduplicate", "summarise", "summarize",
               "translate", "search", "find", "retrieve", "prepare",
               "preparatory", "suggest", "draft"}


def _tokens(record: UseCaseRecord, keys: tuple[str, ...] = ()) -> set[str]:
    """Tokens from the whole record, or from named fields only.

    Classification turns on the INTENDED PURPOSE, so the Annex III tests read
    only that field plus who is affected. Scanning the whole record produced
    false positives: an idea whose users happen to include "staff" was read as
    monitoring staff.
    """
    if keys:
        text = " ".join(record.value(k) for k in keys).lower()
    else:
        text = record.searchable_text().lower()
    words = set(query.tokens(text))
    # Keep multi-word cues too; the single-token split would lose them.
    for phrase in ("task allocation", "job ad", "case study", "case studies",
                   "payment terms", "per employee", "per person",
                   "personal traits", "well-being", "credit-worthiness"):
        if phrase in text:
            words.add(phrase)
    return words


def _quote(record: UseCaseRecord, keys: tuple[str, ...]) -> list[str]:
    out = []
    for key in keys:
        field = record.get(key)
        if field.is_usable:
            value = field.value.strip()
            out.append(f"{key}: \"{value[:220]}\"")
    return out


def offline_rules(record: UseCaseRecord, conn: sqlite3.Connection,
                  ai_fit_verdict: str | None = None) -> dict:
    found = _tokens(record)
    evidence = _quote(record, ("intended_purpose", "users_affected",
                               "deployment_context", "human_oversight"))
    local_policy = [f"{p.rule} ({p.policy}, {p.cite})"
                    for p in query.policy_constraints(
                        conn, record.searchable_text())]

    result = {
        "article_5": {"verdict": "none", "matched_check": None,
                      "citation": None, "rationale": ""},
        "high_risk": {"verdict": "minimal", "route": "none",
                      "matched_point": None, "derogation_applied": False,
                      "derogation_condition": None,
                      "citation": "Article 6", "rationale": ""},
        "article_50": {"applies": False, "matched_checks": [],
                       "obligation": "", "citation": None},
        "overall": "minimal",
        "evidence": evidence,
        "gaps": [],
        "local_policy": local_policy,
        "human_review": {"required": False, "who": [], "why": ""},
    }

    # --- Step 0: is it an AI system at all? --------------------------------
    if ai_fit_verdict == "conventional_automation":
        result["high_risk"]["rationale"] = (
            "Not an AI system within the meaning of Article 3(1): the AI-fit "
            "screening concluded this is deterministic automation (a rule or a "
            "field mapping), which does not infer outputs from input. The EU AI "
            "Act imposes no obligation. Ordinary data protection duties still "
            "apply.")
        result["high_risk"]["citation"] = "Article 3(1)"
        return result

    # --- Step 1: Article 5, prohibited ------------------------------------
    purpose_only = _tokens(record, ("intended_purpose",))
    if (purpose_only & EMOTION or found & EMOTION & {"stress", "emotion",
                                                     "sentiment", "mood"}) \
            and found & PEOPLE:
        sensor = sorted(found & BIOMETRIC_SENSOR)
        result["article_5"] = {
            "verdict": "prohibited",
            "matched_check": "art5_1_f",
            "citation": "Article 5(1)(f)",
            "rationale": (
                "The use case infers emotional or affective state of people in "
                "the workplace"
                + (f" from {', '.join(sensor)} data" if sensor else "")
                + ". Article 5(1)(f) prohibits inferring emotions of a natural "
                "person in the workplace. The medical and safety exception is "
                "narrow and does not cover wellbeing, engagement or "
                "productivity monitoring."),
        }
        result["overall"] = "prohibited"
        result["human_review"] = {
            "required": True, "who": ["E113", "E110", "E26"],
            "why": "Confirm the Article 5 match and record the rejection."}
        return result

    if found & {"social", "trustworthiness", "reliability"} and \
            found & PEOPLE and found & ASSESS:
        result["article_5"] = {
            "verdict": "prohibited", "matched_check": "art5_1_c",
            "citation": "Article 5(1)(c)",
            "rationale": ("Appears to evaluate or classify people on social "
                          "behaviour or personal traits in a way that could "
                          "lead to detrimental treatment, which Article 5(1)(c) "
                          "prohibits."),
        }
        result["overall"] = "prohibited"
        result["human_review"] = {"required": True, "who": ["E113", "E110"],
                                  "why": "Confirm the Article 5(1)(c) match."}
        return result

    # --- Step 2: Annex III routes -----------------------------------------
    matched_point = None
    citation = None
    area = ""

    # Read from the intended purpose and the affected people only.
    purpose = _tokens(record, ("intended_purpose", "users_affected"))

    if (purpose & HIRING and purpose & ASSESS) or \
            (purpose & WORKER_MANAGEMENT and purpose & ASSESS
             and purpose & PEOPLE):
        matched_point = "Annex III, point 4"
        area = "employment and workers management"
        citation = ("Article 6(2) and Annex III, point 4"
                    + ("(a)" if purpose & HIRING else "(b)"))
    elif purpose & CREDIT and purpose & ASSESS:
        matched_point = "Annex III, point 5"
        area = "access to essential private services"
        citation = "Article 6(2) and Annex III, point 5(b)"
    elif purpose & EDUCATION_ASSESS and purpose & ASSESS:
        matched_point = "Annex III, point 3"
        area = "education and vocational training"
        citation = "Article 6(2) and Annex III, point 3"
    elif purpose & CRITICAL_INFRA and purpose & {"actuate", "actuates",
                                                 "control", "controls",
                                                 "controlling"}:
        matched_point = "Annex III, point 2"
        area = "critical infrastructure"
        citation = "Article 6(2) and Annex III, point 2"
    elif purpose & BIOMETRIC_SENSOR and purpose & {"identify", "identification",
                                                   "recognise", "recognize"}:
        matched_point = "Annex III, point 1"
        area = "biometrics"
        citation = "Article 6(2) and Annex III, point 1"

    # --- Step 3: Article 50 transparency, independent of the above --------
    transparency: list[str] = []
    if found & INTERACTS and found & CUSTOMER_FACING:
        transparency.append("art50_1")
    if found & GENERATES and found & PUBLISHED:
        transparency.append("art50_2")
    if transparency:
        obligations = []
        if "art50_1" in transparency:
            obligations.append(
                "Tell the person they are interacting with an AI system "
                "(Article 50(1)), unless it is obvious.")
        if "art50_2" in transparency:
            obligations.append(
                "Mark generated or manipulated content in a machine-readable "
                "format as artificially generated (Article 50(2)).")
        result["article_50"] = {
            "applies": True,
            "matched_checks": transparency,
            "obligation": " ".join(obligations),
            "citation": "Article 50(1)" if "art50_1" in transparency
                        else "Article 50(2)",
        }

    # --- Gaps: what we could not determine --------------------------------
    blockers = config.risk_config()["insufficient_information"][
        "blocks_verdict_when_missing"]
    gaps = []
    for key, blocked in blockers.items():
        if not record.get(key).is_usable:
            gaps.append(f"{key} (would decide: {', '.join(blocked)})")
    result["gaps"] = gaps

    if matched_point:
        # Article 6(3) derogation: narrow procedural work, and no profiling.
        profiling = bool(found & PROFILING and found & PEOPLE)
        narrow = bool(found & NARROW_TASK)
        if profiling:
            result["high_risk"] = {
                "verdict": "high_risk", "route": "annex_iii",
                "matched_point": matched_point, "derogation_applied": False,
                "derogation_condition": None, "citation": citation,
                "rationale": (
                    f"Engages {area} ({matched_point}). The Article 6(3) "
                    f"derogation cannot apply because the system profiles "
                    f"natural persons, which the final subparagraph of Article "
                    f"6(3) excludes outright."),
            }
            result["overall"] = "high_risk"
            result["human_review"] = {
                "required": True, "who": ["E113", "E110"],
                "why": ("Qualified legal review and a conformity plan are "
                        "needed before any build.")}
        elif narrow and not (found & HIRING or found & WORKER_MANAGEMENT):
            result["high_risk"] = {
                "verdict": "minimal", "route": "annex_iii",
                "matched_point": matched_point, "derogation_applied": True,
                "derogation_condition": (
                    "performs a narrow procedural task without replacing or "
                    "influencing the human assessment"),
                "citation": "Article 6(3)",
                "rationale": (
                    f"Touches {area} ({matched_point}), but the Article 6(3) "
                    f"derogation applies: the system performs a narrow "
                    f"procedural task and does not profile natural persons. "
                    f"This reasoning must be documented by the provider."),
            }
            result["overall"] = "minimal"
            result["human_review"] = {
                "required": True, "who": ["E113"],
                "why": "Confirm the Article 6(3) derogation assessment."}
        else:
            result["high_risk"] = {
                "verdict": "high_risk", "route": "annex_iii",
                "matched_point": matched_point, "derogation_applied": False,
                "derogation_condition": None, "citation": citation,
                "rationale": (
                    f"Engages {area} ({matched_point}). The output influences "
                    f"an assessment of a person, so the Article 6(3) "
                    f"derogation does not apply."),
            }
            result["overall"] = "high_risk"
            result["human_review"] = {
                "required": True, "who": ["E113", "E110"],
                "why": ("Qualified legal review and a conformity plan are "
                        "needed before any build.")}
    elif gaps:
        # No Annex III match found, but we lack what we would need to be sure.
        result["high_risk"] = {
            "verdict": "insufficient_information", "route": "none",
            "matched_point": None, "derogation_applied": False,
            "derogation_condition": None, "citation": "Article 6",
            "rationale": (
                "No Annex I or Annex III area is apparent from what was "
                "submitted, but the screening cannot conclude minimal risk "
                "because required information is missing: "
                + "; ".join(gaps) + ". Asked of the submitter rather than "
                "assumed."),
        }
        result["overall"] = "insufficient_information"
        result["human_review"] = {
            "required": True, "who": ["E26"],
            "why": "The submitter needs to answer the missing fields."}
    else:
        result["high_risk"]["rationale"] = (
            "No prohibited practice under Article 5. No Annex I safety-component "
            "route and no Annex III area is engaged: the use case does not "
            "assess, rank or monitor natural persons, and does not operate "
            "critical infrastructure. Classified minimal risk on the "
            "information provided.")

    if result["article_50"]["applies"] and result["overall"] == "minimal":
        result["human_review"] = {
            "required": True, "who": ["E113"],
            "why": "Confirm the Article 50 disclosure wording."}

    # Company policy can block independently of the Act.
    if any(p.severity == "blocks" for p in query.policy_constraints(
            conn, record.searchable_text())):
        result["human_review"]["required"] = True
        if "E113" not in result["human_review"]["who"]:
            result["human_review"]["who"].append("E113")
        result["human_review"]["why"] = (
            (result["human_review"]["why"] + " ").strip()
            + " Company policy independently forbids part of this.")

    return result


def gate(payload: dict) -> tuple[bool, str]:
    """Whether the board may select this idea, and why not.

    Called by the board before any decision is recorded. No business score is
    an input here - that is the whole point.
    """
    overall = payload.get("overall", "insufficient_information")
    if overall == "prohibited":
        citation = payload["article_5"].get("citation", "Article 5")
        return False, f"Blocked: prohibited practice under {citation}."
    if overall in ("high_risk", "high_risk_candidate"):
        who = ", ".join(payload.get("human_review", {}).get("who", [])) or "E113"
        return False, (f"Blocked pending qualified review by {who}: potential "
                       f"high-risk classification under "
                       f"{payload['high_risk'].get('citation', 'Article 6')}.")
    if overall == "insufficient_information":
        return False, ("Blocked: screening incomplete because required "
                       "information is missing.")
    if any(p for p in payload.get("local_policy", []) if p):
        # Local policy alone does not block selection, but it is surfaced.
        pass
    return True, ""


def assess(record: UseCaseRecord, conn: sqlite3.Connection,
           ai_fit_verdict: str | None = None) -> tuple[dict, str]:
    policies = query.policy_constraints(conn, record.searchable_text())
    context = [f"AI-fit verdict from the previous step: {ai_fit_verdict or 'unknown'}",
               "", "Company policy rules that matched this text:"]
    context += ([f"- [{p.severity}] {p.rule} ({p.cite})" for p in policies]
                or ["- none"])

    user = f"{record.as_prompt_block()}\n\n" + "\n".join(context)
    payload, model = llm.generate_json(
        SYSTEM, user,
        offline=lambda: offline_rules(record, conn, ai_fit_verdict),
        required_keys=("article_5", "high_risk", "article_50", "overall"),
    )
    if payload.get("overall") not in OVERALL:
        payload = offline_rules(record, conn, ai_fit_verdict)
        model = llm.OFFLINE_MODEL + " (invalid verdict from model)"

    # Never let a model downgrade to `minimal` while required fields are absent.
    blockers = config.risk_config()["insufficient_information"][
        "blocks_verdict_when_missing"]
    missing = [k for k in blockers if not record.get(k).is_usable]
    if payload.get("overall") == "minimal" and missing:
        payload["overall"] = "insufficient_information"
        payload.setdefault("gaps", []).extend(missing)
        payload["high_risk"]["verdict"] = "insufficient_information"
        payload["high_risk"]["rationale"] = (
            payload["high_risk"].get("rationale", "")
            + f" Downgraded to insufficient_information: {', '.join(missing)} "
              f"not provided, so minimal risk cannot be concluded.")
    return payload, model
