from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Attachment, UndoLog, Idea, Experiment, Collaborator
from app.schemas import AttachmentCreate, AttachmentUpdate, AttachmentOut, AttachmentListResponse
from app.services.permissions import require_role, get_user_role

router = APIRouter(prefix="/attachments", tags=["附件"])


def _log_undo(db, user_id, op, entity_type, entity_id, before, after):
    db.add(UndoLog(
        user_id=user_id, operation_type=op, entity_type=entity_type,
        entity_id=entity_id, before_data=before, after_data=after,
    ))
    db.flush()


def _resolve_exp_id(entity_type: str, entity_id: int, db: Session) -> Optional[int]:
    if entity_type == "experiment":
        return entity_id
    elif entity_type == "idea":
        exp = db.query(Experiment).filter(Experiment.idea_id == entity_id).first()
        return exp.id if exp else None
    return None


def _require_entity_role(entity_type: str, entity_id: int, user_id: str, required_role: str, db: Session):
    if entity_type not in ("idea", "experiment"):
        raise HTTPException(status_code=400, detail=f"不支持对 {entity_type} 类型挂载附件")
    if entity_type == "idea":
        idea = db.query(Idea).filter(Idea.id == entity_id).first()
        if not idea:
            raise HTTPException(status_code=404, detail="所属资源不存在")
        exp = db.query(Experiment).filter(Experiment.idea_id == entity_id).first()
        if exp:
            require_role(exp.id, user_id, required_role, db)
        elif idea.user_id != user_id:
            raise HTTPException(status_code=403, detail="权限不足")
    else:
        require_role(entity_id, user_id, required_role, db)


def _check_attachment_permission(att: Attachment, user_id: str, required_role: str, db: Session):
    exp_id = _resolve_exp_id(att.entity_type, att.entity_id, db)
    if exp_id:
        require_role(exp_id, user_id, required_role, db)
    elif att.user_id == user_id:
        return
    else:
        raise HTTPException(status_code=403, detail="权限不足")


def _find_all_versions(root_id: int, db: Session) -> list:
    all_versions = []
    root = db.query(Attachment).filter(Attachment.id == root_id).first()
    if root:
        all_versions.append(root)
    stack = [root_id]
    while stack:
        pid = stack.pop()
        children = db.query(Attachment).filter(Attachment.parent_id == pid).all()
        for c in children:
            all_versions.append(c)
            stack.append(c.id)
    return sorted(all_versions, key=lambda x: x.version)


