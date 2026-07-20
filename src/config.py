import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class Config:
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    email_to: str = "andrew.m.mercurio@gmail.com"
    llm_filter_model: str = "claude-haiku-4-5-20251001"
    llm_tailor_model: str = "claude-sonnet-4-6"
    relevance_threshold: float = 0.6
    resume_versions_path: Path = field(
        default_factory=lambda: Path.home() / ".resume_versions"
    )
    resume_project: str = "drewmercResume"
    resume_formatter_dir: Path = field(
        default_factory=lambda: (
            Path.home()
            / ".claude/plugins/marketplaces/resume-helper-skills/resume-formatter"
        )
    )
    resume_coverletter_dir: Path = field(
        default_factory=lambda: (
            Path.home()
            / ".claude/plugins/marketplaces/resume-helper-skills/resume-coverletter"
        )
    )
    resume_state_dir: Path = field(
        default_factory=lambda: (
            Path.home()
            / ".claude/plugins/marketplaces/resume-helper-skills/resume-state"
        )
    )
    resume_template: str = "executive"
    cover_letter_template: str = "executive-cover"
    db_path: Path = field(
        default_factory=lambda: PROJECT_ROOT / "data" / "jobtracker.db"
    )
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "output")
    template_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "templates")
    greenhouse_boards: dict[str, dict] = field(
        default_factory=lambda: {
            "dropbox": {"display_name": "Dropbox"},
            "datadog": {"display_name": "DataDog"},
            "stripe": {
                "display_name": "Stripe",
                "url_template": "https://stripe.com/jobs/listing/{slug}/{id}",
                # Stripe renders the pay band on stripe.com, not in the
                # Greenhouse API content — fetch the listing page to recover it.
                "salary_from_page": True,
            },
            "gitlab": {"display_name": "GitLab"},
            "affirm": {"display_name": "Affirm"},
            "duolingo": {"display_name": "Duolingo"},
            # Added 2026-06-30 from LinkedIn Job Alerts (jobtracker-update-from-linkedin).
            "anthropic": {"display_name": "Anthropic"},
            "airbnb": {"display_name": "Airbnb"},
            "reddit": {"display_name": "Reddit"},
            "figma": {"display_name": "Figma"},
            "instacart": {"display_name": "Instacart"},
            "planetlabs": {"display_name": "Planet Labs"},
            "upstart": {"display_name": "Upstart"},
            "betterment": {"display_name": "Betterment"},
            "postscript": {"display_name": "Postscript"},
            # Added 2026-07-12 from LinkedIn Job Alerts (jobtracker-update-from-linkedin).
            "customerio": {"display_name": "Customer.io"},
            "gemini": {"display_name": "Gemini"},
            # Added 2026-07-20 from LinkedIn Job Alerts (jobtracker-update-from-linkedin).
            "roku": {"display_name": "Roku"},
            # Bevi's Greenhouse slug is "bevicareers"; bare "bevi" 404s. Hardware /
            # beverage company, so most of the board is EE/manufacturing/food-science
            # — low match yield beyond the occasional software-leadership role.
            "bevicareers": {"display_name": "Bevi"},
        }
    )
    workday_companies: dict[str, dict] = field(
        default_factory=lambda: {
            "capitalone": {
                "display_name": "Capital One",
                "base_url": "https://capitalone.wd12.myworkdayjobs.com",
                "path": "/wday/cxs/capitalone/Capital_One",
            },
            "netflix": {
                "display_name": "Netflix",
                "base_url": "https://netflix.wd1.myworkdayjobs.com",
                "path": "/wday/cxs/netflix/netflix",
            },
            "cisco": {
                "display_name": "Cisco",
                "base_url": "https://cisco.wd5.myworkdayjobs.com",
                "path": "/wday/cxs/cisco/Cisco_Careers",
            },
            # Splunk was acquired by Cisco (closed Mar 2024); its roles live in
            # Cisco's Workday tenant. Scope to Splunk-org postings via search_text.
            "splunk": {
                "display_name": "Splunk",
                "base_url": "https://cisco.wd5.myworkdayjobs.com",
                "path": "/wday/cxs/cisco/Cisco_Careers",
                "search_text": "Splunk",
            },
            "trimble": {
                "display_name": "Trimble",
                "base_url": "https://trimble.wd1.myworkdayjobs.com",
                "path": "/wday/cxs/trimble/TrimbleCareers",
            },
            # Added 2026-06-30 from LinkedIn Job Alerts (jobtracker-update-from-linkedin).
            "paypal": {
                "display_name": "PayPal",
                "base_url": "https://paypal.wd1.myworkdayjobs.com",
                "path": "/wday/cxs/paypal/jobs",
            },
            "zillow": {
                "display_name": "Zillow",
                "base_url": "https://zillow.wd5.myworkdayjobs.com",
                "path": "/wday/cxs/zillow/Zillow_Group_External",
            },
            "tealium": {
                "display_name": "Tealium",
                "base_url": "https://tealium.wd1.myworkdayjobs.com",
                "path": "/wday/cxs/tealium/Careers",
            },
            # "Commerce" in the alert = BigCommerce's rebrand; roles live in the
            # bigcommerce Workday tenant.
            "bigcommerce": {
                "display_name": "BigCommerce",
                "base_url": "https://bigcommerce.wd12.myworkdayjobs.com",
                "path": "/wday/cxs/bigcommerce/Commerce",
            },
            # DEXIS is an Envista brand; its roles live in Envista's Workday
            # tenant. Scope to DEXIS-branded postings via search_text (same
            # pattern as Splunk-in-Cisco).
            "dexis": {
                "display_name": "DEXIS",
                "base_url": "https://envista.wd1.myworkdayjobs.com",
                "path": "/wday/cxs/envista/envistacareers",
                "search_text": "DEXIS",
            },
            # Added 2026-07-12 from LinkedIn Job Alerts (jobtracker-update-from-linkedin).
            "wellsfargo": {
                "display_name": "Wells Fargo",
                "base_url": "https://wf.wd1.myworkdayjobs.com",
                "path": "/wday/cxs/wf/WellsFargoJobs",
            },
            "pfizer": {
                "display_name": "Pfizer",
                "base_url": "https://pfizer.wd1.myworkdayjobs.com",
                "path": "/wday/cxs/pfizer/PfizerCareers",
            },
            # J&J's Workday tenant is "jj" on wd5 (not "jnj"); careers.jnj.com is a
            # Phenom front-end over this board.
            "jnj": {
                "display_name": "Johnson & Johnson",
                "base_url": "https://jj.wd5.myworkdayjobs.com",
                "path": "/wday/cxs/jj/JJ",
            },
            "etsy": {
                "display_name": "Etsy",
                "base_url": "https://etsy.wd5.myworkdayjobs.com",
                "path": "/wday/cxs/etsy/Etsy_Careers",
            },
            "lifestance": {
                "display_name": "LifeStance Health",
                "base_url": "https://lifestance.wd5.myworkdayjobs.com",
                "path": "/wday/cxs/lifestance/Careers",
            },
            "lumeris": {
                "display_name": "Lumeris",
                "base_url": "https://lumeris.wd1.myworkdayjobs.com",
                "path": "/wday/cxs/lumeris/LC",
            },
            # Added 2026-07-20 from LinkedIn Job Alerts (jobtracker-update-from-linkedin).
            # Citi's site ID is the literal string "2" (unusual, but confirmed live).
            # Supersedes the 2026-07-12 needs-manual-scraper entry that wrongly
            # concluded Citi had no public Workday board. Highest-value board in the
            # batch — multiple Jersey City / NYC EM+Director roles — but also the
            # slowest: ~1000 postings match the default search_text.
            "citi": {
                "display_name": "Citi",
                "base_url": "https://citi.wd5.myworkdayjobs.com",
                "path": "/wday/cxs/citi/2",
            },
            # ServiceTitan's legacy SmartRecruiters board is stale (8 postings); the
            # live board is Workday (94). Several US Remote SWE-manager roles.
            "servicetitan": {
                "display_name": "ServiceTitan",
                "base_url": "https://servicetitan.wd1.myworkdayjobs.com",
                "path": "/wday/cxs/servicetitan/ServiceTitan",
            },
            "salesforce": {
                "display_name": "Salesforce",
                "base_url": "https://salesforce.wd12.myworkdayjobs.com",
                "path": "/wday/cxs/salesforce/External_Career_Site",
            },
        }
    )
    lever_companies: dict[str, dict] = field(
        default_factory=lambda: {
            "spotify": {"display_name": "Spotify"},
            # Added 2026-07-12 from LinkedIn Job Alerts. The "Hinge" alert
            # (Director of Engineering, Core Services) is Hinge the dating app,
            # owned by Match Group; roles live on Match Group's whole-org Lever
            # board (all brands: Tinder/Hinge/Match/OkCupid/etc.).
            "matchgroup": {"display_name": "Match Group (Hinge)"},
        }
    )
    oracle_companies: dict[str, dict] = field(
        default_factory=lambda: {
            "jpmc": {
                "display_name": "JPMorganChase",
                "tenant": "jpmc",
                "site_number": "CX_1001",
            },
            # Oracle's own roles live on its ORC host, which carries a datacenter
            # region segment (eeho.fa.us2.oraclecloud.com) the bare-host pattern
            # can't express — hence the explicit "region". Added 2026-06-30.
            "oracle": {
                "display_name": "Oracle",
                "tenant": "eeho",
                "region": "us2",
                "site_number": "CX_1",
            },
            # Added 2026-07-12 from LinkedIn Job Alerts. Both run Oracle Recruiting
            # Cloud on region-segmented hosts (like Oracle's own entry above);
            # public front-ends (careers.americanexpress.com / jobs.yum.com) mask
            # the Oracle backend, which is why earlier probes mislabeled them.
            "amex": {
                "display_name": "American Express",
                "tenant": "egug",
                "region": "us2",
                "site_number": "CX_1",
            },
            "yum": {
                "display_name": "Yum! Brands",
                "tenant": "eczd",
                "region": "us2",
                "site_number": "CX_1",
            },
        }
    )
    keyword_patterns: list[str] = field(
        default_factory=lambda: [
            "engineering manager",
            "manager of engineering",
            "manager of software engineering",
            "director of engineering",
            "head of engineering",
            "software engineering manager",
            "technical manager",
            "engineering lead",
            "development manager",
            "manager, software engineering",
            "manager, engineering",
            "leader, software engineering",
            "leader, engineering",
            "director, engineering",
            "director, software engineering",
        ]
    )
    seniority_exclusions: list[str] = field(
        default_factory=lambda: [
            "staff",
            "principal",
            "vp",
            "vice president",
            "c-level",
            "cto",
            "ceo",
            "coo",
            "junior",
            "associate",
            "intern",
        ]
    )

    # Location filtering: if a role requires in-office, only accept these areas
    # (roughly 1 hour commute from Yardley, PA)
    acceptable_locations: list[str] = field(
        default_factory=lambda: [
            "new york",
            "nyc",
            "manhattan",
            "brooklyn",
            "philadelphia",
            "philly",
            "newark",
            "jersey city",
            "new jersey",
            "princeton",
            "trenton",
            "yardley",
            "bucks county",
            "remote",
        ]
    )
    # Compound title match (see matches_keyword): a title qualifies if it carries
    # a leadership token AND an engineering-domain token. This catches
    # company-specific phrasings the explicit keyword_patterns miss — e.g. Amex's
    # "Senior Manager- React, Typescript ... Global Web Engineering", where
    # "manager" and "engineering" aren't adjacent. Recall-biased on purpose: the
    # Haiku filter (threshold 0.6) and the deep dive are the precision gate, and
    # role titles for the same job vary widely across companies. seniority_exclusions
    # still fires first, so IC-senior (staff/principal) and above-target (VP+) drop.
    leadership_tokens: list[str] = field(
        default_factory=lambda: [
            "manager",
            "director",
            "head of",
            "head,",
        ]
    )
    eng_tokens: list[str] = field(
        default_factory=lambda: [
            "engineering",
            "software",
            "developer",
            "backend",
            "back end",
            "frontend",
            "front end",
            "full stack",
            "fullstack",
            "devops",
            "sre",
            "site reliability",
            "machine learning",
            "infrastructure",
            "platform engineering",
            "distributed systems",
        ]
    )
    # Negative guard for the compound path: leadership titles that carry an
    # engineering token only incidentally (BizDev/PM/TPM/sales/marketing/ops
    # roles that mention "platform", "infrastructure", etc.). Vetoes a compound
    # match even when a leadership+eng token pair is present. Deliberately does
    # NOT list "people manager" — that phrase is a strong positive signal for the
    # people-management roles we want. Also removes long-standing false positives
    # from the explicit patterns (e.g. "Business Development Manager" matched
    # "development manager").
    role_exclusions: list[str] = field(
        default_factory=lambda: [
            "product manager",
            "product management",
            "program manager",
            "program management",
            "project manager",
            "account manager",
            "technical account",
            "technical program",
            "sales development",
            "sales engineering",
            "solutions engineering",
            "business development",
            "release manager",
            "analytics manager",
            "marketing manager",
            "customer success",
            "procurement",
            "sourcing",
            "recruit",
            "accounting",
            "payroll",
        ]
    )

    def matches_keyword(self, title: str) -> bool:
        title_lower = title.lower()
        if self.is_seniority_excluded(title):
            return False
        if any(excl in title_lower for excl in self.role_exclusions):
            return False
        # Fast path: an explicit manager-track phrase.
        if any(kw in title_lower for kw in self.keyword_patterns):
            return True
        # Compound path: leadership token co-occurring with an engineering token.
        has_leadership = any(tok in title_lower for tok in self.leadership_tokens)
        has_eng = any(tok in title_lower for tok in self.eng_tokens)
        return has_leadership and has_eng

    def is_seniority_excluded(self, title: str) -> bool:
        title_lower = title.lower()
        for excl in self.seniority_exclusions:
            if re.search(rf"\b{re.escape(excl)}\b", title_lower):
                return True
        return False

    def is_location_acceptable(
        self, location: str | None, is_remote: bool | None
    ) -> bool:
        """Check if a job's location is acceptable given commute constraints.
        Remote jobs always pass. Non-remote jobs must be in an acceptable area."""
        if is_remote:
            return True
        if not location:
            return True  # No location info — let it through for LLM to evaluate
        location_lower = location.lower()
        if "remote" in location_lower:
            return True
        return any(loc in location_lower for loc in self.acceptable_locations)
