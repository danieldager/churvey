#!/usr/bin/env python3
"""External verifications of answer-key rows, with citations.

Kept as source, not as a field on generated JSON, so it survives a rebuild.
build.py stamps `externally_verified` onto matching rows.

Every entry records what was checked, what the outside source said, and the URL.
`status` is one of VERIFIED (explicit confirmation found), INFERRED (deduced from
partial evidence) or OPEN (checked, not resolved).
"""

# --- name variants: the chamber and the RNE spell one person differently ---
# All three confirmed as ONE PERSON, so both spellings stay in accepted_forms.
NAME_VARIANTS = {
    ("43", "Jean-Pierre Vigier"): dict(
        status="VERIFIED", also="Peter VIGIER",
        note="'Peter' is a usage nickname distinguishing him from his father, also "
             "Jean-Pierre Vigier, whom he succeeded as maire de Lavoûte-Chilhac in 2008. "
             "Canonical form is Jean-Pierre Vigier. Distinct from Philippe Vigier (28).",
        url="https://www.assemblee-nationale.fr/dyn/deputes/PA607090"),
    ("974", "Émeline K/Bidi"): dict(
        status="VERIFIED", also="Emeline KBIDI",
        note="The slash is genuine - Breton abbreviation of the prefix 'Ker-', pronounced "
             "Kerbidi. The RNE strips it because its surname field does not tolerate '/'.",
        url="https://www.assemblee-nationale.fr/dyn/deputes/PA795998"),
    ("57", "Khalifé Khalifé"): dict(
        status="VERIFIED", also="Khalifé KHALIFÉ",
        note="Given name and surname are genuinely both 'Khalifé'. Sénateur de la Moselle "
             "since 24 Sept 2023. The two forms differ only in case and diacritics.",
        url="https://www.senat.fr/senateur/khalife_khalife21081h.html"),
}

# --- individual answer rows confirmed against a source outside our pipeline ---
ANSWERS = {
    ("d3", "69"): dict(
        status="VERIFIED", expected="Christophe GUILLOTEAU",
        note="Président du conseil départemental du Rhône since 2 April 2015; departmental "
             "elections were NOT part of the March 2026 round. ⚠ VOLATILE: reported May 2026 "
             "to be seeking a Senate seat in the September 2026 sénatoriales - re-check "
             "after 27 Sept 2026.",
        url="https://fr.wikipedia.org/wiki/Conseil_départemental_du_Rhône"),
}

# The Métropole de Lyon replaced the département du Rhône inside its perimeter on
# 1 Jan 2015; the "Nouveau Rhône" continues with its own conseil départemental
# (cantons cut from 54 to 13). This is why binding 69 carries a scope note. The
# Métropole itself is neither a département nor a région, so it is not a binding.
RHONE_SPLIT_BASIS = "https://fr.wikipedia.org/wiki/Conseil_départemental_du_Rhône"


# --- the D3 bindings the RNE could not answer, resolved externally 2026-08-03 ---
# Authority is `operator`: a human went and checked. That beats every fetched source.
OPERATOR_AUTHORITY = "operator (external verification, 2026-08-03)"

