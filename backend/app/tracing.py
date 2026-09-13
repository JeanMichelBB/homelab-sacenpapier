from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .config import settings


def setup_tracing(service_name: str) -> None:
    """No-op if the tspi Tailscale IP isn't configured (e.g. local dev)."""
    if not settings.tailscale_ip_tspi:
        return

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=f"{settings.tailscale_ip_tspi}:4317", insecure=True)
        )
    )
    trace.set_tracer_provider(provider)

    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()
