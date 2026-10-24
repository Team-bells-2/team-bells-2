import re
from decimal import Decimal, InvalidOperation

_NUMBER_WORDS: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_SCALES: dict[str, int] = {"k": 1_000, "thousand": 1_000, "m": 1_000_000, "million": 1_000_000}
_FILLERS = {"and", "naira", "ngn"}


def parse_naira_amount(text: str) -> Decimal | None:
    """Naira shorthand and words to an amount, in code, never by the model (FR-S4).
    "ten k" -> 10000, "2.5k" -> 2500, "sixty k" -> 60000, "₦60,000" -> 60000,
    "two and half k" -> 2500. Returns None when the phrase is not a recognisable amount."""
    cleaned = text.lower().replace("₦", " ").replace(",", "").replace("-", " ").strip()
    cleaned = re.sub(r"\bn(?=\d)", "", cleaned)  # "N60000"
    cleaned = re.sub(r"(\d)([a-z])", r"\1 \2", cleaned)  # "2.5k" -> "2.5 k"
    tokens = cleaned.split()
    if not tokens:
        return None

    total = Decimal(0)
    current = Decimal(0)
    seen_number = False
    for index, token in enumerate(tokens):
        if token in _FILLERS:
            continue
        if token == "a":
            # "a thousand" is 1000; in "and a half" the "a" adds nothing.
            if index + 1 < len(tokens) and tokens[index + 1] == "half":
                continue
            current += 1
            seen_number = True
        elif token in _NUMBER_WORDS:
            current += _NUMBER_WORDS[token]
            seen_number = True
        elif re.fullmatch(r"\d+(\.\d+)?", token):
            current += Decimal(token)
            seen_number = True
        elif token == "half":
            current += Decimal("0.5")
            seen_number = True
        elif token == "hundred":
            current = (current or Decimal(1)) * 100
        elif token in _SCALES:
            total += (current or Decimal(1)) * _SCALES[token]
            current = Decimal(0)
        else:
            return None
    if not seen_number:
        return None
    try:
        return (total + current).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
