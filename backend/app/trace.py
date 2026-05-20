from __future__ import annotations

import time
import uuid

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id", uuid.uuid4().hex[:12])

        with logger.contextualize(trace_id=trace_id):
            start = time.perf_counter()
            logger.info(
                "{method} {path} {client}",
                method=request.method,
                path=request.url.path,
                client=request.client.host if request.client else "-",
            )
            response = await call_next(request)
            elapsed_ms = round((time.perf_counter() - start) * 1000)
            logger.info(
                "{status} {elapsed}ms",
                status=response.status_code,
                elapsed=elapsed_ms,
            )
            response.headers["X-Trace-Id"] = trace_id
            return response
