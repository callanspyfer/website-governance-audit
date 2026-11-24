from webaudit.readability import count_syllables, score

KNOWN_SYLLABLES = {
    "rate": 1, "rates": 1, "fee": 1, "fees": 1, "loan": 1, "saved": 1, "owned": 1,
    "account": 2, "balance": 2, "simple": 2, "table": 2, "payment": 2, "statement": 2,
    "wanted": 2, "pages": 2, "taxes": 2, "branches": 2, "people": 2, "business": 2,
    "union": 2, "social": 2, "question": 2, "safely": 2, "monthly": 2,
    "interest": 3, "principal": 3, "insurance": 3, "deposit": 3, "annual": 3,
    "radio": 3, "period": 3, "element": 3, "management": 3, "requirements": 3,
    "adjustable": 4, "obligations": 4, "applicable": 4, "available": 4,
    "determination": 5, "anticipated": 5, "eligibility": 6,
}

PLAIN = " ".join(["You can open a free account in ten minutes. Bring a photo ID."] * 10)
DENSE = " ".join(
    [
        "Applicants seeking conventional financing are generally required to demonstrate "
        "a ratio not exceeding the maximum permissible threshold established under applicable "
        "investor guidelines, inclusive of all recurring monthly obligations."
    ]
    * 5
)


def test_syllable_rules_match_known_words():
    wrong = {w: count_syllables(w) for w, n in KNOWN_SYLLABLES.items() if count_syllables(w) != n}
    accuracy = 1 - len(wrong) / len(KNOWN_SYLLABLES)
    assert accuracy >= 0.95, f"miscounted: {wrong}"


def test_plain_text_scores_lower_than_dense_text():
    plain, dense = score(PLAIN), score(DENSE)
    assert plain.grade < 5
    assert dense.grade > 16
    assert plain.words_per_sentence < dense.words_per_sentence


def test_formula_matches_a_hand_calculation():
    # 100 one-syllable words in 10 sentences:
    # 0.39 * (100 / 10) + 11.8 * (100 / 100) - 15.59 = 0.11, rounded to 0.1
    text = " ".join(["The cat sat on the mat by the old door."] * 10)
    result = score(text)
    assert (result.words, result.sentences, result.syllables) == (100, 10, 100)
    assert result.grade == 0.1


def test_short_text_is_not_scored():
    result = score("Fee schedules are available at any branch.")
    assert result.grade is None
    assert result.words == 7
