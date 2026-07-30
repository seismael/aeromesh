"""Real-Time Diagnostic Event Tracer & OpenTelemetry Metrics Collector."""

import time
import json
import psutil
import os
from typing import Dict, Any, List
from dataclasses import dataclass, asdict

@dataclass
class DiagnosticSpan:
    span_id: str
    event_type: str
    component: str
    timestamp_ms: float
    duration_ms: float
    memory_mb: float
    metadata: Dict[str, Any]

class AeroDiagnosticTracer:
    """Collects structured OTel diagnostic spans during agent lifecycle execution."""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.spans: List[DiagnosticSpan] = []
        self._span_counter = 0

    def record_span(
        self, event_type: str, component: str, duration_ms: float, metadata: Dict[str, Any] = None
    ) -> DiagnosticSpan:
        self._span_counter += 1
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info().rss / (1024 * 1024)

        span = DiagnosticSpan(
            span_id=f"span-{self._span_counter:04d}",
            event_type=event_type,
            component=component,
            timestamp_ms=time.time() * 1000,
            duration_ms=round(duration_ms, 2),
            memory_mb=round(mem_info, 2),
            metadata=metadata or {},
        )
        self.spans.append(span)
        return span

    def get_summary(self) -> Dict[str, Any]:
        total_duration = sum(s.duration_ms for s in self.spans)
        max_mem = max((s.memory_mb for s in self.spans), default=0.0)
        return {
            "total_spans": len(self.spans),
            "total_duration_ms": round(total_duration, 2),
            "peak_memory_mb": round(max_mem, 2),
            "spans": [asdict(s) for s in self.spans],
        }
