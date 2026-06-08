from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Attachment, UndoLog
from app.schemas import AttachmentCreate, AttachmentOut

router = APIRouter(prefix="/attachments", tags=["附件"])


def _log_undo(db, user_id, op, entity_type, entity_id, before, after):
    db.add(UndoLog(
        user_id=user_id, operation_type=op, entity_type=entity_type,
        entity_id=entity_id, before_data=before, after_data=after,
    ))
    db.flush()


@router.post("", response_model=AttachmentOut, summary="保存附件说明")
def create_attachment(body: AttachmentCreate, user_id: str = Query(...), db: Session = Depends(get_db)):
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
        "description": att.description,
    })
    db.commit()
    return att


@router.get("/{entity_type}/{entity_id}", response_model=list[AttachmentOut], summary="获取附件列表")
def list_attachments(entity_type: str, entity_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    return (
        db.query(Attachment)
        .filter(Attachment.entity_type == entity_type, Attachment.entity_id == entity_id, Attachment.user_id == user_id)
        .order_by(Attachment.created_at.desc())
        .all()
    )


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
