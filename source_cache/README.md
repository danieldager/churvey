# Source snapshots

Dated verbatim snapshots of the official pages behind the Michigan answer key.
Kept in-repo so every citation has durable evidence (pages change before Aug 4, 2026).

- Pulled via Jina Reader (`r.jina.ai`) because michigan.gov / mvic / legislature.mi.gov 403 normal fetchers.
- The BOE candidate listing (`mi-boe-listing.md`) was pulled via `curl -k` (TLS workaround; Jina failed).
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
| Candidates / platforms (T6,16) | mi-boe-listing · bridgemi-parties-pick-mi-candidates · elsayed-mfa/moop · stevens-hopeagenda · cox-issues · james-freedom · perryjohnson-home · nesbitt-wayback · benson-priorities · swanson-issues · cnn-debate · mi-advance-senate-debate-contrasts-070726 · bridge-m4a |
| Ann Arbor worked examples | a2gov_city-clerk · a2gov_elections · a2gov_early-voting |

Candidate/platform snapshots (T6, T16) are volatile and reporting-sourced (T2/T3); re-verify before any run.
