---
title: "Product & Engineering"
owner: E03
classification: internal
last_updated: 2026-11-26
---

# Product & Engineering

## Mission
Build reliable sensors and software.

## Team (30)
Leadership and named owners. The full list is in the [directory](../people/directory.md).

| ID | Name | Role | Skills |
|---|---|---|---|
| E03 | Priya Raman | Product Manager | Roadmapping; user research |
| E04 | Lukas Brandt | Hardware Lead | PCB design; certification |
| E05 | Mei Tanaka | Hardware Engineer | Sensor calibration; test rigs |
| E06 | Tomasz Nowak | Firmware Engineer | C; LoRaWAN; over-the-air updates |
| E07 | Aylin Demir | Backend Developer | Python; PostgreSQL; AWS |
| E08 | Felix Hartmann | Frontend Developer | TypeScript; React; accessibility |
| E09 | David Okafor | DevOps & IT Administrator | AWS; monitoring; identity management |
| E29 | Daniel Osei | Engineering Manager, Software | People management; delivery planning; Python |
| E39 | Lars Frey | Product Manager, Canopy | Roadmapping; analytics; interviews |

Composition: 6 hardware and mechanical, 4 firmware, 6 backend, 3 frontend, 1 QA, 3 DevOps and SRE, 4 product, design and documentation, 3 leads.

## Responsibilities
- Hardware, firmware and Canopy development
- Releases and certification
- Cloud operations

## Tools
Jira, GitHub, AWS, Grafana, Slack, Confluence

## Key figures, October 2026

| Measure | Current | Target |
|---|---|---|
| Canopy availability | 99.93% | 99.9% |
| Open bugs, priority high | 34 | under 20 |
| Releases per month | 4 | 4 |
| Median pull request review time | 19 hours | under 8 hours |
| Share of developer time on support questions | 18% | under 10% |

## Known pain points
- Bug reports from support often lack firmware version and logs, so about a third are sent back for more information.
- Calibration results are typed from the test rig into spreadsheets, roughly 400 devices per week.
- About 18% of developer time goes to answering support and sales questions that are already documented somewhere.
- Release notes are written by hand from Jira tickets before every release.
- Nobody can answer "which customers run which firmware version" without a manual export.
- Test coverage of the firmware reconnect path is thin, and reconnect bugs keep returning.
