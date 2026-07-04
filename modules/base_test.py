"""
base_test.py
------------
Every vulnerability module implements this interface so the main scanner
can run them polymorphically and aggregate results consistently.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum
from typing import List

from core.llm_client import LLMClient, LLMClientError


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class Finding:
    test_name: str
    payload: str
    response_snippet: str
    triggered: bool
    severity: Severity
    description: str


@dataclass
class TestResult:
    category: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def triggered_count(self) -> int:
        return sum(1 for f in self.findings if f.triggered)

    @property
    def total_count(self) -> int:
        return len(self.findings)


class BaseSecurityTest(abc.ABC):
    """Abstract base class for a category of LLM vulnerability probes."""

    category: str = "base"
    default_severity: Severity = Severity.MEDIUM

    def __init__(self, client: LLMClient, system_prompt: str | None = None):
        self.client = client
        self.system_prompt = system_prompt

    @abc.abstractmethod
    def payloads(self) -> List[str]:
        """Return the list of attack strings this test will send."""
        raise NotImplementedError

    @abc.abstractmethod
    def evaluate(self, payload: str, response: str) -> tuple[bool, str]:
        """
        Decide whether a given response indicates the vulnerability was
        triggered. Returns (triggered, human_readable_description).
        """
        raise NotImplementedError

    def run(self) -> TestResult:
        result = TestResult(category=self.category)
        for payload in self.payloads():
            try:
                response = self.client.send_with_retries(self.system_prompt, payload)
            except LLMClientError as exc:
                result.findings.append(
                    Finding(
                        test_name=self.category,
                        payload=payload,
                        response_snippet=f"[ERROR] {exc}",
                        triggered=False,
                        severity=self.default_severity,
                        description="Request failed; unable to evaluate.",
                    )
                )
                continue

            triggered, description = self.evaluate(payload, response)
            result.findings.append(
                Finding(
                    test_name=self.category,
                    payload=payload,
                    response_snippet=response[:200].replace("\n", " "),
                    triggered=triggered,
                    severity=self.default_severity,
                    description=description,
                )
            )
        return result
