from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

from src.components import Generator, Retriever
from src.config import AppConfig, load_config
from src.factory import build_pipeline, build_retriever
from src.models import Ticket
from src.pipeline import SupportPipeline


ROOT = Path(__file__).parent
DEFAULT_AUDIT_PATH = ROOT / "runtime" / "api_audit.jsonl"


class TicketRequest(BaseModel):
    request_id: str = Field(min_length=1)
    channel: str = Field(default="api", min_length=1)
    text: str


class TicketResponse(BaseModel):
    request_id: str
    topic: str
    risk: str
    confidence: float | None
    evidence_ids: list[str] = Field(default_factory=list)
    decision: str
    route: str
    draft: str | None
    reason: str | None
    generator_status: str | None


def create_app(
    generator: Generator | None = None,
    retriever: Retriever | None = None,
    audit_path: Path | None = None,
    config: AppConfig | None = None,
) -> FastAPI:
    """Создать FastAPI-оболочку вокруг существующего синхронного конвейера."""

    resolved_config = config or load_config()
    if generator is None and retriever is None:
        pipeline = build_pipeline(resolved_config, audit_path or DEFAULT_AUDIT_PATH)
    else:
        pipeline = SupportPipeline(
            ROOT / "data" / "kb.json",
            audit_path or DEFAULT_AUDIT_PATH,
            generator=generator,
            retriever=retriever or build_retriever(resolved_config),
        )
    app = FastAPI(title="Ticket Automation PoC", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        status = "ok" if pipeline.retriever.status == "available" else "degraded"
        return {
            "status": status,
            "retriever_backend": pipeline.retriever.backend,
            "generator_backend": pipeline.generator.backend,
        }

    @app.post("/tickets", response_model=TicketResponse)
    def process_ticket(payload: TicketRequest) -> TicketResponse:
        result = pipeline.process(
            Ticket(
                text=payload.text,
                channel=payload.channel,
                ticket_id=payload.request_id,
            )
        )
        return TicketResponse(
            request_id=str(result["request_id"]),
            topic=str(result["topic"]),
            risk=str(result["risk"]),
            confidence=result.get("confidence"),
            evidence_ids=list(result.get("evidence", [])),
            decision=str(result["decision"]),
            route=str(result["route"]),
            draft=result.get("draft"),
            reason=result.get("reason"),
            generator_status=result.get("generator_status"),
        )

    return app


app = create_app()
