from src.config import Config


def test_config_loads_defaults():
    config = Config()
    assert config.relevance_threshold == 0.6
    assert config.llm_filter_model == "claude-haiku-4-5-20251001"
    assert config.llm_tailor_model == "claude-sonnet-4-6"
    assert config.email_to == "andrew.m.mercurio@gmail.com"
    assert config.db_path.name == "jobtracker.db"
    assert len(config.keyword_patterns) > 0
    assert "engineering manager" in config.keyword_patterns


def test_config_greenhouse_companies():
    config = Config()
    gh = config.greenhouse_boards
    assert "dropbox" in gh
    assert "datadog" in gh
    assert "stripe" in gh


def test_config_keyword_match():
    config = Config()
    assert config.matches_keyword("Senior Engineering Manager")
    assert config.matches_keyword("Director of Engineering")
    assert not config.matches_keyword("Software Engineer")
    assert not config.matches_keyword("VP of Engineering")


def test_config_compound_match_catches_nonadjacent_tokens():
    """Leadership + engineering tokens that aren't adjacent (company-specific
    phrasings the explicit patterns miss) should still match."""
    config = Config()
    # Amex-style: "manager" and "engineering" separated by the tech stack.
    assert config.matches_keyword(
        "Senior Manager- React, Typescript, Next.js - Global Web Engineering"
    )
    assert config.matches_keyword("Director, AI Engineering (Agentic AI Platform)")
    assert config.matches_keyword("Manager, Machine Learning Engineering (Fraud)")
    # A leadership title with no engineering token must not match.
    assert not config.matches_keyword("Senior Manager, Data Strategy and Insights")


def test_config_compound_match_negative_guard():
    """Non-eng leadership titles that merely mention an eng noun are vetoed,
    but real engineering-management titles survive the guard."""
    config = Config()
    # Vetoed: incidental eng token in a non-eng role.
    assert not config.matches_keyword("Business Development Manager, Agentic Commerce")
    assert not config.matches_keyword("Technical Program Manager, Engineering")
    assert not config.matches_keyword("Senior Product Manager, Platform")
    # Survives: "People Manager" is a positive signal, not a veto.
    assert config.matches_keyword(
        "Senior Manager, Software Engineering - Full Stack (People Manager)"
    )
    # Survives: eng role that happens to mention marketing tech.
    assert config.matches_keyword(
        "Engineering Manager, Marketing Technology - Segmentation Platform"
    )


def test_config_seniority_excluded():
    config = Config()
    assert config.is_seniority_excluded("VP of Engineering")
    assert config.is_seniority_excluded("Principal Engineer")
    assert not config.is_seniority_excluded("Senior Engineering Manager")


def test_config_bank_svp_is_not_excluded():
    """Banks invert the ladder: SVP is a senior-manager rung below Director,
    not an executive title. Both the abbreviated and spelled-out forms must
    survive the seniority gate, while a bare VP still gets vetoed."""
    config = Config()
    # Abbreviated: \bvp\b can't match inside "svp", so this always worked —
    # pin it so a future regex change can't silently regress it.
    assert not config.is_seniority_excluded(
        "Senior Engineering Manager, Capital Markets Platform - SVP"
    )
    # Spelled out: this was the actual bug — vetoed by the "vice president"
    # entry, silently dropping in-band Citi/JPMC/Wells Fargo roles.
    assert not config.is_seniority_excluded(
        "Senior Vice President, Engineering Sr Lead Analyst - C14"
    )
    assert config.matches_keyword("SVP, Software Engineering Manager")
    # The exemption must not leak: a bare VP is still above target.
    assert config.is_seniority_excluded("Vice President of Engineering")
    assert config.is_seniority_excluded("VP of Engineering")
    # A title carrying both forms is still excluded on the bare one.
    assert config.is_seniority_excluded(
        "VP, Engineering — reports to the Senior Vice President"
    )
