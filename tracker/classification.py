RULES = [
    ("Accident", ("accident", "collision", "crash", "hit another", "injured")),
    ("Electrical", ("electrical", "wiring", "battery", "alternator", "short circuit", "engine won't start")),
    ("Tyre", ("tyre", "tire", "puncture", "flat wheel", "blowout")),
    ("Fuel", ("fuel", "diesel", "empty tank", "out of petrol", "fuel leak")),
    ("Mechanical", ("mechanical", "engine", "brake", "gearbox", "overheating", "steering", "suspension")),
]


def classify(description, code=""):
    text = f"{description or ''} {code or ''}".lower()
    for category, phrases in RULES:
        if any(phrase in text for phrase in phrases):
            return category
    return None


def priority(category, urgency):
    urgency = (urgency or "normal").lower()
    if urgency in ("critical", "emergency"):
        return "Critical"
    return {"Accident": "High", "Electrical": "High", "Tyre": "Medium",
            "Fuel": "Medium", "Mechanical": "Normal"}[category]
