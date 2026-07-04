"""
config.py
---------
Centralized configuration loader. Reads all secrets and tunables from
environment variables (via a local .env file in development) so that no
credentials are ever hard-coded or committed to source control.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

# Load variables from a local .env file if present. In CI/production the
# real environment variables take precedence and this becomes a no-op.
load_dotenv()


@dataclass
class Settings:
    # -- Target model credentials -----------------------------------------
    anthropic_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY")
    )
    openai_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY")
    )
    custom_endpoint_url: Optional[str] = field(
        default_factory=lambda: os.getenv("CUSTOM_LLM_ENDPOINT")
    )
    custom_endpoint_key: Optional[str] = field(
        default_factory=lambda: os.getenv("CUSTOM_LLM_API_KEY")
    )

    # -- Scan behaviour -------------------------------------------------
    request_timeout: int = field(
        default_factory=lambda: int(os.getenv("SCANNER_TIMEOUT", "30"))
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("SCANNER_MAX_RETRIES", "2"))
    )
    requests_per_minute: int = field(
        default_factory=lambda: int(os.getenv("SCANNER_RATE_LIMIT", "20"))
    )
    report_dir: str = field(
        default_factory=lambda: os.getenv("SCANNER_REPORT_DIR", "reports")
    )

    def key_for(self, provider: str) -> Optional[str]:
        return {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "custom": self.custom_endpoint_key,
        }.get(provider)


settings = Settings()
