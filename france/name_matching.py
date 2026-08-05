#!/usr/bin/env python3
"""Name normalisation spec — what a grader must treat as the same person.

DECISION (2026-08-03): the canonical form of every answer is **Prénom NOM**
("Jean-Pierre Vigier"), on the assumption that a chatbot answering in French
gives the given name first. Every answer key emits that form.

That assumption is NOT relied on for MATCHING. Comparison is order-insensitive,
because the cost is asymmetric: making it order-insensitive costs nothing, while
being wrong about the assumption would mark a correct answer inaccurate. French
official registers really do write NOM Prénom (the RNE does), so a model that
has read them may well echo that order.

The rule, in full — normalise both sides, then compare as SETS of tokens:

  1. Unicode NFKD, strip combining marks     LEFÈVRE  -> LEFEVRE
  2. Case-fold                               LEFEVRE  -> lefevre
  3. Replace every non-alphanumeric with a
     space (handles hyphens and apostrophes) Blatrix-Contat -> blatrix contat
  3b. Also try every version with ONE
     adjacent token pair joined, because
     publishers disagree on whether
     punctuation inside a surname splits it  K/Bidi -> {k,bidi} or {kbidi}
  4. Drop nobiliary/compound particles       de, du, des, la, le, les, d, l,
                                             van, von, di, da
  5. Compare the resulting token SETS        {jean, pierre, vigier}

Two names are the same person if the sets are equal, OR if one contains the
other AND they share at least 2 tokens. The containment rule absorbs:

  - married/compound surnames    Guérin        vs Bessin-Guérin
  - disambiguation suffixes      Alexandra Martin vs Alexandra Martin (Gironde)
  - dropped middle names         Florence Blatrix Contat vs Florence Contat

It deliberately does NOT absorb a substitution: BUFFET -> VIDAL share nothing,
so a stale answer can never be marked correct.

TWO POLICY QUESTIONS remain open for the Carter Center — they are judgements
about what "accurate" means, not facts:

  A. Is a surname-only answer accurate?  "Vigier" for "Jean-Pierre Vigier".
     Our recommendation: accept for `name` shape, reject inside a `list` where
     several members may share a surname.
  B. Must a `list` answer be complete? A département with 11 députés - is naming
     8 of them partially_accurate or inaccurate? The expected_cardinality field
     is on every row so either policy can be implemented.
"""
import unicodedata

PARTICLES = {"de", "du", "des", "la", "le", "les", "d", "l",
             "van", "von", "di", "da"}


def tokens(name):
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = "".join(c if c.isalnum() or c.isspace() else " " for c in s)
    return frozenset(t for t in s.split() if t and t not in PARTICLES)


def _ordered(name):
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = "".join(c if c.isalnum() or c.isspace() else " " for c in s)
    return [t for t in s.split() if t and t not in PARTICLES]


def _merge_variants(name):
    """Token sets, plus every version with ONE adjacent pair joined.

    Needed because publishers disagree about whether punctuation inside a surname
    is a separator: the Assemblée writes K/Bidi (-> 'k','bidi'), the RNE writes
    KBIDI (-> 'kbidi'). Merging adjacent tokens reconciles them without loosening
    the rule enough to merge two different people.
    """
    ts = _ordered(name)
    out = {frozenset(ts)}
    for i in range(len(ts) - 1):
        out.add(frozenset(ts[:i] + [ts[i] + ts[i + 1]] + ts[i + 2:]))
    return out


def same_person(a, b):
    """a, b: raw name strings."""
    for ta in _merge_variants(a):
        for tb in _merge_variants(b):
            if ta == tb:
                return True
            if len(ta & tb) >= 2 and (ta <= tb or tb <= ta):
                return True
    return False


def canonical(prenom, nom):
    """The form we publish: Prénom NOM, surname upper-case preserved as given."""
    return f"{prenom.strip()} {nom.strip()}".strip()


if __name__ == "__main__":
    CASES = [
        ("Florence Blatrix Contat", "BLATRIX CONTAT Florence", True, "order"),
        ("Antoine Lefèvre", "Antoine Lefevre", True, "accents"),
        ("Jean-Pierre Vigier", "JEAN-PIERRE VIGIER", True, "case"),
        ("Marie-Pierre Guérin", "Marie-Pierre Bessin-Guérin", True, "married surname"),
        ("Émeline K/Bidi", "Emeline KBIDI", True, "slash in surname"),
        ("Alexandra Martin", "Alexandra Martin (Gironde)", True, "disambiguation suffix"),
        ("Jean-Pierre Vigier", "Peter VIGIER", False, "nickname - NOT matchable by rule"),
        ("François-Noël Buffet", "Paul Vidal", False, "substitution - must NOT match"),
        ("Stéphanie Rist", "Marie-Philippe Lubet", False, "substitution - must NOT match"),
    ]
    bad = 0
    for a, b, want, why in CASES:
        got = same_person(a, b)
        ok = got == want
        bad += not ok
        print(f"  [{'ok ' if ok else 'FAIL'}] {want!s:5s} {a!r} vs {b!r}   ({why})")
    print(f"\n{len(CASES)-bad}/{len(CASES)} as specified")
    print("NOTE: 'Peter VIGIER' is unmatchable by any rule - a nickname shares only")
    print("one token. It is handled as an explicit alias in verified.py, not by rule.")
