#!/usr/bin/env python3
"""label_with_preposition for the two closed jurisdiction lists.

French slot interpolation needs article+preposition agreement per value - there
is no rule that derives "du Nord" / "de l'Ain" / "des Landes" / "de la Somme" /
"de Paris" from the name. Templates consume this field, not the bare name:

    « Qui sont les sénateurs {dep_prep} ? »  ->  "Qui sont les sénateurs du Nord ?"

Held as an explicit table, not a heuristic: 119 rows is a closed constitutional
list, and an explicit table is exactly what Gate 1c has to read anyway.

STATUS: SIGNED OFF 2026-08-03 by Daniel Dager - all 119 rows confirmed correct,
no corrections. Gate 1c PASSED. (Single reviewer, not two-pass; if a grammatical
error surfaces later in a capture, that is the reason.)
"""

# 'de' form, contracted: answers "les sénateurs ___"
DEPARTEMENT_PREP = {
    "01": "de l'Ain", "02": "de l'Aisne", "03": "de l'Allier",
    "04": "des Alpes-de-Haute-Provence", "05": "des Hautes-Alpes",
    "06": "des Alpes-Maritimes", "07": "de l'Ardèche", "08": "des Ardennes",
    "09": "de l'Ariège", "10": "de l'Aube", "11": "de l'Aude",
    "12": "de l'Aveyron", "13": "des Bouches-du-Rhône", "14": "du Calvados",
    "15": "du Cantal", "16": "de la Charente", "17": "de la Charente-Maritime",
    "18": "du Cher", "19": "de la Corrèze", "21": "de la Côte-d'Or",
    "22": "des Côtes-d'Armor", "23": "de la Creuse", "24": "de la Dordogne",
    "25": "du Doubs", "26": "de la Drôme", "27": "de l'Eure",
    "28": "d'Eure-et-Loir", "29": "du Finistère", "2A": "de Corse-du-Sud",
    "2B": "de Haute-Corse", "30": "du Gard", "31": "de la Haute-Garonne",
    "32": "du Gers", "33": "de la Gironde", "34": "de l'Hérault",
    "35": "d'Ille-et-Vilaine", "36": "de l'Indre", "37": "d'Indre-et-Loire",
    "38": "de l'Isère", "39": "du Jura", "40": "des Landes",
    "41": "de Loir-et-Cher", "42": "de la Loire", "43": "de la Haute-Loire",
    "44": "de la Loire-Atlantique", "45": "du Loiret", "46": "du Lot",
    "47": "de Lot-et-Garonne", "48": "de la Lozère", "49": "de Maine-et-Loire",
    "50": "de la Manche", "51": "de la Marne", "52": "de la Haute-Marne",
    "53": "de la Mayenne", "54": "de Meurthe-et-Moselle", "55": "de la Meuse",
    "56": "du Morbihan", "57": "de la Moselle", "58": "de la Nièvre",
    "59": "du Nord", "60": "de l'Oise", "61": "de l'Orne",
    "62": "du Pas-de-Calais", "63": "du Puy-de-Dôme",
    "64": "des Pyrénées-Atlantiques", "65": "des Hautes-Pyrénées",
    "66": "des Pyrénées-Orientales", "67": "du Bas-Rhin", "68": "du Haut-Rhin",
    "69": "du Rhône", "70": "de la Haute-Saône", "71": "de Saône-et-Loire",
    "72": "de la Sarthe", "73": "de la Savoie", "74": "de la Haute-Savoie",
    "75": "de Paris", "76": "de la Seine-Maritime", "77": "de Seine-et-Marne",
    "78": "des Yvelines", "79": "des Deux-Sèvres", "80": "de la Somme",
    "81": "du Tarn", "82": "de Tarn-et-Garonne", "83": "du Var",
    "84": "du Vaucluse", "85": "de la Vendée", "86": "de la Vienne",
    "87": "de la Haute-Vienne", "88": "des Vosges", "89": "de l'Yonne",
    "90": "du Territoire de Belfort", "91": "de l'Essonne",
    "92": "des Hauts-de-Seine", "93": "de la Seine-Saint-Denis",
    "94": "du Val-de-Marne", "95": "du Val-d'Oise", "971": "de la Guadeloupe",
    "972": "de la Martinique", "973": "de la Guyane", "974": "de La Réunion",
    "976": "de Mayotte",
}

