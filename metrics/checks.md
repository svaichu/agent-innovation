---
name: checks
version: 2
---
# AI fit and EU AI Act screening

These checks give **flags, not a score**. They are not a metric: they apply whichever metric is
active, are shown next to the score and never change it. A high business score must not override a
regulatory concern. The agent recommends; people decide. Result: preliminary screening, not legal
advice.

Answer only the questions below (true / false / ids), or `null` when the idea does not say. These
answers are not quote-checked (a "no" cannot be quoted), so a person has to confirm them.
`portal/checks.py` applies the rules, so every flag carries its rule or article. Unanswered AI Act
questions never give the tier "minimal".

## 1. AI, conventional automation or more research?

Questions (true / false / null):
- `low_volume_low_value`: does it happen rarely and save little?
- `structured_input`: is the input mostly forms, tables or fixed fields?
- `rule_expressible`: could the steps be written as clear if-then rules?
- `needs_judgement`: are there many exceptions, or is judgement needed?
- `unstructured_or_language`: free text, documents, images or speech?
- `deterministic_required`: must the same input always give exactly the same result?
- `prediction_task`: does it predict something from past data?
- `has_historical_data`: does that data exist in usable quality? (check `it/data-inventory.csv`)

Rules, in order (sources: Google PAIR; Google Rules of ML #1 and #3; Microsoft CAF; Wellmann et al. 2020 on RPA):
1. low volume and low value -> **more research** (probably not worth automating)
2. structured input, rule-expressible, no judgement -> **conventional automation**
3. prediction task without usable data -> **more research**
4. same result required every time -> **conventional automation**
5. language, judgement, or prediction with data -> **AI**
6. otherwise -> **more research**

## 2. EU AI Act screen

An idea that would otherwise be "minimal" becomes "needs_review" when it mentions one of the
`risk_terms` below (regular expressions, case ignored, English and German).

Questions:
- `art5_practices`: list of matched banned practices (ids below), or `[]`
- `annex_i_safety_component`: is it a safety part of a regulated product (machine, vehicle, medical device)?
- `annex_iii_area`: one area id below, `"none"`, or `null`
- `profiles_people`: does it rate or profile individual people?
- `narrow_or_preparatory`: does it only do a narrow procedural or preparatory task, without materially influencing the decision?
- `art50`: list of transparency cases below, or `[]`

Order (Regulation (EU) 2024/1689 as amended by Regulation (EU) 2026/1744): Art. 5 -> Art. 6(1) -> Annex III with
the Art. 6(3) exception (never when profiling) -> Art. 50 as a separate flag -> otherwise minimal, but only when
every question was answered.

```json
{
  "art5": {
    "manipulation": "Art. 5(1)(a) manipulative or deceptive techniques causing significant harm",
    "vulnerability": "Art. 5(1)(b) exploiting vulnerabilities (age, disability, social or economic situation)",
    "social_scoring": "Art. 5(1)(c) social scoring",
    "crime_prediction": "Art. 5(1)(d) predicting crime from profiling only",
    "face_scraping": "Art. 5(1)(e) untargeted scraping of facial images",
    "emotion_work_education": "Art. 5(1)(f) emotion recognition at work or in education",
    "biometric_categorisation": "Art. 5(1)(g) biometric categorisation of sensitive traits",
    "realtime_biometric_police": "Art. 5(1)(h) real-time remote biometric identification for law enforcement",
    "intimate_deepfakes": "Art. 5(1)(ba) non-consensual intimate deepfakes (from 2 Dec 2026)",
    "csam": "Art. 5(1)(bb) child sexual abuse material (from 2 Dec 2026)"
  },
  "annex_iii": {
    "biometrics": "Annex III(1) biometrics",
    "critical_infrastructure": "Annex III(2) critical infrastructure",
    "education": "Annex III(3) education and vocational training",
    "employment": "Annex III(4) employment and workers management",
    "essential_services": "Annex III(5) essential private and public services (credit, insurance, benefits)",
    "law_enforcement": "Annex III(6) law enforcement",
    "migration": "Annex III(7) migration, asylum and border control",
    "justice_democracy": "Annex III(8) administration of justice and democratic processes"
  },
  "art50": {
    "chatbot": "Art. 50(1) tell people they are interacting with an AI system",
    "synthetic_content": "Art. 50(2) mark AI-generated content in machine-readable form",
    "emotion_or_biometric_categorisation": "Art. 50(3) inform people exposed to emotion recognition or biometric categorisation",
    "deepfake_or_public_text": "Art. 50(4) disclose deepfakes and AI-generated text on public-interest matters"
  },
  "risk_terms": [
    "emotion", "biometri", "facial", "face (recognition|scan|image|detection)", "webcam", "surveil",
    "monitor\\w* (staff|employee|agent)", "hiring", "recruit", "applicant", "\\bcvs?\\b", "candidate",
    "performance review", "promotion (decision|review)", "dismiss", "termination", "credit(?! notes?)",
    "insurance", "\\bschools?\\b", "student", "\\bexams?\\b", "examination", "police", "migration",
    "deepfake", "manipulat",
    "gesichtserkennung", "überwach", "bewerb(er|ung)", "einstellungsverfahren", "kündigung",
    "leistungsbeurteilung", "beförderung", "kredit", "versicherung", "schüler", "prüfung(en)? der (schüler|studierenden)",
    "polizei"
  ],
  "dates": {
    "prohibited": "applies since 2 Feb 2025",
    "high_risk_annex_iii": "applies from 2 Dec 2027",
    "high_risk_annex_i": "applies from 2 Aug 2028",
    "art50": "applies since 2 Aug 2026"
  }
}
```

Article list adapted from a2welt/ai-act-mcp `rules/ruleset.json` (MIT); dates from the Digital Omnibus
(Regulation (EU) 2026/1744, in force 27 Jul 2026). The Commission's Art. 6 guidelines are still a draft
(19 May 2026), so Annex III results are preliminary.
