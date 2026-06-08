from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Review, Experiment, Budget, Order, Feedback
from app.schemas import ReviewOut

router = APIRouter(prefix="/reviews", tags=["复盘"])


@router.post("/generate/{exp_id}", response_model=ReviewOut, summary="生成复盘文本")
def generate_review(exp_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    exp = db.query(Experiment).filter(Experiment.id == exp_id, Experiment.user_id == user_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在或无权限")

    budgets = db.query(Budget).filter(Budget.experiment_id == exp_id).all()
    orders = db.query(Order).filter(Order.experiment_id == exp_id).all()
    feedbacks = db.query(Feedback).filter(Feedback.experiment_id == exp_id).all()

    total_cost = sum(b.amount for b in budgets if b.type == "cost")
    total_income = sum(b.amount for b in budgets if b.type == "income")
    net_profit = total_income - total_cost
    order_count = len(orders)
    feedback_count = len(feedbacks)
    avg_rating = (sum(f.rating for f in feedbacks) / feedback_count) if feedback_count > 0 else 0
    conversion_rate = (order_count / total_income * 100) if total_income > 0 else 0

    steps_info = ""
    if isinstance(exp.validation_steps, list):
        done_steps = sum(1 for s in exp.validation_steps if isinstance(s, dict) and s.get("done"))
        total_steps = len(exp.validation_steps)
        steps_info = f"验证步骤完成 {done_steps}/{total_steps}。"

    content = (
        f"【复盘报告：{exp.title}】\n"
        f"实验状态：{exp.status}\n"
        f"总成本：{total_cost:.2f}，总收入：{total_income:.2f}，净利润：{net_profit:.2f}\n"
        f"订单数：{order_count}，转化率：{conversion_rate:.2f}%\n"
        f"客户反馈 {feedback_count} 条，平均评分 {avg_rating:.1f}\n"
        f"{steps_info}\n"
        f"目标指标：{exp.target_metrics or '未设置'}\n"
    )

    summary = "盈利" if net_profit > 0 else ("亏损" if net_profit < 0 else "持平")
    if exp.status == "completed":
        summary += "，实验已完成"
    elif exp.status == "failed":
        summary += "，实验已失败"
    else:
        summary += "，实验进行中"

    review = Review(
        experiment_id=exp_id, content=content,
        conversion_rate=round(conversion_rate, 2),
        summary=summary, user_id=user_id,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.get("/experiment/{exp_id}", response_model=list[ReviewOut], summary="获取实验的所有复盘")
def list_reviews(exp_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    exp = db.query(Experiment).filter(Experiment.id == exp_id, Experiment.user_id == user_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在或无权限")
    return db.query(Review).filter(Review.experiment_id == exp_id, Review.user_id == user_id).order_by(Review.created_at.desc()).all()


@router.get("/{review_id}", response_model=ReviewOut, summary="获取复盘详情")
def get_review(review_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == review_id, Review.user_id == user_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="复盘不存在或无权限")
    return review
