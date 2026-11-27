"""Seeded use cases, part 1 of 2: the demo scenarios and the strong cases.

Every idea traces to a documented pain point in knowledge-base/departments/*,
so the assessments cite real evidence rather than inventing a problem. Fields
follow config/intake-questionnaire.yaml.

`demo` marks an idea required by the challenge brief's demo script.
"""

CASES = [
    # ======================= DEMO 1: duplicate pair =======================
    # Two departments, same underlying capability, neither knows about the
    # other. This is the overlap the brief asks us to detect.
    dict(
        id="UC-001", title="Answer tender questions from our past responses",
        author_id="E11", demo="duplicate_a",
        fields=dict(
            problem="Public tenders take 2 to 4 days each to answer and we answer about 14 per month. Most of the work is hunting through the roughly 420 tender documents we have already written to find text we can reuse.",
            intended_purpose="Search our past tender responses and draft an answer to each tender question, which the account executive then edits and approves.",
            users_affected="The 9 account executives and 2 sales managers use it. About 14 tenders per month. No individual outside the company is assessed by it.",
            deployment_context="Internal only, runs on documents in Google Workspace. The drafted text is reviewed before it ever leaves the company.",
            data="Tender responses in Google Workspace, about 420 documents, unstructured. Product data sheets and the price list.",
            expected_benefit="Cut tender answering from 2 to 4 days down to under a day. That is roughly 25 days of account executive time per month.",
            effort="Three weeks for two people, one backend and one account executive to check the output.",
            human_oversight="The account executive reads and edits every answer before submission. Nothing is submitted automatically.")),
    dict(
        id="UC-002", title="Answer repeat support tickets from the help centre",
        author_id="E86", demo="duplicate_b",
        fields=dict(
            problem="About 40% of our 1,250 tickets per month are repeat questions on connectivity, readings and logins. Support specialists retype the same explanations, and 30 of the 85 help centre articles are out of date so people do not trust them.",
            intended_purpose="Search the help centre and past resolved tickets, then draft a first reply the support specialist edits before sending.",
            users_affected="The 10 support specialists use it. Around 500 customers per month receive a reply drafted this way.",
            deployment_context="Runs inside Zendesk when a ticket arrives. The drafted reply is customer-facing once a specialist approves it.",
            data="Zendesk support tickets, about 52,000 since 2022, categories inconsistent. The 85 help centre articles.",
            expected_benefit="Halve handling time on repeat questions, which is about 500 tickets per month, and lift first response within SLA from 88% towards 95%.",
            effort="About four weeks for two people.",
            human_oversight="A support specialist reads and approves every draft. The AI never replies to a customer directly.")),

    # ============== DEMO 2: conventional automation wins ==================
    dict(
        id="UC-003", title="Stop retyping HubSpot orders into the inventory sheet",
        author_id="E109", demo="conventional_automation",
        fields=dict(
            problem="Order data is retyped from HubSpot into the inventory spreadsheet, about 180 orders per month. Typing mistakes cause stock record errors, accuracy sits at 87%, and we had two stock-outs in 2026.",
            intended_purpose="Copy each won deal from HubSpot into the inventory records automatically, using the same fixed set of fields we type by hand today.",
            users_affected="Two logistics coordinators, the inventory controller and the warehouse lead. No customer and no individual is assessed.",
            deployment_context="Internal only. Reads the HubSpot deals API and writes to the inventory records.",
            data="HubSpot deals, about 11,500 since 2020. Stock movements in the inventory spreadsheet, low quality with gaps.",
            expected_benefit="Removes the retyping entirely, about 15 hours per month, and removes one whole class of stock error.",
            effort="Two weeks for one backend developer, once there is something to write into.",
            human_oversight="The inventory controller reviews a daily log of what was written and can reverse any row.")),

    # ===================== DEMO 3: strong AI use case =====================
    dict(
        id="UC-004", title="Categorise and route incoming tickets",
        author_id="E77", demo="promising_ai",
        fields=dict(
            problem="Every one of our 1,250 tickets per month is categorised and routed by hand. It costs the team lead about an hour a day and mis-routed tickets are the main reason we miss the SLA on 12% of first responses.",
            intended_purpose="Read each incoming ticket and set its category, priority and queue. It labels and routes work; it does not answer the customer and does not assess any person.",
            users_affected="The support team lead and 10 support specialists. About 1,250 tickets per month are routed.",
            deployment_context="Internal, runs inside Zendesk on ticket creation. The customer never sees its output.",
            data="Zendesk support tickets, about 52,000 since 2022 with inconsistent categories, which is exactly the label noise to clean up first.",
            expected_benefit="Give the team lead back about 20 hours a month and cut mis-routing, which should move first response within SLA from 88% to above 95%.",
            effort="About three weeks for two people, mostly backend with support input on the label set.",
            human_oversight="The team lead reviews a daily sample and can re-route anything. Categories are suggestions the specialist can override.")),

    # =============== DEMO 4: incomplete, must ask not guess ===============
    dict(
        id="UC-005", title="Use AI for our content somehow",
        author_id="E75", demo="incomplete", status="draft",
        fields=dict(
            problem="Our content takes too long to produce.")),

    # ================ Risk showcases: prohibited and high-risk ============
    dict(
        id="UC-006", title="Spot stressed colleagues early",
        author_id="E119", demo="prohibited",
        fields=dict(
            problem="Managers notice burnout too late, usually only after someone is already off sick. We had four long-term absences in 2026.",
            intended_purpose="Analyse webcam images and keyboard activity during the working day to infer each employee's stress level, and show managers a weekly wellbeing score per person.",
            users_affected="All 120 employees would be monitored. The 18 managers would see the per-person scores.",
            deployment_context="Runs continuously on company laptops. Internal manager dashboard.",
            data="Webcam images, keystroke timing and calendar load per named employee.",
            expected_benefit="Fewer long-term absences. Perhaps 20% fewer, though we have not measured this.",
            effort="Unclear, maybe two months.",
            human_oversight="Managers decide what to do with a score. There is no review of the score itself.")),
    dict(
        id="UC-007", title="Screen and rank incoming applications",
        author_id="E118", demo="high_risk",
        fields=dict(
            problem="We receive about 140 applications per open role and 7 roles are open. Screening them by hand takes the recruiter roughly 20 hours a week and time to fill is 68 days against a 45 day target.",
            intended_purpose="Read each application and rank candidates from best to worst against the job description, so the recruiter interviews the top ten.",
            users_affected="The recruiter and the hiring managers use it. About 2,400 candidates per year are ranked by it.",
            deployment_context="Internal, runs on each new application in Personio.",
            data="Candidate applications in Personio, about 2,400 per year, containing personal data.",
            expected_benefit="Saves the recruiter about 15 hours a week and should shorten time to fill substantially.",
            effort="About four weeks for one developer plus recruiter time.",
            human_oversight="The recruiter reads the top ten. Candidates ranked below the top ten are not read.")),

    # ========================== Strong, feasible ==========================
    dict(
        id="UC-008", title="Answer internal policy questions for new starters",
        author_id="E119",
        fields=dict(
            problem="New staff ask the same twenty policy questions every time: leave, expenses, core hours, learning budget. People Operations answers them one by one, and with 7 roles open we onboard someone most weeks.",
            intended_purpose="Answer employee questions about internal policies from this knowledge base, with a link to the page the answer came from.",
            users_affected="All 120 employees can use it, most heavily the roughly 40 people joining or changing role each year. No individual is assessed.",
            deployment_context="Internal only, a chat window on the intranet. Not customer-facing.",
            data="This knowledge base: policies, processes and the directory. Internal documentation in Confluence, about 1,900 pages, many outdated.",
            expected_benefit="Save People Operations about 10 hours a month and give new starters an answer in seconds instead of a day.",
            effort="Two weeks for one developer, plus a week of content tidying.",
            human_oversight="Answers always cite the source page so the employee can check. People Operations reviews the unanswered questions weekly.")),
    dict(
        id="UC-009", title="Draft release notes from Jira tickets",
        author_id="E41",
        fields=dict(
            problem="Release notes are written by hand from Jira tickets before every release, and we ship 4 releases per month. It takes the technical writer about half a day each time and the notes often miss customer-visible changes.",
            intended_purpose="Read the Jira tickets in a release and draft the release notes, grouped by what changed for the customer.",
            users_affected="The technical writer, the product manager and the 30 people in engineering. Customers read the published result.",
            deployment_context="Internal drafting tool. The output is published to customers after the product manager approves it.",
            data="Jira issues, which have an API but are not in the data warehouse. Past release notes.",
            expected_benefit="Save about 8 hours per month and stop missing customer-visible changes.",
            effort="Two weeks for one developer.",
            human_oversight="The product manager approves the release notes before publication, as the release process already requires.")),
    dict(
        id="UC-010", title="Pull the leadership figures together automatically",
        author_id="E27",
        fields=dict(
            problem="Figures for the Monday leadership sync are copied by hand from six systems, about 5 hours per week, and several numbers exist in two places with two values.",
            intended_purpose="Collect the agreed leadership metrics from the data warehouse each Monday morning and produce one reconciled summary.",
            users_affected="The 10 people in the leadership sync. The Chief of Staff prepares it today.",
            deployment_context="Internal only. Reads the data warehouse and the BI tool.",
            data="Data warehouse, which already holds HubSpot, Zendesk, Canopy and DATEV. Inventory and Personio are not loaded yet.",
            expected_benefit="Save about 20 hours per month and end the two-values problem for the metrics that are in the warehouse.",
            effort="Three weeks for one data engineer and one analyst.",
            human_oversight="The Chief of Staff reviews the summary before it goes to the sync.")),
    dict(
        id="UC-011", title="Extract calibration results from the test rig",
        author_id="E46",
        fields=dict(
            problem="Calibration results are typed from the test rig into spreadsheets, roughly 400 devices per week. Transcription errors make the calibration record unreliable and we hold about 96,000 device records.",
            intended_purpose="Read the calibration result file the rig already writes and load it into a structured store, replacing the manual typing.",
            users_affected="Two quality technicians, the test engineer and the hardware lead. About 1,700 devices per month.",
            deployment_context="Internal, on the assembly line in Aachen. Not customer-facing.",
            data="Calibration results currently in spreadsheets, about 96,000 devices, medium quality. The rig writes a structured file already.",
            expected_benefit="Removes about 12 hours per week of typing and makes the calibration record trustworthy for the first time.",
            effort="Two weeks for one developer with test engineer support.",
            human_oversight="The quality technician reviews any device the rig flags as out of tolerance, as today.")),
    dict(
        id="UC-012", title="Flag at-risk accounts before the renewal month",
        author_id="E90",
        fields=dict(
            problem="We only see a renewal is in trouble in the renewal month. Annual revenue churn is 7% against a 5% target, and two of our sixteen key accounts are currently at risk.",
            intended_purpose="Combine product usage, ticket history and renewal dates to flag accounts that look likely to churn, so a success manager can intervene early.",
            users_affected="The 4 customer success managers and the head of customer success. About 780 customer accounts are scored, not individual people.",
            deployment_context="Internal only. Reads Canopy usage, Zendesk and HubSpot. Customers never see the flag.",
            data="Canopy sensor measurements, over 4 billion readings, high quality. Zendesk tickets. HubSpot deals, notes often missing.",
            expected_benefit="If we save even a fifth of the churn that is currently a surprise, that is roughly EUR 60,000 of ARR a year.",
            effort="About five weeks for a data engineer and an analyst.",
            human_oversight="A success manager reviews every flag and decides what to do. The flag is about an account, not a person, and nothing happens automatically.")),
    dict(
        id="UC-013", title="Structure site survey notes from photos of paper forms",
        author_id="E91",
        fields=dict(
            problem="Site survey notes are written on paper during the visit and typed up days later, sometimes not at all. We have about 900 surveys and the notes are not searchable, so installers repeat questions the surveyor already asked.",
            intended_purpose="Read a photo of the completed paper survey form and turn it into a structured record attached to the customer.",
            users_affected="The 5 field installation technicians and the support specialists who prepare installations. About 30 surveys per month.",
            deployment_context="Mobile, used on site. Internal only; the customer does not see the output.",
            data="Site survey notes, about 900, handwritten and unstructured. This is the weak point.",
            expected_benefit="Notes available the same day instead of days later, and searchable for the first time. Saves each technician about 2 hours a week.",
            effort="Four weeks, and it needs a redesigned form to be reliable.",
            human_oversight="The technician checks the extracted record on site before saving it.")),
    dict(
        id="UC-014", title="Keep website product facts in step with the data sheets",
        author_id="E15",
        fields=dict(
            problem="Product facts on the website drift from the current data sheets. 38 of our 190 pages are known to be out of date, which creates support tickets and embarrasses sales.",
            intended_purpose="Compare each website page against the current product data and list the specific sentences that no longer match.",
            users_affected="The content specialist and the marketing lead. Indirectly every website visitor and the 16 people in sales.",
            deployment_context="Internal checking tool. Its output is a list for a human to act on, not a direct edit to the website.",
            data="Website content, 190 pages, medium quality. Product catalogue and sensor specifications in this knowledge base.",
            expected_benefit="Clear the 38 out-of-date pages and keep the number under 10, which is the stated target.",
            effort="Two weeks for one developer.",
            human_oversight="Nothing is published automatically. The content specialist makes every edit.")),
    dict(
        id="UC-015", title="Translate help centre articles into German and Dutch",
        author_id="E86",
        fields=dict(
            problem="Content is translated between German, Dutch and English by hand. It is the main reason the help centre has only 85 articles and why 30 of them are out of date in at least one language.",
            intended_purpose="Produce a first-draft translation of each help centre article, which a native speaker in support then corrects before publication.",
            users_affected="The knowledge manager, the content specialist and the support specialists who speak each language. Customers read the published result.",
            deployment_context="Internal drafting. Output is published to the public help centre after human review.",
            data="The 85 help centre articles. No personal data.",
            expected_benefit="Cut translation effort by maybe 70% and let us keep all three languages current.",
            effort="One week for one developer.",
            human_oversight="A native-speaking support specialist reviews every translation before it is published.")),
    dict(
        id="UC-016", title="Check tender documents for questions we cannot answer",
        author_id="E59",
        fields=dict(
            problem="We sometimes commit to a tender and only discover halfway through that it asks for something we do not have, such as a certification or an integration. That wastes 2 to 4 days of work.",
            intended_purpose="Read a new tender document and list the requirements we cannot currently meet, with a pointer to what we would need.",
            users_affected="The 2 sales managers and 9 account executives. About 14 tenders per month.",
            deployment_context="Internal only, before a bid decision. Not customer-facing.",
            data="Tender responses, about 420 documents. Product specifications and the quality certification status.",
            expected_benefit="Avoid starting maybe 3 hopeless bids per month, which is roughly 9 days of effort.",
            effort="Three weeks for one developer with sales input.",
            human_oversight="The sales manager makes the bid decision. The tool only produces a list of concerns.")),
    dict(
        id="UC-017", title="Collect ISO 27001 audit evidence automatically",
        author_id="E111",
        fields=dict(
            problem="Audit evidence is collected by hand from six systems before every audit, about 10 person-days each time, and we are only 38% of the way through evidencing ISO 27001 controls.",
            intended_purpose="Pull the recurring evidence items from each system on a schedule and file them against the control they satisfy.",
            users_affected="The quality systems manager, the information security officer and the head of quality. 3 people directly.",
            deployment_context="Internal only. Reads Google Workspace, GitHub, AWS and the device management tool.",
            data="Access review exports, change records, device inventory. Each system produces a different format.",
            expected_benefit="Save about 20 person-days per year and make the ISO 27001 timeline realistic.",
            effort="Four weeks for one developer with the quality manager defining each control.",
            human_oversight="The quality systems manager signs off every piece of evidence before it is used in an audit.")),
    dict(
        id="UC-018", title="Predict reorder dates from stock movements",
        author_id="E103",
        fields=dict(
            problem="Reorder dates are estimated from experience. We had two stock-outs in 2026 and stock record accuracy is 87%, so the estimates are built on unreliable numbers.",
            intended_purpose="Forecast when each component will run out and suggest a reorder date, based on stock movements and open orders.",
            users_affected="The production planner, procurement specialist and head of operations. 4 people, covering about 180 purchase orders a month.",
            deployment_context="Internal only. Needs stock movement and purchase order data.",
            data="Stock movements in the inventory spreadsheet since 2023, low quality with gaps and manual errors. This is the blocker.",
            expected_benefit="Avoid stock-outs, which cost us delivery time on the 8-day order-to-ship figure we want to halve.",
            effort="Three weeks, but only after the inventory system replacement lands.",
            human_oversight="The planner approves every purchase order, as procurement policy requires.")),
    dict(
        id="UC-019", title="Draft case studies from the account history",
        author_id="E72",
        fields=dict(
            problem="Case studies take about 6 weeks, mostly waiting for input from sales and the customer. We publish 2 a quarter against a target of 5.",
            intended_purpose="Draft a case study from the account's own usage data and ticket history, which marketing and the customer then edit and approve.",
            users_affected="The product marketing manager and content specialist. Indirectly the 16 people in sales. Named customers appear in the output.",
            deployment_context="Internal drafting. The result is published publicly once marketing and the customer approve it.",
            data="Canopy usage per account, high quality. HubSpot deal notes, often missing. Key account records, which are confidential.",
            expected_benefit="Get from 2 to 5 case studies a quarter without more headcount.",
            effort="Three weeks for one developer.",
            human_oversight="Marketing edits every draft and the customer approves before anything is published.")),
    dict(
        id="UC-020", title="Summarise the week's tickets for product triage",
        author_id="E17",
        fields=dict(
            problem="The Wednesday support and product triage meeting starts with someone reading out the week's tickets. Nobody has time to spot that the same fault appeared 30 times, so repeat causes are fixed late.",
            intended_purpose="Group the week's tickets by underlying cause and summarise the top recurring issues for the triage meeting.",
            users_affected="The 5 people in the triage meeting. Summarises about 290 tickets per week.",
            deployment_context="Internal only, a weekly report. Not customer-facing.",
            data="Zendesk tickets, about 52,000 since 2022, categories inconsistent.",
            expected_benefit="Find repeat causes weeks earlier. Our own value is that a repeated ticket is a product problem, and we currently cannot see the repeats.",
            effort="Two weeks for one developer.",
            human_oversight="The triage meeting decides what to act on. The summary is input to people, not a decision.")),
]
