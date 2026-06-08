from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Boolean, ForeignKey, JSON,
)
from sqlalchemy.orm import relationship
from app.database import Base


class Idea(Base):
    __tablename__ = "ideas"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    category = Column(String(100), default="")
    user_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    experiments = relationship("Experiment", back_populates="idea")


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    idea_id = Column(Integer, ForeignKey("ideas.id"), nullable=False)
    title = Column(String(200), nullable=False)
    target_metrics = Column(JSON, default=dict)
    validation_steps = Column(JSON, default=list)
    status = Column(String(50), default="draft")
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    user_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    idea = relationship("Idea", back_populates="experiments")
    budgets = relationship("Budget", back_populates="experiment", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="experiment", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="experiment", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="experiment", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="experiment", cascade="all, delete-orphan")
    collaborators = relationship("Collaborator", back_populates="experiment", cascade="all, delete-orphan")


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    type = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, default="")
    user_id = Column(String(100), nullable=False, index=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    experiment = relationship("Experiment", back_populates="budgets")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    source = Column(String(200), default="")
    amount = Column(Float, default=0)
    status = Column(String(50), default="pending")
    customer_info = Column(JSON, default=dict)
    user_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    experiment = relationship("Experiment", back_populates="orders")


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    content = Column(Text, nullable=False)
    customer_name = Column(String(100), default="")
    rating = Column(Integer, default=0)
    user_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    experiment = relationship("Experiment", back_populates="feedbacks")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    content = Column(Text, default="")
    conversion_rate = Column(Float, default=0)
    summary = Column(Text, default="")
    user_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    experiment = relationship("Experiment", back_populates="reviews")


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    type = Column(String(50), default="deadline")
    message = Column(Text, default="")
    remind_at = Column(DateTime, nullable=False)
    sent = Column(Boolean, default=False)
    user_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    experiment = relationship("Experiment", back_populates="reminders")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), default="")
    description = Column(Text, default="")
    user_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Collaborator(Base):
    __tablename__ = "collaborators"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    user_id = Column(String(100), nullable=False, index=True)
    role = Column(String(20), default="viewer")
    created_at = Column(DateTime, default=datetime.utcnow)

    experiment = relationship("Experiment", back_populates="collaborators")


class UndoLog(Base):
    __tablename__ = "undo_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    operation_type = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    before_data = Column(JSON, default=dict)
    after_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