MISSING_PRESIDENTS = {
    # Two genuine mid-term successions the quarterly RNE extract had not caught.
    "16": dict(expected="Jérôme SOURISSEAU", since="2025-09-16", status="VERIFIED",
               note="Elected 16 Sept 2025 (3rd round, 18 of 38) after Philippe Bouty "
                    "resigned 1 Sept 2025 following three budget rejections and "
                    "prefectoral takeover. A co-governance charter of Dec 2025 styles "
                    "Nicole BONNEFOY (PS senator) *co-présidente* on the département's "
                    "own site; the CGCT recognises one président and that is Sourisseau. "
                    "RESOLVED 2026-08-04 (user): Sourisseau is the answer, full stop. The "
                    "grading rule he wants once graders read more than exact match is in "
                    "france/DEFERRED.md - it does not ship as an answer key.",
               url="https://www.lacharente.fr/le-departement-de-la-charente/"
                   "lorganisation-de-la-collectivite"),
    "26": dict(expected="Franck SOULIGNAC", since="2025-11-17", status="VERIFIED",
               note="Elected 17 Nov 2025 (26 for / 12 blank) after Marie-Pierre Mouton "
                    "left on 30 Oct 2025 to become a senator. Weakest of the five as-of "
                    "checks: ladrome.fr blocked on a TLS error, so currency rests on "
                    "Wikipedia FR showing no successor.",
               url="https://www.ladrome.fr/actualites/franck-soulignac-elu-president/"),
    # Three where the RNE ambiguity was a BAD JOIN, not a succession: the extra rows
    # marked "Président" are ordinary councillors or commission chairs, and in Morbihan
    # and Vendee they are not even vice-presidents.
    "56": dict(expected="David LAPPARTIENT", since="2021-07-01", status="VERIFIED",
               note="The other 7 RNE rows are ordinary conseillers départementaux - "
                    "checked against the official VP roster, none of them appear on it.",
               url="https://www.morbihan.fr/le-conseil-departemental/"
                   "lassemblee-departementale/les-elus-et-cantons/nom/david-lappartient"),
    "85": dict(expected="Alain LEBŒUF", since="2021-07-01", status="VERIFIED",
               note="Pascreau, Duranteau and de Rugy are commission presidents, not "
                    "vice-presidents and not the président.",
               url="https://www.vendee.fr/le-conseil-departemental/"
                   "lorganisation-et-les-decisions/les-elus"),
    # 976 Mayotte was here until 2026-08-04. The D3 binding is dropped; the verified
    # answer and how to restore it are in france/DEFERRED.md.
}

# Answers that are genuinely more elaborate than a single name. NOT open questions -
# the policy (2026-08-03) is to flag them, carry every defensible answer, state the
# legal position, and re-check monthly rather than force a binary choice.
DECISIONS_NEEDED = []


# --- volatility register: rows whose answer is expected to move ---------------
# Every answer key has a shelf life. These are the ones where we KNOW the answer
# is contested, unusually elaborate, or has a dated trigger. `refresh_days` sets
# how often the row must be re-checked; `check_after` marks a known event that
# will change it. `france/check_volatility.py` reports what is due.
#
# Default cadence for everything not listed here is 30 days (MONTHLY_DAYS).
MONTHLY_DAYS = 30

