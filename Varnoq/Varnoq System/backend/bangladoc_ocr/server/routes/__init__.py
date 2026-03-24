from fastapi import FastAPI

from bangladoc_ocr.server.routes.auth_routes import router as auth_router
from bangladoc_ocr.server.routes.corpus_routes import router as corpus_router
from bangladoc_ocr.server.routes.document_routes import router as document_router
from bangladoc_ocr.server.routes.ocr_routes import router as ocr_router
from bangladoc_ocr.server.routes.system_routes import router as system_router


def register_routes(app: FastAPI) -> None:
    app.include_router(system_router)
    app.include_router(corpus_router)
    app.include_router(auth_router)
    app.include_router(ocr_router)
    app.include_router(document_router)
