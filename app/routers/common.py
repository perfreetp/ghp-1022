from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import (
    Experiment, Budget, Order, Idea, UndoLog, Collaborator, Attachment, Review, Feedback, Reminder,
)
from app.schemas import (
    LeaderboardItem, SyncProgress, ExperimentOut, IdeaOut, UndoRequest, UndoLogOut,
)

router = APIRouter(tags=["通用"])


@router.get("/leaderboard", response_model=list[LeaderboardItem], summary="输出排行榜数据")
def get_leaderboard(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    rows = (
        db.query(Experiment.user_id, func.count(Experiment.id).label("total"))
        .group_by(Experiment.user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    result = []
    for user_id, total_exp in rows:
        experiments = db.query(Experiment).filter(Experiment.user_id == user_id).all()
        completed = sum(1 for e in experiments if e.status == "completed")
        exp_ids = [e.id for e in experiments]
        budgets = db.query(Budget).filter(Budget.experiment_id.in_(exp_ids)).all() if exp_ids else []
        total_cost = sum(b.amount for b in budgets if b.type == "cost")
        total_income = sum(b.amount for b in budgets if b.type == "income")
        orders = db.query(Order).filter(Order.experiment_id.in_(exp_ids)).all() if exp_ids else []
        order_count = len(orders)
        avg_conversion = (order_count / total_income * 100) if total_income > 0 else 0
        result.append(LeaderboardItem(
            user_id=user_id,
            total_experiments=total_exp,
            completed_experiments=completed,
            total_income=total_income,
            total_cost=total_cost,
            net_profit=total_income - total_cost,
            avg_conversion_rate=round(avg_conversion, 2),
        ))
    result.sort(key=lambda x: x.net_profit, reverse=True)
    return result


@router.post("/undo", summary="撤销误操作")
def undo_operation(body: UndoRequest, user_id: str = Query(...), db: Session = Depends(get_db)):
    if body.undo_log_id:
        log = db.query(UndoLog).filter(UndoLog.id == body.undo_log_id, UndoLog.user_id == user_id).first()
    else:
        log = (
            db.query(UndoLog)
            .filter(UndoLog.user_id == user_id)
            .order_by(UndoLog.created_at.desc())
            .first()
        )
    if not log:
        raise HTTPException(status_code=404, detail="无可撤销的操作")
    entity_map = {
        "idea": Idea,
        "experiment": Experiment,
        "budget": Budget,
        "order": Order,
        "attachment": Attachment,
        "collaborator": Collaborator,
    }
    model_cls = entity_map.get(log.entity_type)
    if not model_cls:
        raise HTTPException(status_code=400, detail=f"不支持撤销 {log.entity_type} 类型")
    if log.operation_type == "create":
        entity = db.query(model_cls).filter(model_cls.id == log.entity_id).first()
        if entity:
            db.delete(entity)
    elif log.operation_type == "delete":
        obj_data = dict(log.before_data)
        if obj_data:
            obj_data["id"] = log.entity_id
            if "user_id" not in obj_data:
                obj_data["user_id"] = user_id
            new = model_cls(**obj_data)
            db.add(new)
    elif log.operation_type == "update":
        entity = db.query(model_cls).filter(model_cls.id == log.entity_id).first()
        if entity:
            for k, v in log.before_data.items():
                setattr(entity, k, v)
    db.delete(log)
    db.commit()
    return {"detail": "已撤销", "undone_operation": log.operation_type, "entity_type": log.entity_type}


@router.get("/undo/logs", response_model=list[UndoLogOut], summary="查询撤销日志")
def list_undo_logs(user_id: str = Query(...), skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return (
        db.query(UndoLog)
        .filter(UndoLog.user_id == user_id)
        .order_by(UndoLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/sync/progress", response_model=SyncProgress, summary="按用户同步进度")
def sync_progress(user_id: str = Query(...), db: Session = Depends(get_db)):
    own_experiments = db.query(Experiment).filter(Experiment.user_id == user_id).all()
    collab_exp_ids = [c.experiment_id for c in db.query(Collaborator).filter(Collaborator.user_id == user_id).all()]
    collab_experiments = db.query(Experiment).filter(Experiment.id.in_(collab_exp_ids)).all() if collab_exp_ids else []
    all_exp_ids = set(e.id for e in own_experiments) | set(collab_exp_ids)
    all_experiments = own_experiments[:]
    seen = set(e.id for e in own_experiments)
    for e in collab_experiments:
        if e.id not in seen:
            all_experiments.append(e)
            seen.add(e.id)
    idea_ids = set(e.idea_id for e in all_experiments if e.idea_id)
    ideas = db.query(Idea).filter(Idea.id.in_(idea_ids)).all() if idea_ids else []
    return SyncProgress(
        user_id=user_id,
        experiments=[ExperimentOut.model_validate(e) for e in all_experiments],
        ideas=[IdeaOut.model_validate(i) for i in ideas],
        last_sync=datetime.utcnow(),
    )
