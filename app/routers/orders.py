from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Order, Experiment, UndoLog
from app.schemas import OrderCreate, OrderBindSource, OrderOut
from app.services.permissions import require_role

router = APIRouter(prefix="/orders", tags=["订单"])


def _log_undo(db, user_id, op, entity_type, entity_id, before, after):
    db.add(UndoLog(
        user_id=user_id, operation_type=op, entity_type=entity_type,
        entity_id=entity_id, before_data=before, after_data=after,
    ))
    db.flush()


@router.post("", response_model=OrderOut, summary="创建订单")
def create_order(body: OrderCreate, user_id: str = Query(...), db: Session = Depends(get_db)):
    require_role(body.experiment_id, user_id, "editor", db)
    order = Order(
        experiment_id=body.experiment_id, source=body.source,
        amount=body.amount, status=body.status,
        customer_info=body.customer_info if isinstance(body.customer_info, dict) else {},
        user_id=user_id,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    _log_undo(db, user_id, "create", "order", order.id, {}, {"source": order.source, "amount": order.amount})
    db.commit()
    return order


@router.get("/experiment/{exp_id}", response_model=list[OrderOut], summary="查看实验订单")
def list_orders(exp_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    require_role(exp_id, user_id, "viewer", db)
    return db.query(Order).filter(Order.experiment_id == exp_id).order_by(Order.created_at.desc()).all()


@router.put("/{order_id}/bind", response_model=OrderOut, summary="绑定订单来源")
def bind_source(order_id: int, body: OrderBindSource, user_id: str = Query(...), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    require_role(order.experiment_id, user_id, "editor", db)
    before = {"source": order.source}
    order.source = body.source
    db.commit()
    db.refresh(order)
    _log_undo(db, user_id, "update", "order", order.id, before, {"source": order.source})
    db.commit()
    return order
