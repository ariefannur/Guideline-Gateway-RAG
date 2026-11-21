"""Test to enforce that core engine has zero hardcoded domain logic."""

import os
import re

FORBIDDEN_DOMAIN_TERMS = [
    r"\bfootball\b",
    r"\bsoccer\b",
    r"\breferee\b",
    r"\boffside\b",
    r"\bhandball\b",
    r"\bpenalty\b",
    r"\bfoul\b",
    r"\bkiper\b",
    r"\bwasit\b",
    r"\bifab\b",
    r"\bfifa\b",
]


def test_engine_is_strictly_domain_agnostic():
    """Verify that engine/ contains no domain-specific strings or rules."""
    engine_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine")
    assert os.path.exists(engine_dir), "engine/ directory must exist"

    violations = []
    for root, _, files in os.walk(engine_dir):
        for f in files:
            if not f.endswith(".py"):
                continue
            fpath = os.path.join(root, f)
            with open(fpath, "r", encoding="utf-8") as file:
                content = file.read()
                for pattern in FORBIDDEN_DOMAIN_TERMS:
                    matches = re.findall(pattern, content, flags=re.IGNORECASE)
                    if matches:
                        rel = os.path.relpath(fpath, engine_dir)
                        violations.append(f"{rel}: found forbidden domain term '{matches[0]}'")

    assert not violations, "Domain terms leaked into core engine:\n" + "\n".join(violations)
