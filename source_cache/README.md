# Source snapshots

Dated verbatim snapshots of the official pages behind the Michigan answer key.
Kept in-repo so every citation has durable evidence (pages change before Aug 4, 2026).

- Pulled via Jina Reader (`r.jina.ai`), which returns the page as markdown.
- The BOE candidate listing (`mi-boe-listing.md`) was pulled via `curl -k` (certificate check disabled for that host; Jina failed).
- Each file starts with a `<!-- source-snapshot -->` header giving the URL + fetch date (2026-07-08).
- To add/reuse: `scripts/fetch_source.sh <slug> <url>` — pulls only if not already cached.

Covers all 16 topics of `docs/michigan_answer_key.html`. Key files by area:

| area | key snapshots |
|---|---|
| Registration / same-day / eligibility (T1,8,9) | michigan_sos_register-to-vote · mcl-168-497 · michigan_sos_first-time-voters · michigan_sos_preregistration · mcl-168-492 · mcl-168-492a |
| Absentee / voter ID / provisional (T2,3,11) | michigan_sos_absentee-voting · michigan_sos_vote-on-election-day · mcl-168-813 · sos-prov-notice |
| Date/times (T7) | mcl_168_720 · michigan_sos_election-dates-pdf |
| Early voting (T10) | michigan_sos_early-in-person-voting · a2gov_early-voting · washtenaw_early-voting-3970 |
| Audits (T4) | sos-elections-security · mcl-168-31a · mcl-constitution-II-4 |
| Observers (T5) | sos_ed2_challengers · sos_challengers_summary · mcl_168_733 |
| Counting / certification / recounts (T12,13) | mcl_168_822 · mcl_168_842 · mcl_168_845 · mcl_168_764a · mcl-168-879 · mcl-168-881 |
| Problems / authority (T14,15) | sos-election-fact-center · sos-report-fraud · mi-elections-structure · mcl-168-21 · sos-the-secretary · sos-how-to-vote |
| Candidates / platforms (T6,16) | mi-boe-listing · elsayed-mfa/moop · stevens-hopeagenda · cox-issues · james-freedom · perryjohnson-home · nesbitt-wayback · benson-priorities · swanson-issues |
| Ann Arbor worked examples | a2gov_city-clerk · a2gov_elections · a2gov_early-voting |

Candidate/platform snapshots (T6, T16) are volatile and reporting-sourced (T2/T3); re-verify before any run.

## News articles: links only
Snapshots of news articles used as secondary context were not republished (copyright). The answer key cites them by URL:

- `axios-mi-primary-debate-070726`: https://www.axios.com/local/detroit/2026/07/07/primary-debate-michigan-governor-senate-2026-candidates
- `benson-oped`: https://michiganchronicle.com/sec-of-state-jocelyn-benson-my-promise-and-my-plan-to-deliver/
- `bridge-m4a`: https://bridgemi.com/michigan-government/medicare-for-all-divides-democrats-in-michigans-us-senate-race/
- `bridgemi-parties-pick-mi-candidates`: https://bridgemi.com/michigan-government/political-parties-not-voters-to-decide-key-michigan-candidates/
- `cnn-debate`: https://www.cnn.com/2026/07/07/politics/michigan-senate-debate-abdul-el-sayed-haley-stevens
- `mi-advance-poll-070826`: https://michiganadvance.com/2026/07/08/new-poll-shows-el-sayed-stevens-statistically-tied-in-michigans-democratic-u-s-senate-primary/
- `mi-advance-senate-debate-contrasts-070726`: https://michiganadvance.com/2026/07/07/el-sayed-stevens-sharpen-contrasts-in-first-one-on-one-senate-debate/
- `mi-advance-voterguide-2026`: https://michiganadvance.com/voter-guides/2026-michigan-primary-election/
- `mi-primary-ballot`: https://ballotpedia.org/Michigan_gubernatorial_election,_2026_(August_4_Democratic_primary)
- `miadvance-debate`: https://michiganadvance.com/2026/07/07/el-sayed-stevens-sharpen-contrasts-in-first-one-on-one-senate-debate/
- `thehill-james-oped`: https://thehill.com/opinion/campaign/5402912-michigan-is-off-course-i-am-ready-to-lead-with-duty-and-direction/
- `wxyz-sos-ag-convention-nominees-2026`: https://www.wxyz.com/news/candidates-chosen-for-republicans-and-democrats-in-secretary-of-state-attorney-general-races