@router.post("", response_model=AttachmentOut, summary="保存附件说明")
def create_attachment(body: AttachmentCreate, user_id: str = Query(...), db: Session = Depends(get_db)):
    _require_entity_role(body.entity_type, body.entity_id, user_id, "editor", db)
    version = 1
    is_current = True
    if body.parent_id:
        parent = db.query(Attachment).filter(Attachment.id == body.parent_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail="父版本不存在")
        db.query(Attachment).filter(
            Attachment.parent_id == body.parent_id, Attachment.is_current == True
        ).update({"is_current": False})
        parent.is_current = False
        version = parent.version + 1
    att = Attachment(
        entity_type=body.entity_type, entity_id=body.entity_id,
        file_name=body.file_name, file_path=body.file_path,
        description=body.description, version=version,
        change_note=body.change_note, is_current=is_current,
        parent_id=body.parent_id, user_id=user_id,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    _log_undo(db, user_id, "create", "attachment", att.id, {}, {
        "entity_type": att.entity_type, "entity_id": att.entity_id,
        "file_name": att.file_name, "file_path": att.file_path,
        "description": att.description, "version": att.version,
        "change_note": att.change_note, "is_current": att.is_current,
        "parent_id": att.parent_id, "user_id": att.user_id,
    })
    db.commit()
    return att


@router.get("/search", response_model=AttachmentListResponse, summary="筛选检索附件")
def search_attachments(
    user_id: str = Query(...),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[int] = Query(None),
    file_name: Optional[str] = Query(None),
    created_after: Optional[datetime] = Query(None),
    created_before: Optional[datetime] = Query(None),
    is_current: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    own_exp_ids = [e.id for e in db.query(Experiment).filter(Experiment.user_id == user_id).all()]
    collab_exp_ids = [c.experiment_id for c in db.query(Collaborator).filter(Collaborator.user_id == user_id).all()]
    accessible_exp_ids = set(own_exp_ids + collab_exp_ids)
    accessible_idea_ids = [e.idea_id for e in db.query(Experiment).filter(Experiment.id.in_(accessible_exp_ids)).all() if e.idea_id]

    if entity_type == "experiment" and entity_id is not None:
        if entity_id not in accessible_exp_ids:
            return AttachmentListResponse(total=0, items=[], skip=skip, limit=limit)
        q = db.query(Attachment).filter(Attachment.entity_type == entity_type, Attachment.entity_id == entity_id)
    elif entity_type == "idea" and entity_id is not None:
        if entity_id not in set(accessible_idea_ids):
            return AttachmentListResponse(total=0, items=[], skip=skip, limit=limit)
        q = db.query(Attachment).filter(Attachment.entity_type == entity_type, Attachment.entity_id == entity_id)
    else:
        exp_atts = db.query(Attachment).filter(
            Attachment.entity_type == "experiment", Attachment.entity_id.in_(accessible_exp_ids)
        )
        idea_atts = db.query(Attachment).filter(
            Attachment.entity_type == "idea", Attachment.entity_id.in_(accessible_idea_ids)
        ) if accessible_idea_ids else db.query(Attachment).filter(Attachment.id < 0)
        all_ids = [a.id for a in exp_atts.all()] + [a.id for a in idea_atts.all()]
        q = db.query(Attachment).filter(Attachment.id.in_(all_ids)) if all_ids else db.query(Attachment).filter(Attachment.id < 0)

    if file_name:
        q = q.filter(Attachment.file_name.contains(file_name))
    if created_after:
        q = q.filter(Attachment.created_at >= created_after)
    if created_before:
        q = q.filter(Attachment.created_at <= created_before)
    if is_current is not None:
        q = q.filter(Attachment.is_current == is_current)
    total = q.count()
    items = q.order_by(Attachment.created_at.desc()).offset(skip).limit(limit).all()
    return AttachmentListResponse(total=total, items=items, skip=skip, limit=limit)


@router.get("/list/{entity_type}/{entity_id}", response_model=AttachmentListResponse, summary="获取附件列表")
def list_attachments(
    entity_type: str, entity_id: int,
    user_id: str = Query(...),
    is_current: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    _require_entity_role(entity_type, entity_id, user_id, "viewer", db)
    q = db.query(Attachment).filter(
        Attachment.entity_type == entity_type, Attachment.entity_id == entity_id
    )
    if is_current is not None:
        q = q.filter(Attachment.is_current == is_current)
    total = q.count()
    items = q.order_by(Attachment.created_at.desc()).offset(skip).limit(limit).all()
    return AttachmentListResponse(total=total, items=items, skip=skip, limit=limit)


@router.get("/versions/{att_id}", response_model=list[AttachmentOut], summary="获取附件版本列表")
def list_versions(att_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    att = db.query(Attachment).filter(Attachment.id == att_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")
    _check_attachment_permission(att, user_id, "viewer", db)
    root = att
    while root.parent_id is not None:
        parent = db.query(Attachment).filter(Attachment.id == root.parent_id).first()
        if not parent:
            break
        root = parent
    return _find_all_versions(root.id, db)


@router.get("/current/{entity_type}/{entity_id}", response_model=Optional[AttachmentOut], summary="获取当前版本")
def get_current_version(entity_type: str, entity_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    _require_entity_role(entity_type, entity_id, user_id, "viewer", db)
    return (
        db.query(Attachment)
        .filter(Attachment.entity_type == entity_type, Attachment.entity_id == entity_id, Attachment.is_current == True)
        .order_by(Attachment.version.desc())
        .first()
    )


@router.get("/detail/{att_id}", response_model=AttachmentOut, summary="获取附件版本详情")
def get_attachment_detail(att_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    att = db.query(Attachment).filter(Attachment.id == att_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")
    _check_attachment_permission(att, user_id, "viewer", db)
    return att


@router.put("/{att_id}", response_model=AttachmentOut, summary="修改附件说明")
def update_attachment(att_id: int, body: AttachmentUpdate, user_id: str = Query(...), db: Session = Depends(get_db)):
    att = db.query(Attachment).filter(Attachment.id == att_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")
    _check_attachment_permission(att, user_id, "editor", db)
    before = {
        "file_name": att.file_name, "file_path": att.file_path,
        "description": att.description, "change_note": att.change_note,
    }
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(att, k, v)
    db.commit()
    db.refresh(att)
    after = {
        "file_name": att.file_name, "file_path": att.file_path,
        "description": att.description, "change_note": att.change_note,
    }
    _log_undo(db, user_id, "update", "attachment", att.id, before, after)
    db.commit()
    return att


@router.delete("/{att_id}", summary="删除附件")
def delete_attachment(att_id: int, user_id: str = Query(...), db: Session = Depends(get_db)):
    att = db.query(Attachment).filter(Attachment.id == att_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")
    _check_attachment_permission(att, user_id, "owner", db)
    before = {
        "entity_type": att.entity_type, "entity_id": att.entity_id,
        "file_name": att.file_name, "file_path": att.file_path,
        "description": att.description, "version": att.version,
        "change_note": att.change_note, "is_current": att.is_current,
        "parent_id": att.parent_id, "user_id": att.user_id,
    }
    if att.is_current:
        if att.parent_id:
            parent = db.query(Attachment).filter(Attachment.id == att.parent_id).first()
            if parent:
                parent.is_current = True
        else:
            child = db.query(Attachment).filter(
                Attachment.parent_id == att.id,
            ).order_by(Attachment.version.asc()).first()
            if child:
                child.is_current = True
    db.delete(att)
    _log_undo(db, user_id, "delete", "attachment", att_id, before, {})
    db.commit()
    return {"detail": "已删除"}
