import asyncio
from uuid import UUID
from celery import Celery
from .config import settings
celery=Celery('fieldatlas',broker=settings.redis_url,backend=settings.redis_url)
celery.conf.update(task_serializer='json',accept_content=['json'],result_serializer='json',worker_prefetch_multiplier=1,task_soft_time_limit=1800,task_time_limit=1860,broker_connection_retry_on_startup=True,task_publish_retry=False)
@celery.task(name='fieldatlas.discover')
def discover(job_id):
    from .pipeline import run_pipeline
    asyncio.run(run_pipeline(UUID(job_id)))
@celery.task(name='fieldatlas.export')
def export(export_id):
    from .exports import run_export
    run_export(UUID(export_id))
