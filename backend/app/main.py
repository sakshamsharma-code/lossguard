"""
LossGuard — FastAPI entrypoint. Run with: uvicorn app.main:app --reload
"""

from datetime import date
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import SessionLocal
from app.db import models
from app.services.case_service import build_case_evidence, list_case_summaries
from app.explain.explain_service import get_case_explanation
from app.models.schemas import (
    CaseEvidence, CaseSummary, DecisionRequest, DecisionResult,
    DashboardStats, ExplainResponse,
)

app = FastAPI(title="LossGuard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "service": "LossGuard API"}


@app.get("/cases", response_model=list[CaseSummary])
def get_cases(limit: int = 150):
    try:
        return list_case_summaries(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/case/{return_id}", response_model=CaseEvidence)
def get_case(return_id: str):
    try:
        return build_case_evidence(return_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/decision/{return_id}", response_model=DecisionResult)
def log_decision(return_id: str, decision: DecisionRequest):
    if decision.action not in ("approve", "reject", "verify"):
        raise HTTPException(status_code=400, detail="action must be approve, reject, or verify")

    db = SessionLocal()
    try:
        ret = db.query(models.Return).filter(models.Return.return_id == return_id).first()
        if ret is None:
            raise HTTPException(status_code=404, detail=f"Return {return_id} not found")

        log = models.DecisionLog(
            return_id=return_id,
            action=decision.action,
            reviewer_note=decision.reviewer_note,
            logged_at=date.today(),
        )
        db.add(log)
        db.commit()

        return DecisionResult(
            return_id=return_id, action=decision.action,
            reviewer_note=decision.reviewer_note, logged_at=date.today(),
        )
    finally:
        db.close()


@app.get("/stats", response_model=DashboardStats)
def get_stats():
    db = SessionLocal()
    try:
        total_cases = db.query(models.Return).count()

        # Perf fix: computing full evidence for EVERY case (1000+) on every
        # /stats call was exhausting the DB connection pool. Cap the sample
        # used for the dashboard summary — good enough for a live demo,
        # avoids rebuilding evidence for the entire dataset on each request.
        sample_limit = min(total_cases, 150)
        summaries = list_case_summaries(limit=sample_limit)
        high_risk = sum(1 for s in summaries if s.decision_tier == "manual_review")
        medium_risk = sum(1 for s in summaries if s.decision_tier == "verify")
        total_expected_loss = sum(s.expected_loss for s in summaries)

        from app.graph.ring_detector import get_full_graph
        import networkx as nx
        graph = get_full_graph()
        potential_rings = sum(1 for c in nx.connected_components(graph) if len(c) > 1)

        return DashboardStats(
            total_cases=total_cases,
            high_risk_count=high_risk,
            medium_risk_count=medium_risk,
            potential_rings=potential_rings,
            total_expected_loss_today=round(total_expected_loss, 2),
        )
    finally:
        db.close()


@app.post("/explain/{return_id}", response_model=ExplainResponse)
def explain_case(return_id: str):
    try:
        evidence = build_case_evidence(return_id)
        summary = get_case_explanation(evidence)
        return ExplainResponse(return_id=return_id, summary=summary)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))