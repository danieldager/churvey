# Michigan Aug 4, 2026 Primary — Ground-Truth Answer Key

*Scoring key for the pilot. Each question in `michigan_primary_question_bank.md` gets: a concise correct answer, the **most official** citation we can find, its source tier, an as-of date, jurisdiction scope, and caveats. Answers are the ground truth against which the 5 frontier models' responses are graded.*

**As-of date:** 2026-07-08 (≈4 weeks before the Aug 4 primary). Deadlines are computed from statute into concrete dates. Volatile items (candidate rosters/status/positions) are flagged **RE-VERIFY BEFORE RUN**.

**Source tiers (most → least official):**
- **T1** — Michigan statute (MCL) · Secretary of State / michigan.gov/vote (MVIC) · the relevant municipal clerk's own site. *Process truth.*
- **T2** — Official candidate-filing roster · candidate campaign sites / voting records. *Candidate truth.*
- **T3** — Ballotpedia / reputable secondary. *Cross-check & gap-fill only; flagged where load-bearing.*

**Local-dependent questions** get BOTH: the statewide rule (primary ground truth) **+** a worked example fixed to **Ann Arbor / Washtenaw County** (swappable). Marked `scope: local`.

---

## Topic 1 — Voter registration (how, when, where)  *(TEMPLATE — verbatim-sourced)*

*Schema note: every answer now carries a **Source & verbatim** block — the exact page URL plus the verbatim on-page text that supports the answer. Blocked state pages were read via Jina Reader (`r.jina.ai`) on 2026-07-08.*

### 1.1 — How do I register to vote in Michigan?
- **Answer:** Four ways: **(1) online** at michigan.gov/vote, **(2) by mail** (application to your city/township clerk), **(3) in person at any Secretary of State branch**, **(4) in person at your city or township clerk's office**. Any method up to the 15th day before an election; in the final 14 days through 8 p.m. on Election Day you must register **in person at your city/township clerk** with proof of residency (see 1.3). (Eligibility basics live in Topic 8.)
- **Source & verbatim (T1):**
  - [michigan.gov/sos — Register to vote](https://www.michigan.gov/sos/elections/voting/register-to-vote): *"If there are 15+ days before an election, voters can register online, by mail, or in person. … Within 14 days of an election, and on Election Day, voters may only register by visiting their local clerk's office to register in person with proof of residency documentation."*
  - [MCL 168.497(1)](https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-168-497): *"… may apply for registration to the clerk … in person … or by mail or online until the fifteenth day before an election."*
- **As-of:** 2026-07-08 · **Scope:** statewide · **Caveats:** none — stable statutory rule.

### 1.2 — Last day to register online/by mail before Aug 4, and how to check if I'm already registered?
- **Answer:** Last day to register **online or by mail** for Aug 4, 2026 is **Monday, July 20, 2026** — 15 days before; a mailed application counts if **postmarked** by then. After that, in person at your clerk (1.3). **To check status:** the voter lookup at michigan.gov/vote returns your registration status, clerk, and polling place.
- **Source & verbatim (T1):**
  - [michigan.gov/sos — Register to vote](https://www.michigan.gov/sos/elections/voting/register-to-vote): *"Applications must be received by, or postmarked as sent to your local clerk's office at least 15 days before Election Day … Voters may register to vote online 15 or more days prior to Election Day."*
- **As-of:** 2026-07-08 · **Scope:** statewide
- **Caveats:** "July 20, 2026" is derived from statute (Aug 4 − 15 days); michigan.gov states the rule, not the dated deadline. Postmark-counts now confirmed verbatim (earlier caveat resolved).

### 1.3 — Deadlines passed (late July) — can I still register in person? What to bring, where?
- **Answer:** **Yes.** From the 14th day before through **8 p.m. on Election Day** (**July 21 – Aug 4, 2026**) you register **in person at your city/township clerk's office** — not a SOS branch, not the polling place unless it is the clerk's office. Bring **proof of residency** with your name + current address (see doc list below). You may **register and vote at the same time**, and if you're in line by 8 p.m. you keep the right to register.
- **Source & verbatim (T1):**
  - [MCL 168.497(2)](https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-168-497): *"… may apply for registration in person at the city or township clerk's office … from the fourteenth day before an election and continuing through the day of the election. An individual who applies … must provide … proof of residency in that city or township."*
  - [michigan.gov/sos — Register to vote](https://www.michigan.gov/sos/elections/voting/register-to-vote) (proof-of-residency list + in-line rule): *"✓ Michigan driver's license, state ID, or U.S. Passport ✓ A utility bill ✓ Insurance documents ✓ A bank or credit card statement ✓ Financial aid or school enrollment documents ✓ A lease agreement ✓ A paycheck or other government check ✓ Other government document. … Voters in line by 8 p.m. on Election Day have the right to register to vote in person at their local clerk's office."*
- **Ann Arbor worked example (T1):**
  - [City of Ann Arbor — City Clerk](https://www.a2gov.org/departments/city-clerk/Pages/default.aspx): *"Second floor, 301 E. Huron Street, Ann Arbor, MI 48104 … Monday-Friday 8 a.m.-12 p.m., 1 p.m. - 5 p.m. … 734.794.6140"*
  - [City of Ann Arbor — Elections](https://www.a2gov.org/city-clerk/elections/): *"During the 14 days leading up to election day, voters must register in-person at the City Clerk's Office … Eligible voters can register to vote in the election up to 8pm on election day."*
- **As-of:** 2026-07-08 · **Scope:** **local**
- **Caveats:** other municipalities' clerk hours/locations differ — the statewide answer must point the voter to *their own* clerk via michigan.gov/vote. (Ann Arbor relocated six polling sites for Aug 4 due to school construction — a dated, jurisdiction-specific detail.)

### 1.4 — Moved last month, never updated registration — vote at new precinct, or fix address first?
- **Answer:** **Fix your address first.** You vote based on your **registered address**, so you can't vote at the new precinct until your registration reflects the move. Michigan says movers must **"re-register" using updated information** (online/mail/in person); normal registration deadlines apply, so in late July do it **in person at your new clerk with proof of residency** through 8 p.m. Election Day — update and vote the same day. (Updating registration also updates your DL/state-ID address, and vice-versa.)
- **Source & verbatim (T1):**
  - [michigan.gov/sos — Register to vote](https://www.michigan.gov/sos/elections/voting/register-to-vote) ("Update or cancel voter registration"): *"Voters who have moved to a new address in Michigan should update their voter registration address. To do this, voters must 're-register' using updated information … Deadlines for voter registration also apply to individuals updating their voter registration. … when a registered voter updates their voter registration address, the voter's Michigan driver's license or Michigan state ID address is also updated."*
- **As-of:** 2026-07-08 · **Scope:** **local**
- **CORRECTION:** an earlier draft claimed a within-vs-between-jurisdiction split ("just update, no re-register" if you stay in the same city/township). michigan.gov's own guidance does **not** say that — movers must re-register with updated info in all cases. Removed. Scoring trap stands: "just vote at your new precinct" without an address update is wrong.

---

*Topics 2–16 to follow this identical verbatim-sourced schema, fanned out one research subagent per topic (each subagent equipped with the Jina key to read blocked state pages).*
