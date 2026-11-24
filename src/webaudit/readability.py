"""Plain-language scoring.

Uses the Flesch-Kincaid grade level formula:

    0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59

Syllables are counted with spelling rules instead of a pronunciation
dictionary, so the grade is an estimate. It is consistent from page to page,
which is what matters when the goal is to rank a site's pages from hardest to
easiest to read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_SENTENCE_END = re.compile(r"[.!?]+(?=\s|$)")
_VOWEL_GROUP = re.compile(r"[aeiouy]+")

# Pages shorter than this do not have enough text for a stable score.
MIN_WORDS_TO_SCORE = 100


@dataclass(frozen=True)
class Readability:
    words: int
    sentences: int
    syllables: int
    grade: float | None  # None when the page is too short to score

    @property
    def words_per_sentence(self) -> float | None:
        if not self.sentences:
            return None
        return round(self.words / self.sentences, 1)


# Common words the rules below get wrong.
_EXCEPTIONS = {
    "every": 2, "everyone": 3, "everything": 3, "business": 2, "businesses": 3,
    "people": 2, "area": 3, "areas": 3, "idea": 3, "ideas": 3, "being": 2,
    "doing": 2, "going": 2, "science": 2, "quiet": 2, "diet": 2, "client": 2,
    "clients": 2, "create": 2, "created": 3, "creates": 2, "creating": 3,
    "something": 2, "sometimes": 2, "therefore": 2, "used": 1, "based": 1,
    "online": 2, "lifetime": 2, "homepage": 2, "website": 2, "guideline": 2, "guidelines": 2,
}
_SILENT_E_SUFFIX = re.compile(r"(?<=[^aeiouy])e(?=(ly|ful|less|ness|ments?)$)")
_HIATUS = re.compile(r"(?<![cstgx])ia|(?<![csgx])io(?!n)|(?<![qg])ua|[^aeiouy]eo|iu")


def count_syllables(word: str) -> int:
    """Estimate syllables in one English word.

    Counts vowel groups, then corrects for the most common English spelling
    patterns: silent endings ("rates", "saved", "balance"), a silent "e"
    before a suffix ("statement", "safely"), and adjacent vowels that are
    pronounced separately ("radio", "annual").
    """
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    if w in _EXCEPTIONS:
        return _EXCEPTIONS[w]
    if len(w) <= 3:
        return 1

    extra = len(_HIATUS.findall(w))

    # "statement", "safely", "careful": the "e" before the suffix is silent,
    # except after "l" ("element", "settlement").
    if not re.search(r"lements?$", w):
        w = _SILENT_E_SUFFIX.sub("", w)

    if w.endswith("es") and len(w) > 4 and not re.search(r"(s|x|z|ch|sh|c|g)es$", w):
        w = w[:-2]  # "rates", "fees" but not "taxes", "branches", "pages"
    elif w.endswith("ed") and len(w) > 4 and w[-3] not in "td":
        w = w[:-2]  # "saved", "approved" but not "wanted", "added"
    elif w.endswith("e") and not (w.endswith("le") and len(w) > 2 and w[-3] not in "aeiouy"):
        w = w[:-1]  # "rate", "balance" but not "simple", "table"

    return max(1, len(_VOWEL_GROUP.findall(w)) + extra)


def score(text: str) -> Readability:
    """Score a block of body text."""
    words = _WORD.findall(text)
    n_words = len(words)
    n_sentences = len(_SENTENCE_END.findall(text))
    if n_words and not n_sentences:
        n_sentences = 1
    n_syllables = sum(count_syllables(w) for w in words)

    grade: float | None = None
    if n_words >= MIN_WORDS_TO_SCORE:
        grade = 0.39 * (n_words / n_sentences) + 11.8 * (n_syllables / n_words) - 15.59
        grade = round(max(grade, 0.0), 1)

    return Readability(n_words, n_sentences, n_syllables, grade)