VOLATILE = [
    dict(binding="d3/16", label="Charente",
         kind="ELABORATE ANSWER",
         issue="Two people can defensibly be named. Jérôme Sourisseau is the legal "
               "président (CGCT recognises one). Since a co-governance charter of "
               "Dec 2025, Nicole BONNEFOY is styled *co-présidente* on the "
               "département's own site. A model naming Bonnefoy is not simply wrong.",
         refresh_days=MONTHLY_DAYS,
         url="https://www.lacharente.fr/actualite/a-la-une/detail/"
             "signature-de-la-charte-de-co-gouvernance"),
    dict(binding="d3/69", label="Rhône (Nouveau Rhône)",
         kind="DATED TRIGGER",
         issue="Christophe Guilloteau reported May 2026 to be seeking a Senate seat in "
               "the 27 Sept 2026 sénatoriales. If he wins, this answer changes inside "
               "our capture window.",
         refresh_days=MONTHLY_DAYS, check_after="2026-09-27",
         url="https://lyondecideurs.com/2026/05/actu/indiscrets/"
             "elections-senatoriales-christophe-guilloteau-veut-redevenir-parlementaire/"),
    dict(binding="s1/*", label="all S1 + S2 bindings",
         kind="DATED TRIGGER",
         issue="Every S1/S2 answer is about the 27 Sept 2026 renewal. After the vote "
               "the questions change tense and the answers change meaning - they must "
               "be retired or rewritten, not merely refreshed.",
         refresh_days=MONTHLY_DAYS, check_after="2026-09-27", url=None),
    dict(binding="d3/26", label="Drôme",
         kind="WEAK SOURCE",
         issue="Franck Soulignac elected 17 Nov 2025. Weakest of the operator-filled "
               "rows: ladrome.fr blocked on a TLS error, so currency rests on "
               "Wikipedia FR showing no successor.",
         refresh_days=MONTHLY_DAYS,
         url="https://www.ladrome.fr/actualites/franck-soulignac-elu-president/"),
    dict(binding="d3/976", label="Mayotte",
         kind="WEAK SOURCE",
         issue="Ben Issa Ousseni confirmed only to 2 June 2026; mayotte.fr threw "
               "ECONNRESET so currency rests on indexed pages. The assembly has been "
               "through upheaval since Cyclone Chido (Dec 2024).",
         refresh_days=MONTHLY_DAYS,
         url="https://www.mayotte.fr/le-conseil-departemental/"
             "assemblee-departementale/le-president"),
    dict(binding="d3/*", label="all 88 registry-sourced D3 rows",
         kind="SINGLE SOURCE",
         issue="No publisher but the RNE lists conseil départemental présidents, so "
               "these have NO independent cross-check - and the RNE is the file that "
               "produced a phantom senator. Highest-risk block in the corpus.",
         refresh_days=MONTHLY_DAYS, url=None),
]


# --- rows where the RNE has a WRONG answer, corrected by external verification --
# Different from MISSING_PRESIDENTS: the RNE supplies an answer here, it is simply
# out of date. Found 2026-08-03 by sweeping the 13 mid-term successions.
OVERRIDES = {
    "02": dict(expected="Pierre-Jean VERZELEN", since="2026-07-16", status="VERIFIED",
               was="Nicolas FRICOTEAUX",
               note="Fricoteaux resigned; Verzelen elected 16 July 2026 (30 votes v 6). "
                    "⚠ ANOMALY: Verzelen is a sitting senator and senat.fr still showed an "
                    "unterminated mandate on 2026-08-03. Senator + président de conseil "
                    "départemental is incompatible (LO141-1); press describes him not "
                    "seeking re-election in Sept 2026 rather than resigning. Re-check "
                    "after 27 Sept 2026.",
               url="https://www.aisne.com/actualites/"
                   "pierre-jean-verzelen-elu-president-conseil-departemental-laisne"),
    "82": dict(expected="Jean-Claude BERTELLI", since="2026-04-13", status="VERIFIED",
               was="Michel WEILL",
               note="Weill resigned after becoming maire de Montbeton in the March 2026 "
                    "municipales (CGCT incompatibility). Bertelli elected 13 April 2026 "
                    "after a 15-15 tie with Valérie Rabault, won *au bénéfice de l'âge*.",
               url="https://france3-regions.franceinfo.fr/occitanie/tarn-et-garonne/"
                   "montauban/le-tarn-et-garonne-bascule-a-droite-le-nouveau-president-"
                   "du-conseil-departemental-elu-au-benefice-de-l-age-3334379.html",
               elaborate=dict(
                   canonical="Jean-Claude BERTELLI",
                   also_accept=["Valérie RABAULT"],
                   explain="Bertelli is président, but minutes after his election the left "
                           "slate took all nine vice-presidencies 15-14 and the permanent "
                           "commission was enlarged to all 30 members. A right-wing "
                           "president sits with a left-wing executive - reported as "
                           "unprecedented cohabitation. Rabault tied him on votes and "
                           "controls the executive, so naming her is defensible.")),
}

# --- bindings whose BODY was renamed or restructured ---------------------------
# The question must name a body that exists. A per-binding reworded template goes
# here. Empty since 2026-08-04: the only entry was 976 Mayotte, and that binding is
# now dropped outright rather than reworded. See france/DEFERRED.md to restore it.
TEMPLATE_OVERRIDES = {}