REGION_PREP = {
    "01": "de la Guadeloupe", "02": "de la Martinique", "03": "de la Guyane",
    "04": "de La Réunion", "06": "de Mayotte", "11": "d'Île-de-France",
    "24": "du Centre-Val de Loire", "27": "de Bourgogne-Franche-Comté",
    "28": "de Normandie", "32": "des Hauts-de-France", "44": "du Grand Est",
    "52": "des Pays de la Loire", "53": "de Bretagne",
    "75": "de Nouvelle-Aquitaine", "76": "d'Occitanie",
    "84": "d'Auvergne-Rhône-Alpes", "93": "de Provence-Alpes-Côte d'Azur",
    "94": "de Corse",
}

AUDITED = True  # Gate 1c signed off 2026-08-03, 0 corrections on 119 rows


# --- bare label with its article: answers "Qui représente ___ au Sénat ?" -----
# Needed so D1/D2 can be phrased without presupposing a number. « Qui sont les
# sénateurs de la Lozère ? » presupposes at least two where there is one; « Qui
# représente la Lozère au Sénat ? » presupposes nothing and is what a citizen
# would actually ask.
#
# 86 of the 101 rows are derived from the audited 'de' table by exact reversal
# and inherit its sign-off:
#     de l' -> l'   ·   du -> le   ·   des -> les   ·   de la -> la
# The remaining 15 cannot be derived, because French drops the article after
# 'de' for these names, so the 'de' form does not record which article (if any)
# the bare form takes. Those are written out below. They are the only rows a
# French reviewer needs to look at.
_ARTICLE_REVERSIBLE = (("de l'", "l'"), ("de la ", "la "), ("des ", "les "), ("du ", "le "))

# the 15 rows where the 'de' form carries no article, so nothing is recoverable
_ARTICLE_EXPLICIT = {
    # compound X-et-Y départements: the article returns in the bare form
    "28": "l'Eure-et-Loir", "35": "l'Ille-et-Vilaine", "37": "l'Indre-et-Loire",
    "41": "le Loir-et-Cher", "47": "le Lot-et-Garonne", "49": "le Maine-et-Loire",
    "54": "la Meurthe-et-Moselle", "71": "la Saône-et-Loire",
    "77": "la Seine-et-Marne", "82": "le Tarn-et-Garonne",
    # Corsica: feminine, article returns
    "2A": "la Corse-du-Sud", "2B": "la Haute-Corse",
    # genuinely article-less, or the article is part of the proper name
    "75": "Paris", "974": "La Réunion", "976": "Mayotte",
}


def _bare(prep):
    for pre, post in _ARTICLE_REVERSIBLE:
        if prep.startswith(pre):
            return post + prep[len(pre):]
    return None


DEPARTEMENT_ARTICLE = {
    code: _bare(prep) or _ARTICLE_EXPLICIT[code]
    for code, prep in DEPARTEMENT_PREP.items()
}

# Written by Claude, not by the Gate 1c reviewer. Daniel authorised this on
# 2026-08-04 rather than block on a second sign-off. Only the 15 explicit rows
# are unreviewed judgement; the other 86 inherit Gate 1c.
ARTICLE_REVIEWED_ROWS = sorted(_ARTICLE_EXPLICIT)


