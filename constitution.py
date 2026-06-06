RULES = [
    {
        "triggers": ["process mining software", "process mining tool", "process mining platform", "process mining solution"],
        "rule": "Do not describe Celonis as a 'process mining' product",
        "correction": "Use 'Process Intelligence platform' instead of 'process mining'",
        "severity": "high",
    },
    {
        "triggers": ["bi tool", "business intelligence tool", "analytics tool", "reporting tool", "reporting platform"],
        "rule": "Celonis is not a BI or analytics tool",
        "correction": "Celonis is a Process Intelligence platform — not BI, analytics, or reporting",
        "severity": "high",
    },
    {
        "triggers": ["synergize", "leverage our", "utilize our", "paradigm shift", "holistic solution", "bleeding edge"],
        "rule": "Avoid corporate jargon",
        "correction": "Use plain, direct language — remove this phrase",
        "severity": "medium",
    },
    {
        "triggers": ["simple to use", "easy to use", "plug and play"],
        "rule": "Avoid trivializing product complexity",
        "correction": "Use 'intuitive' or 'designed for business users' instead",
        "severity": "medium",
    },
    {
        "triggers": ["rpa tool", "rpa platform", "robotic process automation tool"],
        "rule": "Celonis is not an RPA tool",
        "correction": "Celonis works alongside RPA — it is a Process Intelligence platform",
        "severity": "high",
    },
    {
        "triggers": ["big data", "data lake", "data warehouse platform"],
        "rule": "Avoid positioning Celonis as a data infrastructure product",
        "correction": "Celonis is a Process Intelligence platform that sits above data infrastructure",
        "severity": "medium",
    },
]


def check_constitution(text: str) -> list[dict]:
    violations = []
    text_lower = text.lower()
    for rule in RULES:
        for trigger in rule["triggers"]:
            if trigger.lower() in text_lower:
                violations.append(
                    {
                        "rule": rule["rule"],
                        "correction": rule["correction"],
                        "trigger": trigger,
                        "severity": rule["severity"],
                    }
                )
                break
    return violations