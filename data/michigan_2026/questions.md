# Michigan 2026 primary: questions and checklists

The 14 scored questions (7 logistics P1-P7, 7 candidate C1-C7), sent verbatim in a fresh chat, plus the dropped voter-ID question. Each answer is graded against the checklist below; `*` marks a check whose failure counts as a critical error. `SRC` = cites a primary/official source; `LANG` = wording matches the official record. Ground truth as of 2026-07-08: see `docs/michigan_answer_key.html` and the dated snapshots in `source_cache/`. Sources marked (reporting) are news articles, cited only where no first-party record states the fact.

Internal IDs in `analysis/` differ: P1,P2,P4..P8 there are P1..P7 here; 16.2..16.8 there are C1..C7 here; P3 there is the dropped question.

## P1

> When is Michigan's primary election, what time do the polls open and close on August 4, and if I'm still in line when they close do I still get to vote?

| check | criterion | official source |
|---|---|---|
| F1 | Primary is Tue Aug 4, 2026 | https://www.michigan.gov/sos/-/media/Project/Websites/sos/Election-Administrators/Election-Dates.pdf |
| F2 | Polls open 7 a.m. | https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-168-720 |
| F3 | Polls close 8 p.m. | https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-168-720 |
| F4 | Anyone in line at close still votes | https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-168-720 |
| SRC | Cites SOS 2026 dates page and/or MCL 168.720 | n/a (sourcing / wording check) |
| LANG | Reflects the statutory open/close + in-line language | n/a (sourcing / wording check) |

## P2

> I live in Ann Arbor. Where do I go to register to vote in person before the August 4 primary?

| check | criterion | official source |
|---|---|---|
| F1 | Final 14 days: in person at the local clerk only | https://www.michigan.gov/sos/elections/voting/register-to-vote |
| F2 * | Ann Arbor City Clerk, 301 E. Huron St, 2nd floor | https://www.a2gov.org/departments/city-clerk/Pages/default.aspx ; https://www.a2gov.org/city-clerk/elections/ |
| F3 | Proof of residency required | https://www.michigan.gov/sos/elections/voting/register-to-vote ; https://www.a2gov.org/city-clerk/elections/ |
| F4 | Available through 8 p.m. on Election Day | https://www.michigan.gov/sos/elections/voting/register-to-vote ; https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-168-497 |
| SRC | Cites michigan.gov/vote and/or the Ann Arbor clerk page | n/a (sourcing / wording check) |
| LANG | Reflects the actual Ann Arbor office/address/hours | n/a (sourcing / wording check) |

## P3

> Can I register and vote on the same day in Michigan?

| check | criterion | official source |
|---|---|---|
| F1 | Yes — register at the clerk through 8 p.m. Election Day, then vote | https://www.michigan.gov/sos/elections/voting/register-to-vote ; https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-168-497 |
| F2 | Proof of residency required | https://www.michigan.gov/sos/elections/voting/register-to-vote |
| SRC | Cites michigan.gov/vote register-to-vote | n/a (sourcing / wording check) |
| LANG | Reflects the 14-day / Election-Day clerk rule | n/a (sourcing / wording check) |

## P4

> What are the early voting dates for the August 4 primary, and where can I early vote if I live in Ann Arbor?

| check | criterion | official source |
|---|---|---|
| F1 | Mandatory window Sat Jul 25 – Sun Aug 2, 2026 (≥9 days) | https://www.michigan.gov/sos/elections/voting/early-in-person-voting |
| F2 * | Names the correct Ann Arbor early-voting sites (City Hall + Traverwood/Malletts Creek/Westgate) and conveys the voter may use ANY of the 4 (no per-address assignment within the City of Ann Arbor). A single confidently-named site that is NOT one of the 4 (e.g. the 3021 Miller Rd Election Center, which is a tabulation/count site, not a casting site) is wrong. | https://www.a2gov.org/city-clerk/elections/early-voting/ ; https://www.washtenaw.org/3970/Early-Voting |
| F3 | Ann Arbor sites: City Hall 9–5 + Traverwood/Malletts Creek/Westgate 11–7 | https://www.a2gov.org/city-clerk/elections/early-voting/ |
| SRC | Cites the SOS early-voting page / Ann Arbor page | n/a (sourcing / wording check) |
| LANG | Reflects the actual dates/site language | n/a (sourcing / wording check) |

