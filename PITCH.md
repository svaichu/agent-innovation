# AI Compass — plenary notes

Problem / Approach / Limits / Next step. Day 2, 11:20.

---

## Problem

Gartner expects AI spending to grow 47% in 2026. BCG found 60% of companies
get little economic value from it. The gap is not model quality — it is that
most firms have no path from a staff idea to a funded project.

In our fictional 120-person company the symptoms are written down in its own
knowledge base, department by department:

- *"No single list of internal improvement ideas. The same proposal reaches the
  leadership sync from two departments more than once a quarter."*
- *"Ideas arrive in different formats, so they cannot be compared: some carry
  numbers, most do not."*
- *"Nobody tracks whether a funded internal project delivered the benefit it
  promised."*

And the budget is small and real: **EUR 250,000** for internal tooling in 2027,
about **60 engineering person-days a month**, against **1,058 person-days**
already committed to 14 active projects. The portfolio is booked into 2028. So
ideas have to be ranked, not merely collected.

## Approach

An employee describes an idea in a chat. Five agents then assess it, and a
decision board of four people sees the result.

1. **Consistent capture.** Eight core fields, identical for every submission.
   The chat asks for what is missing and records "I do not know" as unknown.
2. **Overlap detection.** Lexical similarity plus *capability signatures* —
   what would actually need building. This is what catches Sales wanting to
   answer tender questions and Support wanting to deflect repeat tickets: two
   departments, no shared vocabulary, same machine.
3. **Is AI even the right tool?** Of 42 seeded ideas, two are plain integration
   work. Saying so is worth more than scoring them.
4. **EU AI Act screening.** Article 5, Article 6 with Annexes I and III, and
   Article 50 as a separate flag. Every verdict cites its article. The
   Article 6(3) derogation is applied explicitly, which is what keeps ordinary
   ticket routing *out* of high-risk.
5. **Feasibility against this company.** Not an opinion — queries against a
   graph built from the knowledge base: who holds the skill, whether the system
   has an API, whether the data is good enough, cost against the remaining
   budget, effort against the committed backlog. Every dimension cites its
   source.
6. **Configurable RICE**, with the business score and the risk flags in
   separate columns.

Two things are enforced in code rather than promised in prose:

- **No score can clear a risk gate.** The gate function is not given the score.
  Press *Select* on the webcam-stress idea and it refuses, citing Article
  5(1)(f).
- **Nothing is invented.** The screening cannot return "minimal risk" while a
  field it needs is missing. It returns "cannot tell yet" and asks the
  submitter by name.

## What it found

| | |
|---|---|
| Ideas assessed | 43 (42 seeded + 1 submitted through the intake chat) |
| Blocked by a risk gate | 10 — one prohibited, two high-risk, seven incomplete |
| Reclassified as conventional automation | 2 |
| Overlap links suggested | 52, of which 37 cross-department |
| Selectable work, costed | EUR 125,915 and 250 person-days against EUR 142,000 unspent |

The highest-ranked idea is not the most exciting one. It is Support wanting to
answer repeat tickets from the help centre: 1,250 tickets a month of which 40%
repeat, Zendesk has an API, 52,000 labelled examples already exist, and it
needs four weeks. It also happens to be one half of our duplicate pair — so
building it serves Sales' tender problem too, which is exactly the finding
nobody had before.

## Limits

- The screening is **triage for a qualified human**, not legal advice. Every
  non-minimal verdict routes to the Data Protection Officer and the Head of
  Quality & Regulatory.
- **RICE inputs are self-reported.** Confidence is the honesty dial; a guess is
  published as a guess rather than rounded up.
- **It runs with no API key**, on a deterministic rule engine. That is
  resilience, not quality: the rules get these scenarios right and are visibly
  thinner than a model.
- **Overlap detection is lexical plus heuristic.** Pure TF-IDF missed our
  headline duplicate pair entirely — cosine 0.15, because "tenders" and
  "tickets" share no words. Embeddings would do this properly.
- **One fictional company.** The questionnaire and scoring are per-client
  config files, but multi-tenancy is untested.
- Thresholds were tuned on 42 ideas. Real portfolios will need retuning.

## Next step

The one experiment that would tell us most: **replace the similarity heuristic
with embeddings and measure it against a labelled set of real duplicate pairs.**
Overlap detection is where the money is — a duplicate caught before two teams
build it pays for the whole exercise — and it is the part we are currently
least confident in.

After that, in order: feed back whether funded projects delivered the benefit
they promised (nobody tracks this today, and it is the only way the scores ever
get calibrated); then collect the four fields the intake chat does not yet ask
for, so submissions stop arriving half-complete.
