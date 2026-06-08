from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Collaborator, Experiment, UndoLog
from app.schemas import CollaboratorCreate, CollaboratorUpdate, CollaboratorOut
from app.services.permissions import require_role, get_user_role

router = APIRouter(prefix="/collaborators", tags=["协作者"])


def _log_undo(db, user_id, op, entity_type, entity_id, before, after):
    db.add(UndoLog(
        user_id=user_id, operation_type=op, entity_type=entity_type,
        entity_id=entity_id, before_data=before, after_data=after,
    ))
    db.flush()


@router.post("", response_model=CollaboratorOut, summary="设置协作者权限")
def add_collaborator(body: CollaboratorCreate, user_id: str = Query(...), db: Session = Depends(get_db)):
    require_role(body.experiment_id, user_id, "owner", db)
    existing = (
        db.query(Collaborator)
        .filter(Collaborator.experiment_id == body.experiment_id, Collaborator.user_id == body.user_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="该用户已是协作者")
    collab = Collaborator(
        experiment_id=body.experiment_id, user_id=body.user_id, role=body.role,
    )
    db.add(collab)
    db.commit()
    db.refresh(collab)
    _log_undo(db, user_id, "create", "collaborator", collab.id, {}, {"experiment_id": collab.experiment_id, "user_id": collab.user_id, "role": collab.role})
    db.commit()
    return collab


@router.get("/experiment/{exp_id}", response_model=list[CollaboratorOut], summary="获取协作者列表")
def list_collaborators(exp_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    require_role(exp_id, user_id, "viewer", db)
    return db.query(Collaborator).filter(Collaborator.experiment_id == exp_id).all()


@router.put("/{collab_id}", response_model=CollaboratorOut, summary="更新协作者权限")
def update_collaborator(
    collab_id: int, body: CollaboratorUpdate, user_id: str = Query(...), db: Session = Depends(get_db),
):
    collab = db.query(Collaborator).filter(Collaborator.id == collab_id).first()
    if not collab:
        raise HTTPException(status_code=404, detail="协作者记录不存在")
    require_role(collab.experiment_id, user_id, "owner", db)
    before = {"role": collab.role}
    collab.role = body.role
    db.commit()
    db.refresh(collab)
    _log_undo(db, user_id, "update", "collaborator", collab.id, before, {"role": collab.role})
    db.commit()
    return collab


@router.delete("/{collab_id}", summary="移除协作者")
def remove_collaborator(collab_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    collab = db.query(Collaborator).filter(Collaborator.id == collab_id).first()
    if not collab:
        raise HTTPException(status_code=404, detail="协作者记录不存在")
    require_role(collab.experiment_id, user_id, "owner", db)
    before = {"experiment_id": collab.experiment_id, "user_id": collab.user_id, "role": collab.role}
    db.delete(collab)
    _log_undo(db, user_id, "delete", "collaborator", collab_id, before, {})
    db.commit()
    return {"detail": "已移除"}