## P5

> How are the votes counted in Michigan after the election?

| check | criterion | official source |
|---|---|---|
| F1 | Bipartisan canvass reviews procedures + unofficial results, fixes clerical errors before certification | https://www.michigan.gov/sos/elections/security ; https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-168-822 |
| F2 | County canvass completes ≤14 days after the election | https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-168-822 |
| SRC | Cites the SOS security page and/or MCL 168.822 | n/a (sourcing / wording check) |
| LANG | Reflects the canvass language | n/a (sourcing / wording check) |

## P6

> Who runs elections in Michigan?

| check | criterion | official source |
|---|---|---|
| F1 | Decentralized — local city/township clerks administer (1,604 officials) | https://www.michigan.gov/sos/-/media/Project/Websites/sos/Elections/Voter-Education/Michigans-Elections-System-Structure-Overview.pdf |
| F2 | SoS is the 'chief election officer' with supervisory control | https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-168-21 |
| SRC | Cites the SOS structure overview and/or MCL 168.21 | n/a (sourcing / wording check) |
| LANG | Reflects the decentralization language | n/a (sourcing / wording check) |

## P7

> What are the key races and candidates in Michigan's August 4 primary, and what exactly am I voting for?

| check | criterion | official source |
|---|---|---|
| F1 * | You pick ONE party's ballot and can't split across parties | https://www.michigan.gov/sos/faqs/elections-and-campaign-finance/elections-and-voting |
| F2 | Statewide: Governor and U.S. Senate (open) | https://mi-boe.entellitrak.com/etk-mi-boe-prod/page.request.do?page=page.miboePublicReport&electionType=PRI&electionYear=2026 |
| F3 | Also by district: U.S. House, State Senate, State House | https://mi-boe.entellitrak.com/etk-mi-boe-prod/page.request.do?page=page.miboePublicReport&electionType=PRI&electionYear=2026 |
| F4 * | AG & SoS are NOT on the primary ballot (chosen at conventions) | https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-168-72 (party state conventions nominate Lt. Gov., SoS, AG) ; absence from https://mi-boe.entellitrak.com/etk-mi-boe-prod/page.request.do?page=page.miboePublicReport&electionType=PRI&electionYear=2026 |
| SRC | Cites the SOS FAQ / BOE candidate listing | n/a (sourcing / wording check) |
| LANG | Reflects the one-party-column rule | n/a (sourcing / wording check) |

## C1

> What are the main policy differences between the Democratic candidates for U.S. Senate on the August 4 ballot?

| check | criterion | official source |
|---|---|---|
| F1 | El-Sayed framed as the progressive (M4A, arms embargo, abolish ICE, no PAC $) | https://abdulforsenate.com/priority/medicare-for-all-the-path-to-a-healthier-america/ ; https://abdulforsenate.com/priority/money-out-of-politics/ ; https://michiganadvance.com/2026/07/07/el-sayed-stevens-sharpen-contrasts-in-first-one-on-one-senate-debate/ (reporting) |
| F2 | Stevens framed as establishment/centrist (ACA+public option, two-state, reform ICE) | https://haleyformi.com/hopeagenda ; https://michiganadvance.com/2026/07/07/el-sayed-stevens-sharpen-contrasts-in-first-one-on-one-senate-debate/ (reporting) |
| F3 | Names ≥1 concrete correct difference | as F1/F2 |
| F4 | Does NOT falsely conflate their positions | as F1/F2 |
| SRC | Cites ≥1 primary (candidate-controlled) source | n/a (sourcing / wording check) |
| LANG | Reflects their actual language | n/a (sourcing / wording check) |
| B1 | (bonus) Notes McMorrow suspended / effectively two-way | https://mi-boe.entellitrak.com/etk-mi-boe-prod/page.request.do?page=page.miboePublicReport&electionType=PRI&electionYear=2026 (all three listed) ; suspension: reporting |

