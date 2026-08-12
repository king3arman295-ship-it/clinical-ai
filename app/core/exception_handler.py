from fastapi import Request
from fastapi.responses import JSONResponse

from app.exceptions.exceptions import AppException
from app.core.logger import logger


async def app_exception_handler(
    request: Request,
    exc: AppException
):

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "data": None
        }
    )


async def unexpected_exception_handler(
    request: Request,
    exc: Exception
):
    # Previously this swallowed every unhandled exception with no trace,
    # so real errors (e.g. missing DB tables) never showed up anywhere,
    # not even Railway's logs. Log the full traceback before responding.
    logger.exception(f"Unhandled error on {request.method} {request.url.path}: {exc}")

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal Server Error",
            "data": None
        }
    )