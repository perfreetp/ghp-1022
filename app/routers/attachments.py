from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Attachment, UndoLog, Idea, Experiment
from app.schemas import AttachmentCreate, AttachmentUpdate, AttachmentOut

router = APIRouter(prefix="/attachments", tags=["附件"])


def _log_undo(db, user_id, op, entity_type, entity_id, before, after):
    db.add(UndoLog(
        user_id=user_id, operation_type=op, entity_type=entity_type,
        entity_id=entity_id, before_data=before, after_data=after,
    ))
    db.flush()


def _check_entity_owner(entity_type: str, entity_id: int, user_id: str, db: Session):
    if entity_type == "idea":
        owner = db.query(Idea).filter(Idea.id == entity_id, Idea.user_id == user_id).first()
    elif entity_type == "experiment":
        owner = db.query(Experiment).filter(Experiment.id == entity_id, Experiment.user_id == user_id).first()
    else:
        raise HTTPException(status_code=400, detail=f"不支持对 {entity_type} 类型挂载附件")
    if not owner:
        raise HTTPException(status_code=404, detail="所属资源不存在或无权限")


@router.post("", response_model=AttachmentOut, summary="保存附件说明")
def create_attachment(body: AttachmentCreate, user_id: str = Query(...), db: Session = Depends(get_db)):
    _check_entity_owner(body.entity_type, body.entity_id, user_id, db)
    att = Attachment(
        entity_type=body.entity_type, entity_id=body.entity_id,
        file_name=body.file_name, file_path=body.file_path,
        description=body.description, user_id=user_id,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    _log_undo(db, user_id, "create", "attachment", att.id, {}, {
        "entity_type": att.entity_type, "entity_id": att.entity_id,
        "file_name": att.file_name, "file_path": att.file_path,
        "description": att.description, "user_id": att.user_id,
    })
    db.commit()
    return att


@router.get("/{entity_type}/{entity_id}", response_model=list[AttachmentOut], summary="获取附件列表")
def list_attachments(entity_type: str, entity_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    _check_entity_owner(entity_type, entity_id, user_id, db)
    return (
        db.query(Attachment)
        .filter(Attachment.entity_type == entity_type, Attachment.entity_id == entity_id)
        .order_by(Attachment.created_at.desc())
        .all()
    )


@router.put("/{att_id}", response_model=AttachmentOut, summary="修改附件说明")
def update_attachment(att_id: int, body: AttachmentUpdate, user_id: str = Query(...), db: Session = Depends(get_db)):
    att = db.query(Attachment).filter(Attachment.id == att_id, Attachment.user_id == user_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在或无权限")
    before = {
        "file_name": att.file_name, "file_path": att.file_path,
        "description": att.description,
    }
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(att, k, v)
    db.commit()
    db.refresh(att)
    after = {
        "file_name": att.file_name, "file_path": att.file_path,
        "description": att.description,
    }
    _log_undo(db, user_id, "update", "attachment", att.id, before, after)
    db.commit()
    return att


@router.delete("/{att_id}", summary="删除附件")
def delete_attachment(att_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    att = db.query(Attachment).filter(Attachment.id == att_id, Attachment.user_id == user_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在或无权限")
    before = {
        "entity_type": att.entity_type, "entity_id": att.entity_id,
        "file_name": att.file_name, "file_path": att.file_path,
        "description": att.description, "user_id": att.user_id,
    }
    db.delete(att)
    _log_undo(db, user_id, "delete", "attachment", att_id, before, {})
    db.commit()
    return {"detail": "已删除"}
