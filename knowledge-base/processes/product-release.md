---
title: "Software and firmware release"
owner: E03
classification: internal
last_updated: 2026-11-26
---

# Software and firmware release

**Process owner:** Priya Raman (E03)

**Starts when:** planned work in Jira is ready.

## Steps
1. A pull request needs one review and passing automated tests.
2. Deploy to the staging system and test.
3. Firmware: test on the lab rig for at least 48 hours.
4. E03 approves the release notes; E09 deploys Canopy.
5. Firmware rolls out over the air to 5% of devices, then 25% after 3 days, then all after 7 days.
6. Roll back if offline devices rise by more than 2 percentage points.
