import re

IDENTIFIER_RE = re.compile(r"BUS[0-9]{4}-ROUTE[A-Z][0-9]{2}")


def validate_regex(identifier):
    return bool(IDENTIFIER_RE.fullmatch((identifier or "").strip().upper()))


def validate_dfa(identifier):
    """DFA for BUS dddd-ROUTE L dd; state advances only on the expected symbol."""
    text = (identifier or "").strip().upper()
    literals = "BUS"
    state = 0
    for char in text:
        if state < 3:
            ok = char == literals[state]
        elif 3 <= state <= 6:
            ok = char.isdigit() and char.isascii()
        elif state == 7:
            ok = char == "-"
        elif 8 <= state <= 12:
            ok = char == "ROUTE"[state - 8]
        elif state == 13:
            ok = "A" <= char <= "Z"
        elif state in (14, 15):
            ok = char.isdigit() and char.isascii()
        else:
            return False
        if not ok:
            return False
        state += 1
    return state == 16


def validate_identifier(identifier):
    dfa, regex = validate_dfa(identifier), validate_regex(identifier)
    return {"valid": dfa and regex, "dfa": dfa, "regex": regex,
            "message": "Identifier accepted" if dfa and regex else "Use BUS####-ROUTE[A-Z]##, for example BUS1234-ROUTEA01"}


def route_key(identifier):
    if not validate_identifier(identifier)["valid"]:
        raise ValueError("Cannot extract a route from an invalid bus identifier")
    return identifier.strip().upper()[-3]
