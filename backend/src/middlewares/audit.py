import logging
from starlette.middleware.base import BaseHTTPMiddleware
from src.config.database import Session
from src.models.audit import Audit
class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        response=await call_next(request)
        if request.url.path!="/health" and (request.method!="GET" or request.url.path.endswith("/export")):
            try:
                with Session() as db:
                    db.add(Audit(actor=getattr(request.state,"actor","anonymous"),action=f"{request.method} {request.url.path}",status_code=response.status_code)); db.commit()
            except Exception:
                logging.exception("audit write failed")
        return response
