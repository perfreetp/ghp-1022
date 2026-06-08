from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Budget, Experiment, UndoLog
from app.schemas import BudgetCreate, BudgetOut

router = APIRouter(prefix="/budgets", tags=["预算"])


def _log_undo(db, user_id, op, entity_type, entity_id, before, after):
    db.add(UndoLog(
        user_id=user_id, operation_type=op, entity_type=entity_type,
        entity_id=entity_id, before_data=before, after_data=after,
    ))
    db.flush()


@router.post("", response_model=BudgetOut, summary="记录成本/收入")
def create_budget(body: BudgetCreate, user_id: str = Query(...), db: Session = Depends(get_db)):
    exp = db.query(Experiment).filter(Experiment.id == body.experiment_id, Experiment.user_id == user_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在或无权限")
    if body.type not in ("cost", "income"):
        raise HTTPException(status_code=400, detail="type 必须为 cost 或 income")
    budget = Budget(
        experiment_id=body.experiment_id, type=body.type,
        amount=body.amount, description=body.description, user_id=user_id,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    _log_undo(db, user_id, "create", "budget", budget.id, {}, {"type": budget.type, "amount": budget.amount})
    db.commit()
    return budget


@router.get("/experiment/{exp_id}", response_model=list[BudgetOut], summary="查看实验预算")
def list_budgets(exp_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    exp = db.query(Experiment).filter(Experiment.id == exp_id, Experiment.user_id == user_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在或无权限")
    return db.query(Budget).filter(Budget.experiment_id == exp_id).order_by(Budget.recorded_at.desc()).all()


@router.get("/conversion-rate/{exp_id}", summary="计算转化率")
def get_conversion_rate(exp_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    exp = db.query(Experiment).filter(Experiment.id == exp_id, Experiment.user_id == user_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在或无权限")
    budgets = db.query(Budget).filter(Budget.experiment_id == exp_id).all()
    orders = exp.orders
    total_cost = sum(b.amount for b in budgets if b.type == "cost")
    total_income = sum(b.amount for b in budgets if b.type == "income")
    order_count = len(orders)
    if total_income > 0:
        conversion_rate = round(order_count / total_income * 100, 2)
    else:
        conversion_rate = 0.0
    return {
        "experiment_id": exp_id,
        "total_cost": total_cost,
        "total_income": total_income,
        "net_profit": total_income - total_cost,
        "order_count": order_count,
        "conversion_rate": conversion_rate,
    }
