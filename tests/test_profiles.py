"""Unit tests for domain chunking profiles."""

from profiles import (
    HierarchicalClauseProfile,
    ProceduralStepsProfile,
    QAPairProfile,
    SectionTableProfile,
    get_profile,
)


def test_hierarchical_clause_profile():
    profile = get_profile("hierarchical-clause")
    assert isinstance(profile, HierarchicalClauseProfile)

    sample_md = """# Section 1 - General Requirements
## 1. Safety Measures
Personnel must wear personal protective equipment at all times.
All incidents must be reported immediately.

# Section 2 - Equipment Specifications
## 2. Electrical Tools
Insulated gloves are required when operating high-voltage tools.
"""

    chunks = profile.chunk(sample_md, edition="2024")
    assert len(chunks) >= 2
    assert chunks[0].section_no == 1
    assert "Section 1" in chunks[0].title
    assert "personal protective equipment" in chunks[0].text
    assert chunks[1].section_no == 2


def test_procedural_steps_profile():
    profile = get_profile("procedural-steps")
    assert isinstance(profile, ProceduralStepsProfile)

    sample_md = """## Step 1: Initialization
1. Turn on master switch.
2. Verify pressure gauge reads 100 PSI.

## Step 2: Calibration
1. Adjust calibration valve until indicator turns green.
"""

    chunks = profile.chunk(sample_md)
    assert len(chunks) == 2
    assert "Step 1" in chunks[0].title
    assert "master switch" in chunks[0].text
    assert "calibration valve" in chunks[1].text


def test_qa_pair_profile():
    profile = get_profile("qa-pair")
    assert isinstance(profile, QAPairProfile)

    sample_md = """### Q: What is the server restart policy?
Servers are restarted every Sunday at 02:00 UTC.

### Q: How do I request elevated access?
Submit an access request ticket via the IT service portal.
"""

    chunks = profile.chunk(sample_md)
    assert len(chunks) == 2
    assert "restart policy" in chunks[0].title
    assert "Sunday at 02:00 UTC" in chunks[0].text


def test_section_table_profile():
    profile = get_profile("section-table")
    assert isinstance(profile, SectionTableProfile)

    sample_md = """## Section 1: Server Dimensions
| Model | Height | Weight |
| --- | --- | --- |
| Alpha 100 | 2U | 15kg |

## Section 2: Power Ratings
| Voltage | Amps |
| --- | --- |
| 220V | 10A |
"""

    chunks = profile.chunk(sample_md)
    assert len(chunks) == 2
    assert "Alpha 100" in chunks[0].text
    assert "220V" in chunks[1].text