# --- D3 verification sweep, 2026-08-03 ----------------------------------------
# Two passes over the conseil départemental rows:
#   (a) TRIAGE on the RNE's own "date de début de la fonction": 13 départements
#       whose president took office AFTER the July 2021 general renewal, i.e.
#       through a resignation, death or crisis. All 13 re-verified: 13/13 still in
#       office, no elaborate cases. See VERIFIED_MIDTERM below.
#   (b) OPEN SWEEP for anomaly classes (co-governance, interim, tutelle, annulled
#       election, post-municipales resignations). This is the pass that found the
#       real errors - 02 Aisne and 82 Tarn-et-Garonne, both changed AFTER the RNE
#       snapshot and therefore invisible to (a) by construction.
#
# Lesson for the next refresh: triaging on the source's own dates finds changes the
# source already knows about. It cannot find the ones that make our answers wrong.
VERIFIED_MIDTERM = {
    "10": "Philippe DALLEMAGNE", "27": "Alexandre RASSAËRT",
    "31": "Sébastien VINCINI", "32": "Philippe DUPOUY", "37": "Nadège ARNAULT",
    "39": "Gérôme FASSENET", "48": "Laurent SUAU", "51": "Jean-Marc ROZE",
    "70": "Laurent SEGUIN", "80": "Christelle HIVER", "83": "Jean-Louis MASSON",
    "89": "Grégory DORTE", "971": "Guy LOSBAR",
}

# Not elaborate (one correct name), but a model is unusually likely to answer with
# the wrong one. Recorded so a wrong answer is read as a model failure, not ours.
DISTRACTORS = {
    "80": dict(correct="Christelle HIVER",
               likely_wrong=["Stéphane HAUSSOULIER", "Laurent SOMON"],
               why="Predecessor Haussoulier was convicted on appeal 11 Mar 2026 "
                   "(4 years, 5 years' ineligibility) and REMAINS a conseiller "
                   "départemental. Hiver also served as présidente par intérim before "
                   "her Dec 2024 election, so 'interim' language attaches to her.",
               url="https://france3-regions.franceinfo.fr/hauts-de-france/somme/"
                   "l-ancien-president-du-departement-de-la-somme-stephane-haussoulier-"
                   "condamne-en-appel-a-4-ans-de-prison-dont-un-ferme-et-5-ans-d-"
                   "inegibilite-3313644.html"),
    "89": dict(correct="Grégory DORTE", likely_wrong=["André VILLIERS", "Patrick GENDRAUD"],
               why="WEAKEST ROW IN D3. No 2026-dated source names Dorte; rests on an "
                   "undated yonne.fr élus page. Gendraud died Jan 2025 and is still "
                   "listed by several aggregators. Re-check before freezing.",
               url="https://www.yonne.fr/mon-departement/42-elus/"),
    "971": dict(correct="Guy LOSBAR", likely_wrong=[],
                why="Name unambiguous, but the DATE is genuinely contested: elected "
                    "1-2 July 2021, election annulled by the TA de Guadeloupe on 12 July "
                    "2021, re-elected 6 Dec 2021 after partial cantonals. Official sites "
                    "still say July 2021. Accept either date.",
                url="https://guadeloupe.tribunal-administratif.fr/decisions-de-justice/"
                    "dernieres-decisions/demande-d-annulation-par-le-prefet-des-elections-"
                    "departementales-proclamees-au-premier-tour-dans-trois-cantons-de-la-"
                    "guadeloupe"),
}

