"""
Hermes V2 — OpenTelemetry Telemetry Setup
═══════════════════════════════════════════════════════════════
Initializes OpenTelemetry tracing and metrics for the entire
application.  Gracefully degrades when the OTel SDK is not
installed.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_tracer_provider: Any = None
_meter_provider: Any = None


def setup_telemetry(service_name: str = "hermes-v2") -> None:
    """Initialize OpenTelemetry tracing and metrics.

    Call this once during application startup (from main.py).
    """
    global _tracer_provider, _meter_provider

    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

        resource = Resource.create({"service.name": service_name})

        # Tracing
        _tracer_provider = TracerProvider(resource=resource)
        span_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
        _tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        trace.set_tracer_provider(_tracer_provider)

        # Metrics
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint="http://localhost:4317", insecure=True)
        )
        _meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(_meter_provider)

        logger.info("[TELEMETRY] OpenTelemetry initialized for %s", service_name)

    except ImportError:
        logger.warning(
            "[TELEMETRY] opentelemetry-sdk not installed — telemetry disabled."
        )
    except Exception as exc:
        logger.warning("[TELEMETRY] Failed to initialize: %s", exc)


def get_tracer(name: str) -> Any:
    """Return an OpenTelemetry tracer (or no-op)."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except Exception:
        return _NoOpTracer()


def get_meter(name: str) -> Any:
    """Return an OpenTelemetry meter (or no-op)."""
    try:
        from opentelemetry import metrics
        return metrics.get_meter(name)
    except Exception:
        return _NoOpMeter()


class _NoOpTracer:
    def start_as_current_span(self, *args, **kwargs):
        return _NoOpSpan()

    def start_span(self, *args, **kwargs):
        return _NoOpSpan()


class _NoOpSpan:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def set_attribute(self, *args, **kwargs):
        pass

    def set_status(self, *args, **kwargs):
        pass


class _NoOpMeter:
    def create_counter(self, *args, **kwargs):
        return _NoOpCounter()

    def create_histogram(self, *args, **kwargs):
        return _NoOpHistogram()


class _NoOpCounter:
    def add(self, *args, **kwargs):
        pass


class _NoOpHistogram:
    def record(self, *args, **kwargs):
        pass
