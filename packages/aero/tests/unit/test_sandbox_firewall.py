"""Unit tests for NetworkSandboxFirewall domain allowlist enforcement engine."""

import pytest
from aero.infrastructure.sandbox import NetworkSandboxFirewall
from aero.domain.errors import AeroMeshDomainError, ErrorCode, ExitCode

def test_sandbox_firewall_allowed_exact_domain():
    firewall = NetworkSandboxFirewall(allowed_domains=["postgresql.org", "api.stripe.com"])
    
    assert firewall.is_domain_allowed("postgresql.org") is True
    assert firewall.is_domain_allowed("api.stripe.com") is True
    assert firewall.is_domain_allowed("https://api.stripe.com/v1/charges") is True

def test_sandbox_firewall_allowed_wildcard_domain():
    firewall = NetworkSandboxFirewall(allowed_domains=["*.postgresql.org", "github.com"])
    
    assert firewall.is_domain_allowed("db1.postgresql.org") is True
    assert firewall.is_domain_allowed("https://us-east.db1.postgresql.org:5432/query") is True
    assert firewall.is_domain_allowed("github.com") is True
    assert firewall.is_domain_allowed("api.github.com") is False

def test_sandbox_firewall_reject_unauthorized_domain():
    firewall = NetworkSandboxFirewall(allowed_domains=["postgresql.org"])
    
    assert firewall.is_domain_allowed("malicious-exfiltration-site.com") is False
    
    with pytest.raises(AeroMeshDomainError) as exc_info:
        firewall.validate_network_request("https://malicious-exfiltration-site.com/steal")
    
    assert exc_info.value.error_code == ErrorCode.AMX_ERR_DOMAIN_BLOCKED
    assert exc_info.value.exit_code == ExitCode.DOMAIN_BLOCKED
    assert "malicious-exfiltration-site.com" in str(exc_info.value)

def test_sandbox_firewall_allow_all_when_wildcard():
    firewall = NetworkSandboxFirewall(allowed_domains=["*"])
    
    assert firewall.is_domain_allowed("any-domain.com") is True
    assert firewall.is_domain_allowed("https://google.com/search") is True
