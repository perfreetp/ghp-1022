from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models import Experiment, Collaborator


def get_user_role(exp_id: int, user_id: str, db: Session) -> Optional[str]:
    exp = db.query(Experiment).filter(Experiment.id == exp_id).first()
    if not exp:
        return None
    if exp.user_id == user_id:
        return "owner"
    collab = db.query(Collaborator).filter(
        Collaborator.experiment_id == exp_id, Collaborator.user_id == user_id
    ).first()
    if collab:
        return collab.role
    return None


ROLE_ORDER = {"viewer": 0, "editor": 1, "owner": 2}


def require_role(exp_id: int, user_id: str, required_role: str, db: Session):
    role = get_user_role(exp_id, user_id, db)
    if role is None:
        raise HTTPException(status_code=404, detail="实验不存在或无权限")
    if ROLE_ORDER.get(role, -1) < ROLE_ORDER.get(required_role, 99):
        raise HTTPException(status_code=403, detail="权限不足，需要 {0} 角色".format(required_role))
    return role
