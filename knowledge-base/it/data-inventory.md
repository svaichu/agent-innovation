---
title: "Data inventory"
owner: E52
classification: internal
last_updated: 2026-11-26
---

# Data inventory

**Check this before proposing analytics or AI work.** An idea that needs data we do not have, or data of low quality, is not feasible yet however good it sounds. Also available as [data-inventory.csv](data-inventory.csv).

Quality is judged for machine use: `high` means usable as it stands, `medium` means usable after cleaning, `low` means the data must be captured differently first.

| Dataset | Location | Owner | Volume | Quality | Personal data |
|---|---|---|---|---|---|
| Sensor measurements | Canopy | E07 | over 4 billion readings, 3 years | high | no (room level) |
| Device health logs | AWS | E09 | 12 months | high | no |
| Supplier invoices | DATEV and email | E24 | about 13,000 per year | high once booked | limited |
| Support tickets | Zendesk | E16 | about 52,000 since 2022 | medium: categories inconsistent | yes |
| CRM deals and notes | HubSpot | E10 | about 11,500 deals since 2020 | medium: notes often missing | yes |
| Tender responses | Google Workspace | E11 | about 420 documents | medium: unstructured | limited |
| Calibration results | Spreadsheets | E05 | about 96,000 devices | medium | no |
| Return fault codes | RMA spreadsheet | E22 | about 3,600 returns | medium | limited |
| Internal helpdesk tickets | Helpdesk tool | E52 | about 7,500 since 2024 | medium: free text only | yes |
| Candidate applications | Personio | E118 | about 2,400 per year | medium | yes: special care, see below |
| Website content | Website content system | E15 | 190 pages | medium | no |
| Internal documentation | Confluence | E52 | about 1,900 pages | low to medium: many outdated | limited |
| Help centre articles | Zendesk | E86 | 85 articles | low to medium: about 30 outdated | no |
| Stock movements | Inventory spreadsheet | E109 | since 2023 | low: gaps and manual errors | no |
| Site survey notes | Paper and Google Drive | E19 | about 900 surveys | low: handwritten, not structured | limited |
| Customer onboarding trackers | Personal spreadsheets | E16 | 780 customers | low: a different format per person | yes |

## Datasets that need special care
- **Candidate applications** and **HR records**: personal data in an employment context. Any automated assessment of people is forbidden by the [AI usage policy](../policies/ai-usage.md) and would likely be high-risk under the EU AI Act.
- **Support tickets**, **CRM notes** and **onboarding trackers** contain customer contact details. Anything built on them needs approval from E113 (Data Protection Officer).
- **Sensor measurements** are room-level and carry no personal data, which makes them the easiest dataset to build on.