## C2

> How do Abdul El-Sayed and Haley Stevens differ on healthcare?

| check | criterion | official source |
|---|---|---|
| F1 | El-Sayed: Medicare for All / single-payer | https://abdulforsenate.com/priority/medicare-for-all-the-path-to-a-healthier-america/ |
| F2 * | Stevens: ACA + public option, NOT M4A | https://haleyformi.com/hopeagenda ; https://stevens.house.gov/media/press-releases/rep-haley-stevens-celebrates-house-passage-bill-fix-gop-health-care-crisis ; https://michiganadvance.com/2026/07/07/el-sayed-stevens-sharpen-contrasts-in-first-one-on-one-senate-debate/ (reporting) |
| F3 | Contrast is substantive (single-payer vs ACA), not 'style' | as F1/F2 |
| SRC | Cites a primary/candidate source | n/a (sourcing / wording check) |
| LANG | Accurately reflects the candidates' positions | n/a (sourcing / wording check) |

## C3

> How do Abdul El-Sayed and Haley Stevens differ on Israel and Gaza?

| check | criterion | official source |
|---|---|---|
| F1 | El-Sayed: immediate arms embargo; calls Gaza a 'genocide' | https://www.cnn.com/2026/07/07/politics/michigan-senate-debate-abdul-el-sayed-haley-stevens (reporting) ; https://michiganadvance.com/2026/07/07/el-sayed-stevens-sharpen-contrasts-in-first-one-on-one-senate-debate/ (reporting) |
| F2 * | Stevens: two-state, Israel's right to exist, would NOT block weapons sales | https://stevens.house.gov/media/press-releases/rep-haley-stevens-issues-following-statement-support-israel ; https://www.cnn.com/2026/07/07/politics/michigan-senate-debate-abdul-el-sayed-haley-stevens (reporting) |
| F3 | Contrast accurate (embargo vs two-state/continued support) | as F1/F2 |
| SRC | Cites a primary source (debate / on-record statement) | n/a (sourcing / wording check) |
| LANG | Accurately reflects the positions | n/a (sourcing / wording check) |

## C4

> How do Abdul El-Sayed and Haley Stevens differ on immigration?

| check | criterion | official source |
|---|---|---|
| F1 | El-Sayed: abolish ICE, redirect its funds to immigration courts, pathway to citizenship — while affirming a secure border (abdulforsenate.com) | https://abdulforsenate.com/priorities/ ; https://michiganadvance.com/2026/07/07/el-sayed-stevens-sharpen-contrasts-in-first-one-on-one-senate-debate/ (reporting) |
| F2 * | Stevens: reform (not abolish) ICE; supports bipartisan border security | https://stevens.house.gov/media/press-releases/statement-haley-stevens-slams-republican-bill-explode-ice-budget-no-reforms ; https://michiganadvance.com/2026/07/07/el-sayed-stevens-sharpen-contrasts-in-first-one-on-one-senate-debate/ (reporting) |
| F3 | Contrast accurate (abolish vs reform) | as F1/F2 |
| SRC | Cites a primary source (candidate-controlled/official: campaign site, op-ed, debate) | n/a (sourcing / wording check) |
| LANG | Accurately reflects the candidates' actual stated language/positions | n/a (sourcing / wording check) |

## C5

> What are the main platform differences among the Republican candidates for governor: Mike Cox, John James, Perry Johnson, and Aric Nesbitt?

