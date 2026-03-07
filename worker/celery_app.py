from celery import Celery

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
)
