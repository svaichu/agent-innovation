---
title: "IT systems"
owner: E52
classification: internal
last_updated: 2026-11-26
---

# IT systems

Sixteen systems. Also available as [systems.csv](systems.csv).

`API or automation` is the first thing to check before proposing any integration or AI use case: a system marked `no` can only be reached by manual export.

| System | Purpose | Owner | Personal data | API or automation | In data warehouse |
|---|---|---|---|---|---|
| HubSpot | CRM and marketing email | E10 | yes | yes | yes |
| Zendesk | Support tickets and help centre | E16 | yes | yes | yes |
| Canopy | Our product platform | E07 | yes | yes | yes |
| DATEV | Accounting | E23 | yes | export only | yes |
| Jira | Product and engineering work | E03 | limited | yes | no |
| GitHub | Source code | E02 | limited | yes | no |
| AWS (Frankfurt) | Hosting | E09 | yes | yes | no |
| Grafana | Monitoring | E09 | no | yes | no |
| Personio | HR records, leave and recruiting | E119 | yes | yes | no |
| Google Workspace | Email, files, calendar | E09 | yes | yes | no |
| Slack | Chat | E09 | yes | yes | no |
| Confluence | Internal documentation | E52 | limited | yes | no |
| Data warehouse | Analytics store | E53 | yes | yes | n/a |
| BI tool | Reporting and dashboards | E56 | limited | yes | n/a |
| Inventory spreadsheet | Stock and orders | E109 | limited | no | no |
| RMA spreadsheet | Returns and fault codes | E22 | limited | no | no |

## Integrations today
- Website forms create leads in HubSpot.
- Zendesk shows basic account data from HubSpot (one-way, nightly).
- Jira links to GitHub.
- HubSpot, Zendesk, Canopy and DATEV load nightly into the data warehouse; the BI tool reads only from there.
- Personio exports payroll input to DATEV as a monthly file.

## Known gaps
- **No integration between HubSpot, the inventory spreadsheet and DATEV.** Order data is retyped.
- The inventory and RMA spreadsheets have no API at all, so anything built on them needs a migration first.
- Confluence, Jira, Personio and Google Workspace are not in the warehouse, so reporting across them is manual.
- Site survey notes and calibration results live outside every system listed here.

## Rules
- New software that processes personal data needs approval from E23 and E09, whatever the price. See [procurement](../policies/procurement.md).
- Customer data stays in EU-hosted systems.