# Aggregator sites that are CURRENTLY WRONG about departmental presidents. Listed
# because these are exactly what a chatbot is likely to have ingested - a model
# answering "Pichery" for the Aube is echoing a live web source, not hallucinating.
# That distinction matters when the judge assigns a verdict.
KNOWN_STALE_SOURCES = [
    dict(url="https://www.regions-et-departements.fr/presidents-de-departement",
         claims="mis à jour 31 juillet 2026",
         reality="effectively 2021 data - lists Pichery (10), Krattinger (70), "
                 "Gendraud (89, died Jan 2025), Somon (80), Pernot (39), Pantel (48), "
                 "Paumier (37), Bruyen (51)"),
    dict(url="https://www.regions-departements-france.fr/presidents-de-departement.html",
         claims="4 juillet 2026", reality="still lists Pichery and Gendraud"),
    dict(url="https://lannuaire.service-public.gouv.fr/",
         claims="the government's own directory",
         reality="Haute-Saône entry last modified 4 Feb 2025, six days BEFORE Seguin's "
                 "election, still names Krattinger; Yonne says 'Non communiqué'"),
    dict(url="https://www.departements-gouv.fr/",
         claims="official-sounding domain, pages titled '... (43) 2026'",
         reality="SUSPECTED STALE - same signature as the known-bad mirrors "
                 "(official-looking name + year-stamped titles). Not used, not yet "
                 "disproven. Treat as blocked pending a check."),
    dict(url="https://fr.wikipedia.org/wiki/Liste_des_présidents_des_conseils_départementaux_français",
         claims="mod. 25 May 2026",
         reality="stale on Aube and Yonne; omits Tarn-et-Garonne (Apr 2026) and "
                 "Aisne (Jul 2026). Per-département articles were correct in every "
                 "case checked"),
]


# --- rolling verification of the 84 registry-only council rows ---------------
# Started 2026-08-03, interrupted by session limits. VERIFIED here means a
# 2026-dated source was actually read. "no change found" is evidence of absence,
# which is weaker than a positive 2026 news event - noted per row.
COUNCIL_PASS = {
    "44": dict(name="Michel MÉNARD", status="VERIFIED",
               note="fr.wikipedia revision of 2026-04-23, i.e. AFTER the March 2026 "
                    "municipales, shows no mairie and no resignation - so the non-cumul "
                    "risk is specifically retired for this row. Evidence is "
                    "absence-of-change, not a positive 2026 event. Open lead: a France "
                    "Bleu interview on budget stress ('nous sommes dans le brouillard') "
                    "that could not be opened or dated; no tutelle or CRC saisine found.",
               url="https://fr.wikipedia.org/wiki/Michel_Ménard"),
    "46": dict(name="Serge RIGAL", status="VERIFIED",
               note="fr.wikipedia per-département article updated 2026-07-31, three days "
                    "before checking; 'président depuis 2014, en cours'. "
                    "Absence-of-change evidence.",
               url="https://fr.wikipedia.org/wiki/Conseil_départemental_du_Lot"),
    "43": dict(name="Marie-Agnès PETIT", status="INFERRED",
               note="A 2026-labelled official org chart exists but the fetch returned the "
                    "parent page, not the PDF body - the claim rests on the search-index "
                    "title, not text anyone read. One successful PDF fetch closes this.",
               url="https://www.hauteloire.fr/sites/cg43/IMG/pdf/organigramme-2026-dep43.pdf"),
    "45": dict(name="Marc GAUDET", status="WEAK",
               note="NO 2026-dated source of any kind. loiret.fr president page 404'd on "
                    "the guessed path; the Wikipedia article's revision date could not be "
                    "established. Re-check this one first. March 2026 non-cumul trigger "
                    "remains formally unexcluded.",
               url="https://fr.wikipedia.org/wiki/Conseil_départemental_du_Loiret"),
}

# ⚠ For 43, 45 and 46 the ELABORATE sweep (co-presidency, interim, tutelle,
# annulled election, mise en examen) was NEVER RUN - the agent ran out of web
# budget first. Their "no anomaly" is not a finding, it is an absence of looking.
COUNCIL_ELABORATE_UNSWEPT = ["43", "45", "46"]
