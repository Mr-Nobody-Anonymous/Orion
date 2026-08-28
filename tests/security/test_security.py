"""Tests for security: secret vault, prompt guard, audit chain, approvals."""

from __future__ import annotations

import pytest

from orion.security import ApprovalGate, AuditLog, PromptGuard, SecretVault, redact_mapping


class TestSecretVault:
    def test_store_and_verify(self) -> None:
        vault = SecretVault()
        reference = vault.store("broker_key", "super-secret-value")
        assert vault.verify("broker_key", "super-secret-value")
        assert not vault.verify("broker_key", "wrong")
        assert reference.digest != "super-secret-value"

    def test_write_once(self) -> None:
        vault = SecretVault()
        vault.store("k", "v1")
        with pytest.raises(ValueError):
            vault.store("k", "v2")

    def test_scrub_removes_secret_from_text(self) -> None:
        vault = SecretVault()
        vault.store("api_key", "sk-1234567890abcdef1234")
        scrubbed, count = vault.scrub("please call the API with sk-1234567890abcdef1234 now")
        assert count >= 1
        assert "sk-1234567890abcdef1234" not in scrubbed
        assert "[REDACTED]" in scrubbed

    def test_pattern_scrub_without_vault_knowledge(self) -> None:
        vault = SecretVault()
        scrubbed, count = vault.scrub("token: AKIAIOSFODNN7EXAMPLE and ghp_" + "a" * 36)
        assert count >= 2
        assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed

    def test_names_do_not_leak_values(self) -> None:
        vault = SecretVault()
        vault.store("k", "value")
        assert vault.names() == ("k",)


class TestPromptGuard:
    def test_prompt_with_secret_is_scrubbed(self) -> None:
        vault = SecretVault()
        vault.store("key", "sk-abcdefghijklmnop1234")
        guard = PromptGuard(vault)
        safe, allowed = guard.screen("Analyze AAPL using key sk-abcdefghijklmnop1234")
        assert allowed
        assert "sk-abcdefghijklmnop1234" not in safe
        assert guard.leakage_attempts_detected >= 1

    def test_clean_prompt_untouched(self) -> None:
        guard = PromptGuard(SecretVault())
        safe, allowed = guard.screen("Analyze AAPL momentum")
        assert safe == "Analyze AAPL momentum" and allowed


class TestAuditLog:
    def test_chain_verifies(self) -> None:
        log = AuditLog()
        log.append("decision", actor="executive", decision="BUY", confidence=0.7)
        log.append("risk_check", actor="risk", approved=True)
        ok, reason = log.verify()
        assert ok and reason == "ok"

    def test_tampering_breaks_chain(self) -> None:
        log = AuditLog()
        log.append("a", actor="x")
        log.append("b", actor="y")
        # Simulate tampering by rebuilding an entry with altered detail.
        victim = log.entries()[1]
        tampered = victim.__class__(
            victim.sequence, victim.action, victim.actor, {"injected": True},
            victim.timestamp, victim.previous_hash, victim.entry_hash,
        )
        log._entries[1] = tampered
        ok, reason = log.verify()
        assert not ok

    def test_empty_action_rejected(self) -> None:
        with pytest.raises(ValueError):
            AuditLog().append("  ", actor="x")


class TestApprovalGate:
    def test_request_and_approve(self) -> None:
        gate = ApprovalGate()
        token = gate.request("enable_live_trading", justification="operator console request")
        assert not gate.is_approved("enable_live_trading")
        assert gate.approve("enable_live_trading", token, approver="operator")
        assert gate.is_approved("enable_live_trading")

    def test_wrong_token_denied(self) -> None:
        gate = ApprovalGate()
        gate.request("promote_model", justification="candidate v2")
        assert not gate.approve("promote_model", "0" * 16, approver="operator")
        assert not gate.is_approved("promote_model")

    def test_no_request_no_approval(self) -> None:
        gate = ApprovalGate()
        assert not gate.approve("anything", "deadbeefdeadbeef", approver="operator")

    def test_revoke(self) -> None:
        gate = ApprovalGate()
        token = gate.request("x", justification="y")
        gate.approve("x", token, approver="op")
        gate.revoke("x", revoker="op")
        assert not gate.is_approved("x")

    def test_empty_justification_rejected(self) -> None:
        with pytest.raises(ValueError):
            ApprovalGate().request("x", justification=" ")

    def test_all_actions_audited(self) -> None:
        gate = ApprovalGate()
        token = gate.request("op", justification="need it")
        gate.approve("op", token, approver="op")
        actions = [entry.action for entry in gate.audit.entries()]
        assert actions == ["approval_requested", "approval_granted"]


def test_redact_mapping() -> None:
    payload = {"api_key": "sk-secret", "symbol": "AAPL", "password": "hunter2"}
    redacted = redact_mapping(payload)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["symbol"] == "AAPL"
    assert payload["api_key"] == "sk-secret"  # original untouched
