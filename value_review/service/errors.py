"""One error shape for the whole API: {"error": {"code", "message", "details"}} (contract, shared conventions).

Pattern copied from parsing_validator/service/errors.py (ADR-001).
"""
import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger('value_review')


class ApiError(Exception):
    def __init__(self, status, code, message, details=None, headers=None):
        super().__init__(message)
        self.status, self.code, self.message, self.details, self.headers = status, code, message, details or {}, headers


def body(code, message, details=None, **extra):
    return {'error': {'code': code, 'message': message, 'details': details or {}, **extra}}


def install(app: FastAPI):
    @app.exception_handler(ApiError)
    async def api_error(_request, error):
        return JSONResponse(body(error.code, error.message, error.details), status_code=error.status, headers=error.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid(_request, error):
        pointers = [{'pointer': '/' + '/'.join(str(p) for p in e['loc']), 'message': e['msg']} for e in error.errors()]
        return JSONResponse(body('invalid_request', 'The request is not valid', {'pointers': pointers}), status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request, error):
        code = 'not_found' if error.status_code == 404 else 'invalid_request'
        return JSONResponse(body(code, str(error.detail)), status_code=error.status_code)

    @app.exception_handler(Exception)
    async def internal(_request: Request, error):
        correlation = uuid.uuid4().hex[:12]
        log.exception('internal error %s', correlation)
        return JSONResponse(body('internal', 'Unexpected failure', correlation_id=correlation), status_code=500)
