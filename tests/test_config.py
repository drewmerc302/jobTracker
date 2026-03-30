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


def test_config_seniority_excluded():
    config = Config()
    assert config.is_seniority_excluded("VP of Engineering")
    assert config.is_seniority_excluded("Principal Engineer")
    assert not config.is_seniority_excluded("Senior Engineering Manager")