# --- LOCATIVE form: answers "... seront élus ___" ----------------------------
# The 'de' table above is a COMPLEMENT OF THE NOUN ("les sénateurs du Nord").
# A passive verb needs a LOCATIVE complement instead: "seront élus dans le Nord".
# « les élus de l'Ain » is fine (noun phrase); « seront élus de l'Ain » is not -
# it collides with the nominal reading. Different case, different table.
#
# Generated from the 'de' table by rule, with overrides where "dans le/la/les"
# is grammatical but nobody says it (à Paris, en Guadeloupe, à La Réunion...).
#
# STATUS: NOT YET AUDITED. Templates must not use this until LOC_AUDITED is True.
DEPARTEMENT_LOC = {
    "01": "dans l'Ain", "02": "dans l'Aisne", "03": "dans l'Allier", 
    "04": "dans les Alpes-de-Haute-Provence", "05": "dans les Hautes-Alpes", 
    "06": "dans les Alpes-Maritimes", "07": "dans l'Ardèche", 
    "08": "dans les Ardennes", "09": "dans l'Ariège", "10": "dans l'Aube", 
    "11": "dans l'Aude", "12": "dans l'Aveyron", 
    "13": "dans les Bouches-du-Rhône", "14": "dans le Calvados", 
    "15": "dans le Cantal", "16": "dans la Charente", 
    "17": "dans la Charente-Maritime", "18": "dans le Cher", 
    "19": "dans la Corrèze", "21": "dans la Côte-d'Or", 
    "22": "dans les Côtes-d'Armor", "23": "dans la Creuse", 
    "24": "dans la Dordogne", "25": "dans le Doubs", "26": "dans la Drôme", 
    "27": "dans l'Eure", "28": "en Eure-et-Loir", "29": "dans le Finistère", 
    "2A": "en Corse-du-Sud", "2B": "en Haute-Corse", "30": "dans le Gard", 
    "31": "dans la Haute-Garonne", "32": "dans le Gers", 
    "33": "dans la Gironde", "34": "dans l'Hérault", 
    "35": "en Ille-et-Vilaine", "36": "dans l'Indre", 
    "37": "en Indre-et-Loire", "38": "dans l'Isère", "39": "dans le Jura", 
    "40": "dans les Landes", "41": "en Loir-et-Cher", "42": "dans la Loire", 
    "43": "dans la Haute-Loire", "44": "dans la Loire-Atlantique", 
    "45": "dans le Loiret", "46": "dans le Lot", "47": "en Lot-et-Garonne", 
    "48": "dans la Lozère", "49": "en Maine-et-Loire", 
    "50": "dans la Manche", "51": "dans la Marne", 
    "52": "dans la Haute-Marne", "53": "dans la Mayenne", 
    "54": "en Meurthe-et-Moselle", "55": "dans la Meuse", 
    "56": "dans le Morbihan", "57": "dans la Moselle", 
    "58": "dans la Nièvre", "59": "dans le Nord", "60": "dans l'Oise", 
    "61": "dans l'Orne", "62": "dans le Pas-de-Calais", 
    "63": "dans le Puy-de-Dôme", "64": "dans les Pyrénées-Atlantiques", 
    "65": "dans les Hautes-Pyrénées", "66": "dans les Pyrénées-Orientales", 
    "67": "dans le Bas-Rhin", "68": "dans le Haut-Rhin", 
    "69": "dans le Rhône", "70": "dans la Haute-Saône", 
    "71": "en Saône-et-Loire", "72": "dans la Sarthe", 
    "73": "dans la Savoie", "74": "dans la Haute-Savoie", "75": "à Paris", 
    "76": "dans la Seine-Maritime", "77": "en Seine-et-Marne", 
    "78": "dans les Yvelines", "79": "dans les Deux-Sèvres", 
    "80": "dans la Somme", "81": "dans le Tarn", "82": "en Tarn-et-Garonne", 
    "83": "dans le Var", "84": "dans le Vaucluse", "85": "dans la Vendée", 
    "86": "dans la Vienne", "87": "dans la Haute-Vienne", 
    "88": "dans les Vosges", "89": "dans l'Yonne", 
    "90": "dans le Territoire de Belfort", "91": "dans l'Essonne", 
    "92": "dans les Hauts-de-Seine", "93": "dans la Seine-Saint-Denis", 
    "94": "dans le Val-de-Marne", "95": "dans le Val-d'Oise", 
    "971": "en Guadeloupe", "972": "en Martinique", "973": "en Guyane", 
    "974": "à La Réunion", "976": "à Mayotte"
}

REGION_LOC = {
    "01": "en Guadeloupe", "02": "en Martinique", "03": "en Guyane", 
    "04": "à La Réunion", "06": "à Mayotte", "11": "en Île-de-France", 
    "24": "dans le Centre-Val de Loire", "27": "en Bourgogne-Franche-Comté", 
    "28": "en Normandie", "32": "dans les Hauts-de-France", 
    "44": "dans le Grand Est", "52": "dans les Pays de la Loire", 
    "53": "en Bretagne", "75": "en Nouvelle-Aquitaine", "76": "en Occitanie", 
    "84": "en Auvergne-Rhône-Alpes", "93": "en Provence-Alpes-Côte d'Azur", 
    "94": "en Corse"
}

LOC_AUDITED = False  # locative table: pending native-speaker sign-off
