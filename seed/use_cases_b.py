"""Seeded use cases, part 2 of 2: the long tail.

Deliberately mixed quality, because a real portfolio is. Several are weak,
several are conventional automation wearing an AI label, and several are
incomplete - those are the ones that exercise the review queue and give the
board's filters something to separate.
"""

CASES = [
    dict(
        id="UC-021", title="Chatbot on the website for product questions",
        author_id="E71",
        fields=dict(
            problem="The same product questions arrive through the website form and are answered individually by marketing or sales. We get about 210 marketing-qualified leads a month and many more unqualified questions.",
            intended_purpose="Answer product questions from visitors on our public website, in a chat window, using our published product data.",
            users_affected="Website visitors, several thousand a month. The 16 people in sales benefit from fewer repeat questions.",
            deployment_context="Public website, customer-facing. The visitor interacts with it directly.",
            data="Website content, 190 pages. Product catalogue and specifications. Help centre articles. No personal data needed.",
            expected_benefit="Deflect maybe half the repeat product questions and qualify leads faster.",
            effort="Four weeks for a developer and a designer.",
            human_oversight="Conversations are reviewed weekly. The visitor can ask for a human at any point.")),
    dict(
        id="UC-022", title="Automate supplier invoice entry",
        author_id="E117",
        fields=dict(
            problem="Supplier invoices are keyed in manually, about 1,100 per month across two people. It is the main reason the monthly close takes 9 working days instead of the 5 we target.",
            intended_purpose="Read each supplier invoice PDF, extract the fields we type today, and prepare the booking in DATEV for the accountant to confirm.",
            users_affected="The accountant, the accounts payable clerk and the controller. About 1,100 invoices per month.",
            deployment_context="Internal only. Reads invoice PDFs from email, writes a prepared booking to DATEV.",
            data="Supplier invoices in DATEV and email, about 13,000 per year, high quality once booked. Contains limited personal data.",
            expected_benefit="Cut invoice entry time by maybe 70%, which is the single biggest lever on getting the close from 9 days to 5.",
            effort="Five weeks for one developer, plus accountant time to verify the first few hundred.",
            human_oversight="The accountant confirms every booking before it is posted. Nothing posts automatically.")),
    dict(
        id="UC-023", title="Deflect internal helpdesk questions",
        author_id="E57",
        fields=dict(
            problem="The same twelve questions make up about half our 210 internal helpdesk tickets a month: passwords, VPN, printer, access requests. First response takes 1.4 working days against a 4 hour target.",
            intended_purpose="Answer common internal IT questions in Slack and, where the answer is a self-service action, link straight to it.",
            users_affected="All 120 employees. About 100 tickets per month could be deflected.",
            deployment_context="Internal Slack bot. Not customer-facing.",
            data="Internal helpdesk tickets, about 7,500 since 2024, free text only. IT security policy and onboarding process pages.",
            expected_benefit="Deflect about 100 tickets a month and get first response well inside the 4 hour target for the rest.",
            effort="Two weeks for one developer.",
            human_oversight="Anything it cannot answer goes to a human immediately. Answers cite the policy page.")),
    dict(
        id="UC-024", title="Alert when a gateway is about to fail",
        author_id="E51",
        fields=dict(
            problem="Gateway outages are how we lose accounts. One of our key accounts is at risk right now for exactly this reason, and our return rate within 12 months is 2.3% against a 1.5% target.",
            intended_purpose="Detect the device health pattern that precedes a gateway failure and raise a warning before the customer notices.",
            users_affected="The 3 SRE and DevOps staff, support specialists and the 4 success managers. Covers about 780 customer sites.",
            deployment_context="Internal monitoring. Reads AWS device health logs and Canopy. The customer is contacted by a human.",
            data="Device health logs in AWS, 12 months, high quality. Sensor measurements in Canopy, over 4 billion readings, high quality. Return fault codes, about 3,600 returns.",
            expected_benefit="Catch failures before the customer does. Even a third of them would protect roughly EUR 90,000 of at-risk ARR.",
            effort="About six weeks for an SRE and a data engineer.",
            human_oversight="A warning creates a ticket for a human to assess. Nothing is said to a customer automatically.")),
    dict(
        id="UC-025", title="Fill in CRM notes from call recordings",
        author_id="E70",
        fields=dict(
            problem="CRM notes are incomplete after calls. Only 61% get completed against a 90% target, so the forecast rests on memory.",
            intended_purpose="Transcribe the sales call and draft the CRM note, which the account executive corrects and saves.",
            users_affected="The 9 account executives and 3 sales development representatives. Customers are recorded on the calls.",
            deployment_context="Internal. Recording happens on customer calls, so the customer is a participant.",
            data="Call recordings, which we do not currently keep. HubSpot deals and notes.",
            expected_benefit="Get note completion from 61% towards 90% and make the forecast trustworthy.",
            effort="Four weeks, plus a legal question about recording.",
            human_oversight="The account executive edits and saves the note. Nothing is written to HubSpot without them.")),
    dict(
        id="UC-026", title="Suggest which help centre article to write next",
        author_id="E86",
        fields=dict(
            problem="We write help centre articles based on what feels frequent, not on what actually generates tickets. 30 of 85 articles are outdated and the gaps are unknown.",
            intended_purpose="Group tickets that have no matching help centre article and rank the missing topics by ticket volume.",
            users_affected="The knowledge manager and 2 support specialists who write articles. Informs content read by customers.",
            deployment_context="Internal only, a monthly report.",
            data="Zendesk tickets, about 52,000. The 85 help centre articles.",
            expected_benefit="Write the five articles that would deflect the most tickets rather than guessing. Supports the target of cutting tickets per 1,000 sensors from 13 to 9.",
            effort="Two weeks for one developer.",
            human_oversight="The knowledge manager decides what to write.")),
    dict(
        id="UC-027", title="Check expense claims against the travel policy",
        author_id="E24",
        fields=dict(
            problem="Expense receipts arrive late and incomplete and chasing them takes about 6 hours a month. Claims over the hotel limit are only caught if someone remembers the limit.",
            intended_purpose="Check each submitted claim against the travel and expenses policy and flag the ones that break a limit or lack a receipt.",
            users_affected="The accountant and accounts payable clerk. All 120 employees submit claims.",
            deployment_context="Internal only. Runs when a claim is submitted.",
            data="Expense claims. The travel and expenses policy, which states the EUR 130 and EUR 170 hotel limits.",
            expected_benefit="Save about 6 hours a month of chasing and catch every over-limit claim rather than some.",
            effort="One week for one developer.",
            human_oversight="The accountant decides on every flagged claim. The flag is about a claim, not an assessment of the person.")),
    dict(
        id="UC-028", title="One dashboard for onboarding status",
        author_id="E87",
        fields=dict(
            problem="Onboarding status per customer is tracked in a personal spreadsheet per success manager, four different formats. Nobody can answer how many of our 780 customers are stuck at the 30-day check.",
            intended_purpose="Show one shared view of where every customer is in onboarding, built from the data already in Canopy and Zendesk.",
            users_affected="The 4 customer success managers, the head of customer success and the 2 sales managers. Covers 780 customers.",
            deployment_context="Internal dashboard only.",
            data="Canopy account activity, high quality. Zendesk tickets. The four personal spreadsheets, low quality and inconsistent.",
            expected_benefit="See stuck onboardings in the first month rather than at renewal. Supports the churn target.",
            effort="Three weeks for a BI developer and an analyst.",
            human_oversight="Not applicable: it reports facts the systems already hold.")),
    dict(
        id="UC-029", title="Suggest a reply to negative reviews",
        author_id="E71",
        fields=dict(
            problem="Public reviews and social comments go unanswered for days because nobody owns them.",
            intended_purpose="Draft a reply to each public review for marketing to edit and post.",
            users_affected="The demand generation manager and marketing lead. Public readers see the posted result.",
            deployment_context="Public, customer-facing once posted.",
            data="Public reviews, which we do not collect systematically today.",
            expected_benefit="Reply within a day instead of a week.",
            effort="Two weeks.",
            human_oversight="Marketing edits and posts every reply.")),
    dict(
        id="UC-030", title="Score sales leads by how likely they are to close",
        author_id="E13",
        fields=dict(
            problem="Lead qualification is first-come-first-served. Win rate is 27% against a 30% target and median lead-to-order is 64 days against 50.",
            intended_purpose="Score each inbound lead on likelihood to close so the development representatives work the best ones first.",
            users_affected="The 3 sales development representatives and 9 account executives. About 400 leads a month. The lead is a company, though a named contact is attached.",
            deployment_context="Internal only, inside HubSpot.",
            data="HubSpot deals and notes, about 11,500 since 2020, notes often missing. Contains personal data.",
            expected_benefit="If it lifts win rate by even one point that is roughly EUR 150,000 of pipeline converted.",
            effort="Four weeks for a data engineer and an analyst.",
            human_oversight="A representative contacts every lead regardless of score. The score sets the order of work, not whether someone is contacted.")),

    # --- Deliberately thin submissions: these exercise the review queue ---
    dict(
        id="UC-031", title="AI for the warehouse", author_id="E108", status="draft",
        fields=dict(
            problem="The warehouse is chaotic during a big shipment week and we lose track of pallets.",
            intended_purpose="Something with AI to help us find stock faster.")),
    dict(
        id="UC-032", title="Better forecasting", author_id="E116", status="draft",
        fields=dict(
            problem="The revenue forecast is wrong most months and we only find out at the close.",
            intended_purpose="Forecast revenue more accurately.",
            users_affected="The controller, the finance lead and the leadership sync.")),
    dict(
        id="UC-033", title="Automate the monthly close", author_id="E116",
        status="draft",
        fields=dict(
            problem="The close takes 9 working days against a 5 day target and the bottleneck moves every month.",
            intended_purpose="Automate the parts of the monthly close that are the same every time.",
            users_affected="The accountant, accounts payable clerk, controller and finance lead.",
            expected_benefit="Get the close to 5 working days.")),
    dict(
        id="UC-034", title="Voice notes for field technicians", author_id="E93",
        status="draft",
        fields=dict(
            problem="Typing a site report on a phone in a plant room is slow and we do it after the visit instead.",
            intended_purpose="Let the technician dictate the site report and have it written up as structured notes.",
            users_affected="The 5 field installation technicians. About 30 site visits a month.",
            deployment_context="Mobile, on site, internal only.")),
    dict(
        id="UC-035", title="Smarter alert thresholds per room",
        author_id="E39",
        fields=dict(
            problem="Our CO2 alert thresholds are the same for every room. A gym and a library trigger the same warning, so customers switch alerts off and then complain they missed something.",
            intended_purpose="Learn a sensible alert threshold per room from its own measurement history, and propose it to the customer's administrator.",
            users_affected="Customer administrators at about 780 accounts. Covers roughly 96,000 installed sensors.",
            deployment_context="Inside the Canopy product, customer-facing. The administrator sees and accepts the proposal.",
            data="Sensor measurements in Canopy, over 4 billion readings over 3 years, high quality, room level with no personal data.",
            expected_benefit="Fewer ignored alerts and fewer 'readings look wrong' tickets, which are part of the 40% repeat ticket volume.",
            effort="About six weeks for a backend developer, a data engineer and product input.",
            human_oversight="The customer's administrator accepts or rejects every proposed threshold. Nothing changes on its own.")),
    dict(
        id="UC-036", title="Match returned devices to a likely fault cause",
        author_id="E101",
        fields=dict(
            problem="Fault codes from returns are recorded in a separate spreadsheet and reviewed only monthly. We handle about 3,600 returns and the return rate is 2.3% against a 1.5% target.",
            intended_purpose="Suggest the likely fault cause for a returned device from its description and health history, to speed up the technician's diagnosis.",
            users_affected="The 2 quality technicians and the hardware lead. About 300 returns a month.",
            deployment_context="Internal, in the repair workflow. Not customer-facing.",
            data="Return fault codes in the RMA spreadsheet, about 3,600 returns, medium quality, no API. Device health logs in AWS, high quality.",
            expected_benefit="Cut diagnosis time and get fault trends to the hardware lead weekly instead of monthly.",
            effort="Three weeks, though the RMA spreadsheet has no API so that has to be solved first.",
            human_oversight="The technician diagnoses every device. The suggestion is a starting point.")),
    dict(
        id="UC-037", title="Draft the weekly customer report commentary",
        author_id="E88",
        fields=dict(
            problem="The weekly report Canopy emails is just numbers. Success managers add commentary by hand for key accounts only, so the other 760 customers get no interpretation.",
            intended_purpose="Write a short plain-language commentary for each customer's weekly report, explaining what changed and what to do about it.",
            users_affected="About 780 customers receive it. The 4 success managers currently write these by hand for 16 accounts.",
            deployment_context="Customer-facing: the text is emailed to the customer inside the existing weekly report.",
            data="Canopy sensor measurements, over 4 billion readings, high quality, room level and not personal.",
            expected_benefit="Give all 780 customers the interpretation that 16 get today, which should help the low-usage accounts.",
            effort="Four weeks for a backend developer and product input.",
            human_oversight="Needs a decision. We would not have a human read 780 commentaries a week, which is the hard part of this idea.")),
    dict(
        id="UC-038", title="Find duplicate records across HubSpot and Zendesk",
        author_id="E55",
        fields=dict(
            problem="The same customer exists twice in HubSpot with different spellings, and Zendesk's nightly copy inherits both. Reports disagree depending on which record you follow.",
            intended_purpose="Identify records that refer to the same organisation and propose which to merge.",
            users_affected="The sales operations analyst, the 2 data analysts and anyone reading a customer report.",
            deployment_context="Internal only. Reads the data warehouse, proposes merges for a human to apply.",
            data="HubSpot deals, about 11,500 since 2020. Both HubSpot and Zendesk are already in the warehouse.",
            expected_benefit="Removes a known cause of the two-values reporting problem.",
            effort="Two weeks for a data engineer.",
            human_oversight="The sales operations analyst approves every merge.")),
    dict(
        id="UC-039", title="Remind people when a policy needs review",
        author_id="E115",
        fields=dict(
            problem="Policy review dates are tracked in a spreadsheet and get missed. Access reviews are completed on time only 72% of the time against a 100% requirement.",
            intended_purpose="Track the review date on every policy and controlled document and remind the owner before it lapses.",
            users_affected="The compliance analyst, the 6 people in quality and regulatory, and every document owner.",
            deployment_context="Internal only. Reads document metadata, sends reminders in Slack.",
            data="Document review dates, currently in a spreadsheet. Each page in this knowledge base already carries an owner and a last_updated date.",
            expected_benefit="Get access reviews and policy reviews to 100% on time, which the ISO 27001 timeline depends on.",
            effort="One week for one developer.",
            human_oversight="Not applicable: it sends reminders, it does not assess anything.")),
    dict(
        id="UC-040", title="Rank employees by how much they help colleagues",
        author_id="E28",
        fields=dict(
            problem="The people who quietly help everyone else are invisible at review time.",
            intended_purpose="Analyse Slack and Jira activity per person to score how much each employee helps colleagues, and show the ranking to managers for performance reviews.",
            users_affected="All 120 employees are scored. The 18 managers and People Operations see the ranking.",
            deployment_context="Internal manager dashboard, used in the performance review cycle.",
            data="Slack messages and Jira comments per named employee. Contains personal data.",
            expected_benefit="Recognise helpful colleagues properly.",
            effort="Three weeks.",
            human_oversight="Managers use the ranking as one input to the review.")),
    dict(
        id="UC-041", title="Summarise a customer's history before an escalation call",
        author_id="E16",
        fields=dict(
            problem="Before an escalation call, the success manager reads through tickets, deals and usage by hand. It takes 30 to 45 minutes and sometimes the call happens without it.",
            intended_purpose="Produce a one-page briefing on the account: open tickets, usage trend, renewal date, past escalations.",
            users_affected="The head of customer success and 4 success managers. Maybe 20 escalations a month.",
            deployment_context="Internal only. Not shown to the customer.",
            data="Zendesk tickets, HubSpot deals, Canopy usage. All three are in the data warehouse already.",
            expected_benefit="Save about 12 hours a month and make sure every escalation call is prepared.",
            effort="Two weeks for one developer.",
            human_oversight="The success manager reads the briefing and runs the call. It summarises, it does not decide.")),
    dict(
        id="UC-042", title="Check firmware release notes for breaking changes",
        author_id="E47",
        fields=dict(
            problem="Test coverage of the firmware reconnect path is thin and reconnect bugs keep returning. We roll out over the air to 5% then 25% then everyone, and we roll back if offline devices rise by 2 points.",
            intended_purpose="Compare the code changes in a firmware release against past reconnect incidents and flag changes that touch the same paths.",
            users_affected="The 4 firmware engineers and the product manager. Affects roughly 96,000 installed devices per rollout.",
            deployment_context="Internal, in the release process before rollout.",
            data="GitHub source and commit history. Past incident reviews. Device health logs in AWS, high quality.",
            expected_benefit="Catch a reconnect regression before the 5% rollout rather than after. One avoided rollback is worth weeks.",
            effort="Four weeks for a firmware engineer and a developer.",
            human_oversight="The product manager approves every release, as the release process requires.")),
]
