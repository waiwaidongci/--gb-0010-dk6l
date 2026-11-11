from redis import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from src.config.settings import REDIS_URL
import time
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        if request.url.path=="/auth/login":
            client=Redis.from_url(REDIS_URL)
            key=f"frontier:login:{request.client.host}:{int(time.time()//60)}"
            count=client.incr(key)
            if count==1: client.expire(key,65)
            if count>30:
                return JSONResponse({"detail":"登录请求过于频繁，请一分钟后重试"},429)
        return await call_next(request)
