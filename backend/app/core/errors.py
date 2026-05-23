from fastapi import Request
from fastapi.responses import JSONResponse


class AppProblem(Exception):
    def __init__(self, *, status: int, title: str, detail: str, type_: str) -> None:
        self.status = status
        self.title = title
        self.detail = detail
        self.type_ = type_


async def problem_exception_handler(request: Request, exc: AppProblem) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        media_type="application/problem+json",
        content={
            "type": exc.type_,
            "title": exc.title,
            "status": exc.status,
            "detail": exc.detail,
            "instance": str(request.url.path),
            "trace_id": request.headers.get("x-request-id", ""),
        },
    )
