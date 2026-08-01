"""Unit tests for OpenTelemetry Diagnostic Span Tracer in aero.infrastructure.diagnostics."""

import pytest
from aero.infrastructure.diagnostics import AeroDiagnosticTracer

def test_telemetry_tracer_disabled():
    tracer = AeroDiagnosticTracer(enabled=False)
    assert tracer.enabled is False
    tracer.record_span("TEST", "TestComponent", 5.0)
    summary = tracer.get_summary()
    assert summary["total_spans"] == 1

def test_telemetry_tracer_enabled():
    tracer = AeroDiagnosticTracer(enabled=True)
    assert tracer.enabled is True
    tracer.record_span("PARSE_MANIFEST", "ManifestParser", 4.25, metadata={"agent_id": "test_agent"})
    tracer.record_span("RESOLVE_VAULT", "ZeroTrustVaultResolver", 0.50, metadata={"resolved_count": 2})

    summary = tracer.get_summary()
    assert summary["total_spans"] == 2
    assert len(summary["spans"]) == 2
    assert summary["spans"][0]["event_type"] == "PARSE_MANIFEST"
    assert summary["spans"][1]["event_type"] == "RESOLVE_VAULT"
