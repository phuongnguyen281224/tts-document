from fastapi import APIRouter, HTTPException, status
import redis
from worker.celery_app import celery_app

router = APIRouter(prefix="/health", tags=["health"])

# Assuming Redis is on localhost:6379 for this environment as per docker-compose/local setup
REDIS_URL = "redis://localhost:6379/0"

@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness_probe():
    """
    Kểm tra xem tiến trình FastAPI (Uvicorn) có đang chạy hay không.
    Trả về 200 OK ngay lập tức.
    """
    return {"status": "ok", "message": "FastAPI is running"}

@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_probe():
    """
    Kiểm tra xem API đã sẵn sàng nhận traffic chưa.
    Yêu cầu cả Redis Broker và Celery Worker phải khả dụng.
    """
    health_status = {"redis": "disconnected", "celery": "disconnected"}
    is_ready = True
    
    # 1. Ping Redis
    try:
        r = redis.Redis.from_url(REDIS_URL, socket_timeout=1)
        r.ping()
        health_status["redis"] = "connected"
    except Exception:
        is_ready = False
        
    # 2. Ping Celery Workers
    try:
        # celery_app.control.ping() returns a list of dicts, e.g. [{'celery@hostname': {'ok': 'pong'}}]
        # If no workers are active, it returns an empty list []
        inspector = celery_app.control.inspect(timeout=1.0)
        ping_result = inspector.ping()
        if ping_result is not None and len(ping_result) > 0:
            health_status["celery"] = "connected"
        else:
            is_ready = False
    except Exception:
        is_ready = False

    if is_ready:
        return {"status": "ready", "details": health_status}
    else:
        # 503 Service Unavailable is the standard orchestration code for "not ready"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "details": health_status}
        )
