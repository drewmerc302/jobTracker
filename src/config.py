import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class Config:
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    email_to: str = "andrew.m.mercurio@gmail.com"
    llm_filter_model: str = "claude-haiku-4-5-20251001"
    llm_tailor_model: str = "claude-sonnet-4-6"
    relevance_threshold: float = 0.6
    resume_versions_path: Path = field(default_factory=lambda: Path.home() / ".resume_versions")
    resume_project: str = "drewmercResume"
    resume_formatter_dir: Path = field(
        default_factory=lambda: Path.home() / ".claude/plugins/marketplaces/resume-helper-skills/resume-formatter"
    )
    resume_coverletter_dir: Path = field(
        default_factory=lambda: Path.home() / ".claude/plugins/marketplaces/resume-helper-skills/resume-coverletter"
    )
    resume_state_dir: Path = field(
        default_factory=lambda: Path.home() / ".claude/plugins/marketplaces/resume-helper-skills/resume-state"
    )
    resume_template: str = "executive"
    cover_letter_template: str = "executive-cover"
    db_path: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "jobtracker.db")
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "output")
    template_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "templates")
    greenhouse_boards: dict[str, str] = field(default_factory=lambda: {
        "dropbox": "Dropbox",
        "datadog": "DataDog",
        "stripe": "Stripe",
    })
    workday_companies: dict[str, dict] = field(default_factory=lambda: {
        "capitalone": {
            "display_name": "Capital One",
            "base_url": "https://capitalone.wd12.myworkdayjobs.com",
            "path": "/wday/cxs/capitalone/Capital_One",
        },
    })
    keyword_patterns: list[str] = field(default_factory=lambda: [
        "engineering manager",
        "manager of engineering",
        "director of engineering",
        "head of engineering",
        "software engineering manager",
        "technical manager",
        "engineering lead",
        "development manager",
    ])
    seniority_exclusions: list[str] = field(default_factory=lambda: [
        "staff", "principal", "vp", "vice president",
        "c-level", "cto", "ceo", "coo",
        "junior", "associate", "intern",
    ])

    def matches_keyword(self, title: str) -> bool:
        title_lower = title.lower()
        if self.is_seniority_excluded(title):
            return False
        return any(kw in title_lower for kw in self.keyword_patterns)

    def is_seniority_excluded(self, title: str) -> bool:
        title_lower = title.lower()
        for excl in self.seniority_exclusions:
            if re.search(rf"\b{re.escape(excl)}\b", title_lower):
                return True
        return False
