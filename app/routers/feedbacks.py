from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Feedback, Experiment
from app.schemas import FeedbackCreate, FeedbackOut

router = APIRouter(prefix="/feedbacks", tags=["反馈"])


@router.post("", response_model=FeedbackOut, summary="创建反馈")
def create_feedback(body: FeedbackCreate, user_id: str = Query(...), db: Session = Depends(get_db)):
    exp = db.query(Experiment).filter(Experiment.id == body.experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在")
    fb = Feedback(
        experiment_id=body.experiment_id, content=body.content,
        customer_name=body.customer_name, rating=body.rating, user_id=user_id,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


@router.get("/experiment/{exp_id}", summary="汇总客户留言")
def aggregate_feedbacks(exp_id: int, db: Session = Depends(get_db)):
    feedbacks = db.query(Feedback).filter(Feedback.experiment_id == exp_id).order_by(Feedback.created_at.desc()).all()
    total = len(feedbacks)
    avg_rating = (sum(f.rating for f in feedbacks) / total) if total > 0 else 0
    by_customer = {}
    for f in feedbacks:
        name = f.customer_name or "匿名"
        if name not in by_customer:
            by_customer[name] = []
        by_customer[name].append({"content": f.content, "rating": f.rating, "created_at": f.created_at.isoformat()})
    return {
        "experiment_id": exp_id,
        "total_feedbacks": total,
        "avg_rating": round(avg_rating, 2),
        "by_customer": by_customer,
        "items": [
            {"id": f.id, "content": f.content, "customer_name": f.customer_name, "rating": f.rating}
            for f in feedbacks
        ],
    }