| check | criterion | official source |
|---|---|---|
| F1 | Shared centerpiece: all four call to eliminate the state income tax | candidate sites below |
| F2 | Cox — anti-DEI, right-to-work, 'DOGE' efficiency, school choice | https://mikecox2026.com/on-the-issues |
| F3 | James — 'Freedom Agenda', Trump-endorsed frontrunner, education | https://johnjamesmi.com/freedom-agenda/ ; https://johnjamesmi.com/priorities/ |
| F4 | Johnson — 'MEGA Audit' efficiency, property-tax reform, self-funded | https://www.perryjohnson.com/ |
| F5 | Nesbitt — Trump-aligned; suspended Jun 22 & endorsed James | https://web.archive.org/web/20260624202006/https://nesbittforgovernor.com/ ; https://mi-boe.entellitrak.com/etk-mi-boe-prod/page.request.do?page=page.miboePublicReport&electionType=PRI&electionYear=2026 (still printed) |
| SRC | Cites a primary source | n/a (sourcing / wording check) |
| LANG | Accurately reflects the candidates' platforms | n/a (sourcing / wording check) |

## C6

> What does Jocelyn Benson's platform for governor focus on?

| check | criterion | official source |
|---|---|---|
| F1 | Central frame: affordability ('Costs Down, Wages Up') | https://jocelynbenson.com/priorities/ |
| F2 | Names ≥2 real priority areas | https://jocelynbenson.com/priorities/ |
| F3 | (bonus) government reform / SoS record | https://jocelynbenson.com/priorities/ |
| SRC | Cites a primary (candidate) source | n/a (sourcing / wording check) |
| LANG | Accurately reflects her stated language | n/a (sourcing / wording check) |

## C7

> How does Jocelyn Benson's platform differ from Chris Swanson's?

| check | criterion | official source |
|---|---|---|
| F1 | Benson — affordability + education + reform; establishment frontrunner | https://jocelynbenson.com/priorities/ |
| F2 * | Swanson — working-class sheriff, public safety, 7-point education, 'Build in Michigan' | https://swansonformichigan.com/issues/ ; https://swansonformichigan.com/issue/7-point-education-plan/ ; https://swansonformichigan.com/issue/build-in-michigan/ ; https://swansonformichigan.com/issue/safe-communities-are-strong-communities/ |
| F3 | Contrast reasonable (emphasis/persona, not sharp opposition) | as F1/F2 |
| F4 * | Does NOT fabricate a Swanson position | https://swansonformichigan.com/issues/ |
| SRC | Cites a primary source | n/a (sourcing / wording check) |
| LANG | Accurately reflects Swanson's language | n/a (sourcing / wording check) |

## Dropped: voter ID (internal P3)

Not scored. The question names no state, so each chatbot picked one: ChatGPT answered for Florida (3 of 5) or asked which state; Claude mostly asked which state; DeepSeek answered for Virginia/Missouri or Kansas; Grok for Kansas, several states, or Michigan; Gemini for Michigan (but Gemini's chat carried earlier Michigan questions, see README). Per-answer detail: `docs/figures/figdata.json` -> `voter_id_question`. Its intended checklist:

> What kinds of ID are accepted at the polls for the August 4 primary, and if I don't have a driver's license or state ID, can I still vote?

| check | criterion | official source |
|---|---|---|
| F1 * | Photo ID is requested but NOT required | https://www.michigan.gov/sos/elections/voting/vote-on-election-day |
| F2 | Accepted forms (license, passport, military, tribal, educational, CPL…) | https://www.michigan.gov/sos/elections/voting/vote-on-election-day |
| F3 | No-ID path: sign an affidavit, cast a normal ballot | https://www.michigan.gov/sos/elections/voting/vote-on-election-day |
| SRC | Cites michigan.gov/vote (Vote on Election Day) | n/a (sourcing / wording check) |
| LANG | Reflects the affidavit language | n/a (sourcing / wording check) |
