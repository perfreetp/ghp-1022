from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Reminder, Experiment
from app.schemas import ReminderCreate, ReminderOut

router = APIRouter(prefix="/reminders", tags=["提醒"])


@router.post("", response_model=ReminderOut, summary="创建提醒")
def create_reminder(body: ReminderCreate, user_id: str = Query(...), db: Session = Depends(get_db)):
    exp = db.query(Experiment).filter(Experiment.id == body.experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在")
    reminder = Reminder(
        experiment_id=body.experiment_id, type=body.type,
        message=body.message, remind_at=body.remind_at, user_id=user_id,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.get("/pending", response_model=list[ReminderOut], summary="获取待推送提醒")
def get_pending_reminders(user_id: str = Query(...), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    return (
        db.query(Reminder)
        .filter(Reminder.user_id == user_id, Reminder.sent == False, Reminder.remind_at <= now)
        .order_by(Reminder.remind_at.asc())
        .all()
    )


@router.post("/{reminder_id}/send", response_model=ReminderOut, summary="推送到期提醒")
def send_reminder(reminder_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == user_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在或无权限")
    if reminder.sent:
        raise HTTPException(status_code=400, detail="提醒已推送")
    reminder.sent = True
    db.commit()
    db.refresh(reminder)
    return reminder


@router.get("/experiment/{exp_id}", response_model=list[ReminderOut], summary="获取实验提醒列表")
def list_reminders(exp_id: int, db: Session = Depends(get_db)):
    return db.query(Reminder).filter(Reminder.experiment_id == exp_id).order_by(Reminder.remind_at.asc()).all()
