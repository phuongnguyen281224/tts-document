from celery import Celery

# OpenTelemetry Instrumentation
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from app.telemetry import setup_telemetry

# Khởi tạo Global Tracer Provider và nối OTel vào Celery ngay lập tức
# Việc này đảm bảo Trace ID sẽ được chèn vào Headers của Redis message
setup_telemetry("celery-worker")
CeleryInstrumentor().instrument()

celery_app = Celery(
    "pdf_worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=['worker.tasks']
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_transport_options={'visibility_timeout': 3600} # 1 hour timeout for long TTS tasks
)
