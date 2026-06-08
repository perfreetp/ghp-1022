from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Idea, Experiment, Budget, Order, Feedback, UndoLog
from app.schemas import (
    ExperimentCreate, ExperimentUpdate, MetricsUpdate, StepsUpdate,
    ExperimentOut, ExperimentCompare,
)

router = APIRouter(prefix="/experiments", tags=["实验"])


def _log_undo(db: Session, user_id: str, op: str, entity_type: str, entity_id: int, before: dict, after: dict):
    log = UndoLog(
        user_id=user_id, operation_type=op, entity_type=entity_type,
        entity_id=entity_id, before_data=before, after_data=after,
    )
    db.add(log)
    db.flush()


@router.post("", response_model=ExperimentOut, summary="创建实验")
def create_experiment(body: ExperimentCreate, user_id: str = Query(...), db: Session = Depends(get_db)):
    idea = db.query(Idea).filter(Idea.id == body.idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="关联点子不存在")
    exp = Experiment(idea_id=body.idea_id, title=body.title, user_id=user_id)
    db.add(exp)
    db.commit()
    db.refresh(exp)
    _log_undo(db, user_id, "create", "experiment", exp.id, {}, {"title": exp.title, "status": exp.status})
    db.commit()
    return exp


@router.get("", response_model=list[ExperimentOut], summary="实验列表")
def list_experiments(
    user_id: str = Query(...),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(Experiment).filter(Experiment.user_id == user_id)
    if status:
        q = q.filter(Experiment.status == status)
    return q.order_by(Experiment.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/history", response_model=list[ExperimentOut], summary="查询历史实验")
def query_history(
    user_id: str = Query(...),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(Experiment).filter(Experiment.user_id == user_id)
    if status:
        q = q.filter(Experiment.status == status)
    if category:
        q = q.join(Idea, Experiment.idea_id == Idea.id).filter(Idea.category == category)
    return q.order_by(Experiment.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/compare", response_model=list[ExperimentCompare], summary="比较同类项目")
def compare_experiments(
    user_id: str = Query(...),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Experiment).filter(Experiment.user_id == user_id)
    if category:
        q = q.join(Idea, Experiment.idea_id == Idea.id).filter(Idea.category == category)
    experiments = q.all()
    results = []
    for exp in experiments:
        total_cost = sum(b.amount for b in exp.budgets if b.type == "cost")
        total_income = sum(b.amount for b in exp.budgets if b.type == "income")
        order_count = len(exp.orders)
        conversion_rate = (order_count / total_income * 100) if total_income > 0 else 0
        results.append(ExperimentCompare(
            experiment_id=exp.id, title=exp.title, status=exp.status,
            total_cost=total_cost, total_income=total_income,
            net_profit=total_income - total_cost, conversion_rate=round(conversion_rate, 2),
        ))
    return results


@router.get("/{exp_id}", response_model=ExperimentOut, summary="获取实验详情")
def get_experiment(exp_id: int, db: Session = Depends(get_db)):
    exp = db.query(Experiment).filter(Experiment.id == exp_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在")
    return exp


@router.put("/{exp_id}/metrics", response_model=ExperimentOut, summary="设置目标指标")
def update_metrics(
    exp_id: int, body: MetricsUpdate, user_id: str = Query(...), db: Session = Depends(get_db),
):
    exp = db.query(Experiment).filter(Experiment.id == exp_id, Experiment.user_id == user_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在或无权限")
    before = {"target_metrics": exp.target_metrics}
    exp.target_metrics = body.target_metrics
    db.commit()
    db.refresh(exp)
    _log_undo(db, user_id, "update", "experiment", exp.id, before, {"target_metrics": exp.target_metrics})
    db.commit()
    return exp


@router.put("/{exp_id}/steps", response_model=ExperimentOut, summary="拆分验证步骤")
def update_steps(
    exp_id: int, body: StepsUpdate, user_id: str = Query(...), db: Session = Depends(get_db),
):
    exp = db.query(Experiment).filter(Experiment.id == exp_id, Experiment.user_id == user_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在或无权限")
    before = {"validation_steps": exp.validation_steps}
    exp.validation_steps = body.validation_steps
    db.commit()
    db.refresh(exp)
    _log_undo(db, user_id, "update", "experiment", exp.id, before, {"validation_steps": exp.validation_steps})
    db.commit()
    return exp


@router.get("/{exp_id}/status", summary="判断实验状态")
def get_experiment_status(exp_id: int, db: Session = Depends(get_db)):
    exp = db.query(Experiment).filter(Experiment.id == exp_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在")
    total_cost = sum(b.amount for b in exp.budgets if b.type == "cost")
    total_income = sum(b.amount for b in exp.budgets if b.type == "income")
    feedback_count = len(exp.feedbacks)
    order_count = len(exp.orders)
    all_steps_done = (
        isinstance(exp.validation_steps, list)
        and len(exp.validation_steps) > 0
        and all(s.get("done", False) for s in exp.validation_steps if isinstance(s, dict))
    )
    status = exp.status
    if status == "running":
        if total_income >= total_cost and all_steps_done:
            status = "completed"
        elif total_cost > 0 and total_income == 0 and feedback_count == 0:
            status = "failed"
    return {
        "experiment_id": exp.id,
        "current_status": exp.status,
        "suggested_status": status,
        "total_cost": total_cost,
        "total_income": total_income,
        "order_count": order_count,
        "feedback_count": feedback_count,
        "all_steps_done": all_steps_done,
    }


@router.put("/{exp_id}", response_model=ExperimentOut, summary="更新实验")
def update_experiment(
    exp_id: int, body: ExperimentUpdate, user_id: str = Query(...), db: Session = Depends(get_db),
):
    exp = db.query(Experiment).filter(Experiment.id == exp_id, Experiment.user_id == user_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在或无权限")
    before = {"title": exp.title, "status": exp.status}
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(exp, k, v)
    if body.status == "running" and not exp.started_at:
        from datetime import datetime
        exp.started_at = datetime.utcnow()
    if body.status in ("completed", "failed") and not exp.ended_at:
        from datetime import datetime
        exp.ended_at = datetime.utcnow()
    db.commit()
    db.refresh(exp)
    _log_undo(db, user_id, "update", "experiment", exp.id, before, {"title": exp.title, "status": exp.status})
    db.commit()
    return exp
