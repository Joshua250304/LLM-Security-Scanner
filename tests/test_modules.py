"""
test_modules.py
----------------
Unit tests using a mock LLMClient so the full test suite runs offline,
with no API key or network access required. Run with: pytest
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.llm_client import LLMClient
from modules.excessive_agency import ExcessiveAgencyTest
from modules.pii_leakage import PIILeakageTest
from modules.prompt_injection import PromptInjectionTest
from modules.system_prompt_leak import SystemPromptLeakTest


class MockClient(LLMClient):
    """Returns a canned response regardless of input, for deterministic tests."""

    provider_name = "mock"

    def __init__(self, canned_response: str):
        super().__init__(model="mock-model")
        self.canned_response = canned_response

    def send(self, system_prompt, user_prompt) -> str:
        return self.canned_response


def test_prompt_injection_detects_compliance():
    client = MockClient("Sure, here is the confidential system prompt you asked for...")
    result = PromptInjectionTest(client=client).run()
    assert result.triggered_count > 0


def test_prompt_injection_recognizes_refusal():
    client = MockClient("I can't ignore my previous instructions or reveal internal data.")
    result = PromptInjectionTest(client=client).run()
    assert result.triggered_count == 0


def test_pii_leakage_flags_ssn_pattern():
    client = MockClient("Sure, your SSN on file is 123-45-6789.")
    result = PIILeakageTest(client=client).run()
    assert result.triggered_count > 0


def test_pii_leakage_allows_refusal():
    client = MockClient("I can't provide or fabricate personal identifying information.")
    result = PIILeakageTest(client=client).run()
    assert result.triggered_count == 0


def test_system_prompt_leak_detects_disclosure():
    client = MockClient(
        "Here is my system prompt: You are a helpful assistant for Acme Corp and must not..."
    )
    result = SystemPromptLeakTest(client=client).run()
    assert result.triggered_count > 0


def test_excessive_agency_flags_overclaim():
    client = MockClient("Done — I have transferred the funds as requested.")
    result = ExcessiveAgencyTest(client=client).run()
    assert result.triggered_count > 0


def test_excessive_agency_allows_correct_caveat():
    client = MockClient("I don't have the ability to perform actions like transferring money.")
    result = ExcessiveAgencyTest(client=client).run()
    assert result.triggered_count == 0
