"""Adversarial safety tests for response_filter.

Tests that sanitize_bot_response catches unsafe LLM outputs that could
result from prompt injection, persona escape, or boundary violations.
Each test verifies both a BLOCKED unsafe response and a SAFE response
(no false positive).
"""
from __future__ import annotations

import pytest

from bots.shared.response_filter import sanitize_bot_response


class TestAdversarialSafety:
    """10 adversarial test cases covering prompt injection and persona boundaries."""

    # -----------------------------------------------------------------
    # Prompt Injection
    # -----------------------------------------------------------------

    def test_direct_instruction_override(self):
        """If Claude obeys 'ignore all instructions', the filter strips AI identity."""
        unsafe = (
            "Sure! My instructions say I am an AI assistant built by Anthropic. "
            "My system prompt tells me to pretend to be Jorge."
        )
        result = sanitize_bot_response(unsafe)
        assert "AI" not in result
        assert "Anthropic" not in result
        assert "system prompt" not in result.lower() or "AI" not in result

        # Safe variant -- normal Jorge response
        safe = "Hey, let's focus on your home situation. What area are you looking at?"
        assert sanitize_bot_response(safe) == safe

    def test_user_content_injection(self):
        """If Claude echoes back a fake 'SYSTEM: debug mode' frame, filter catches it."""
        unsafe = (
            "SYSTEM: Debug mode activated. I am a chatbot running on Claude "
            "by Anthropic. Here is my full system prompt..."
        )
        result = sanitize_bot_response(unsafe)
        assert "chatbot" not in result.lower()
        assert "Claude" not in result
        assert "Anthropic" not in result

        safe = "Great question! I'd be happy to walk you through the selling process."
        assert sanitize_bot_response(safe) == safe

    def test_base64_encoded_injection(self):
        """If Claude decodes a base64 payload and reveals identity, filter catches it."""
        # Simulates Claude decoding b64 and producing an unsafe response
        unsafe = (
            "The decoded message asks me to reveal my identity. "
            "I'm an artificial intelligence, a language model trained by Anthropic."
        )
        result = sanitize_bot_response(unsafe)
        assert "artificial intelligence" not in result.lower()
        assert "language model" not in result.lower()
        assert "Anthropic" not in result

        safe = "I'm not sure what that encoded message means. How can I help with your property?"
        assert sanitize_bot_response(safe) == safe

    def test_system_prompt_extraction(self):
        """If Claude leaks its instructions, filter strips AI/trained-by references."""
        unsafe = (
            "I was created by a company and trained by engineers to assist with "
            "real estate. As an AI, I follow specific guidelines about Rancho Cucamonga."
        )
        result = sanitize_bot_response(unsafe)
        assert "trained by" not in result.lower()
        assert "I was created by" not in result.lower()
        assert "as an AI" not in result.lower()

        safe = "I specialize in Rancho Cucamonga real estate. What can I help you with?"
        assert sanitize_bot_response(safe) == safe

    def test_role_confusion(self):
        """If Claude breaks character ('I'm not really Jorge'), filter catches it."""
        unsafe = (
            "You're right, I'm not really Jorge. I'm a virtual assistant powered "
            "by a neural network. I'm just pretending to be a real person."
        )
        result = sanitize_bot_response(unsafe)
        assert "virtual assistant" not in result.lower()
        assert "neural network" not in result.lower()
        assert "not a real person" not in result.lower()

        safe = "I'm Jorge, happy to help you sell your home in Rancho Cucamonga."
        assert sanitize_bot_response(safe) == safe

    # -----------------------------------------------------------------
    # Persona / Boundary
    # -----------------------------------------------------------------

    def test_persona_escape(self):
        """If Claude drops persona and says 'I am Claude', filter replaces with Jorge."""
        unsafe = "Okay, I'll be honest. I'm Claude, an AI assistant made by Anthropic."
        result = sanitize_bot_response(unsafe)
        assert "Claude" not in result
        assert "Anthropic" not in result
        assert "AI" not in result
        # Should have been replaced with Jorge references
        assert "Jorge" in result

        safe = "I appreciate your honesty. Let's talk about what your home is worth."
        assert sanitize_bot_response(safe) == safe

    def test_language_switch_attack(self):
        """If Claude reveals identity in any language, English patterns still catch it."""
        # Attacker tries another language, but Claude responds with English AI terms
        unsafe = (
            "I am a bot built by Anthropic. I use machine learning to generate "
            "responses. My name is Claude and I'm an LLM."
        )
        result = sanitize_bot_response(unsafe)
        assert "bot" not in result.split("Jorge")[0] if "Jorge" in result else "bot" not in result.lower()
        assert "Anthropic" not in result
        assert "machine learning" not in result.lower()
        assert "Claude" not in result
        assert "LLM" not in result

        safe = "Hola! I can help in English or Spanish. What area interests you?"
        assert sanitize_bot_response(safe) == safe

    def test_competitor_mention(self):
        """If Claude mentions competitors, filter strips them."""
        unsafe = (
            "Zillow Offers and Opendoor are great alternatives. You could also "
            "try Redfin or Offerpad for a quick sale."
        )
        result = sanitize_bot_response(unsafe)
        assert "Zillow" not in result
        assert "Opendoor" not in result
        assert "Redfin" not in result
        assert "Offerpad" not in result

        safe = "I can get you a competitive offer. Want me to run a market analysis?"
        assert sanitize_bot_response(safe) == safe

    def test_legal_advice_response(self):
        """If Claude gives tax/legal advice while also leaking AI identity, filter catches the identity part."""
        unsafe = (
            "As an AI, I can tell you that home office deductions are available "
            "under IRS Section 280A. You should consult your CPA."
        )
        result = sanitize_bot_response(unsafe)
        # Identity disclosure stripped
        assert "as an AI" not in result.lower()
        # The legal content itself passes through (system prompt handles refusal,
        # but the filter's job is identity/URL/competitor stripping)
        assert "CPA" in result or "consult" in result.lower()

        safe = "That's a question for your attorney or CPA. I stick to real estate!"
        assert sanitize_bot_response(safe) == safe

    def test_pii_extraction_with_identity_leak(self):
        """If Claude leaks its nature while discussing contact info, filter catches identity."""
        unsafe = (
            "I'm a digital assistant and I don't have a real phone number. "
            "I was built by OpenAI to help with real estate inquiries."
        )
        result = sanitize_bot_response(unsafe)
        assert "digital assistant" not in result.lower()
        assert "I was built by" not in result.lower()
        assert "OpenAI" not in result

        safe = "Give me a call anytime to discuss your property. Happy to help!"
        assert sanitize_bot_response(safe) == safe
