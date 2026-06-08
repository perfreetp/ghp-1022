from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Idea, UndoLog
from app.schemas import IdeaCreate, IdeaUpdate, IdeaOut

router = APIRouter(prefix="/ideas", tags=["点子"])


def _log_undo(db: Session, user_id: str, op: str, entity_type: str, entity_id: int, before: dict, after: dict):
    log = UndoLog(
        user_id=user_id,
        operation_type=op,
        entity_type=entity_type,
        entity_id=entity_id,
        before_data=before,
        after_data=after,
    )
    db.add(log)
    db.flush()


@router.post("", response_model=IdeaOut, summary="创建点子")
def create_idea(body: IdeaCreate, user_id: str = Query(..., description="用户ID"), db: Session = Depends(get_db)):
    idea = Idea(title=body.title, description=body.description, category=body.category, user_id=user_id)
    db.add(idea)
    db.commit()
    db.refresh(idea)
    _log_undo(db, user_id, "create", "idea", idea.id, {}, {"title": idea.title, "description": idea.description, "category": idea.category})
    db.commit()
    return idea


@router.get("", response_model=list[IdeaOut], summary="查询点子列表")
def list_ideas(
    user_id: str = Query(..., description="用户ID"),
    category: Optional[str] = Query(None, description="按分类筛选"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(Idea).filter(Idea.user_id == user_id)
    if category:
        q = q.filter(Idea.category == category)
    return q.order_by(Idea.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{idea_id}", response_model=IdeaOut, summary="获取点子详情")
def get_idea(idea_id: int, db: Session = Depends(get_db)):
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="点子不存在")
    return idea


@router.put("/{idea_id}", response_model=IdeaOut, summary="更新点子")
def update_idea(
    idea_id: int,
    body: IdeaUpdate,
    user_id: str = Query(..., description="用户ID"),
    db: Session = Depends(get_db),
):
    idea = db.query(Idea).filter(Idea.id == idea_id, Idea.user_id == user_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="点子不存在或无权限")
    before = {"title": idea.title, "description": idea.description, "category": idea.category}
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(idea, k, v)
    db.commit()
    db.refresh(idea)
    after = {"title": idea.title, "description": idea.description, "category": idea.category}
    _log_undo(db, user_id, "update", "idea", idea.id, before, after)
    db.commit()
    return idea


@router.delete("/{idea_id}", summary="删除点子")
def delete_idea(idea_id: int, user_id: str = Query(..., description="用户ID"), db: Session = Depends(get_db)):
    idea = db.query(Idea).filter(Idea.id == idea_id, Idea.user_id == user_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="点子不存在或无权限")
    before = {"title": idea.title, "description": idea.description, "category": idea.category}
    db.delete(idea)
    _log_undo(db, user_id, "delete", "idea", idea_id, before, {})
    db.commit()
    return {"detail": "已删除"}
