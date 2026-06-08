from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class IdeaCreate(BaseModel):
    title: str
    description: str = ""
    category: str = ""


class IdeaUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None


class IdeaOut(BaseModel):
    id: int
    title: str
    description: str
    category: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExperimentCreate(BaseModel):
    idea_id: int
    title: str


class MetricsUpdate(BaseModel):
    target_metrics: dict


class StepsUpdate(BaseModel):
    validation_steps: list


class ExperimentUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None


class ExperimentOut(BaseModel):
    id: int
    idea_id: int
    title: str
    target_metrics: dict
    validation_steps: list
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    user_id: str
    created_at: datetime
    updated_at: datetime
    overview: Optional[dict] = None

    model_config = {"from_attributes": True}


class BudgetCreate(BaseModel):
    experiment_id: int
    type: str
    amount: float
    description: str = ""


class BudgetOut(BaseModel):
    id: int
    experiment_id: int
    type: str
    amount: float
    description: str
    user_id: str
    recorded_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    experiment_id: int
    source: str = ""
    amount: float = 0
    status: str = "pending"
    customer_info: dict = Field(default_factory=dict)


class OrderBindSource(BaseModel):
    source: str


class OrderOut(BaseModel):
    id: int
    experiment_id: int
    source: str
    amount: float
    status: str
    customer_info: dict
    user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackCreate(BaseModel):
    experiment_id: int
    content: str
    customer_name: str = ""
    rating: int = 0


class FeedbackOut(BaseModel):
    id: int
    experiment_id: int
    content: str
    customer_name: str
    rating: int
    user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewOut(BaseModel):
    id: int
    experiment_id: int
    content: str
    conversion_rate: float
    summary: str
    user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReminderCreate(BaseModel):
    experiment_id: int
    type: str = "deadline"
    message: str = ""
    remind_at: datetime


class ReminderOut(BaseModel):
    id: int
    experiment_id: int
    type: str
    message: str
    remind_at: datetime
    sent: bool
    user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AttachmentCreate(BaseModel):
    entity_type: str
    entity_id: int
    file_name: str
    file_path: str = ""
    description: str = ""
    change_note: str = ""
    parent_id: Optional[int] = None


class AttachmentUpdate(BaseModel):
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    description: Optional[str] = None
    change_note: Optional[str] = None


class AttachmentOut(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    file_name: str
    file_path: str
    description: str
    version: int
    change_note: str
    is_current: bool
    parent_id: Optional[int] = None
    user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AttachmentListResponse(BaseModel):
    total: int
    items: list[AttachmentOut]
    skip: int
    limit: int


class ExperimentOverview(BaseModel):
    experiment_id: int
    attachment_count: int
    recent_attachments: list[AttachmentOut]
    review_count: int
    total_cost: float
    total_income: float
    net_profit: float


class CollaboratorCreate(BaseModel):
    experiment_id: int
    user_id: str
    role: str = "viewer"


class CollaboratorUpdate(BaseModel):
    role: str


class CollaboratorOut(BaseModel):
    id: int
    experiment_id: int
    user_id: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UndoRequest(BaseModel):
    undo_log_id: Optional[int] = None


class UndoLogOut(BaseModel):
    id: int
    user_id: str
    operation_type: str
    entity_type: str
    entity_id: int
    before_data: dict
    after_data: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class LeaderboardItem(BaseModel):
    user_id: str
    total_experiments: int
    completed_experiments: int
    total_income: float
    total_cost: float
    net_profit: float
    avg_conversion_rate: float


class SyncProgress(BaseModel):
    user_id: str
    experiments: list[ExperimentOut]
    ideas: list[IdeaOut]
    last_sync: datetime


class ExperimentCompare(BaseModel):
    experiment_id: int
    title: str
    status: str
    total_cost: float
    total_income: float
    net_profit: float
    conversion_rate: float
