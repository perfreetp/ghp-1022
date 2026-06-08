from fastapi import FastAPI
from app.database import engine, Base
from app.routers import ideas, experiments, budgets, orders, feedbacks, reviews, reminders, attachments, collaborators, common

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="副业实验室",
    description="为多个记账和社群产品提供副业实验管理能力的后端服务，覆盖点子、实验、预算、订单、反馈、复盘、提醒 7 大能力",
    version="1.0.0",
)

app.include_router(ideas.router)
app.include_router(experiments.router)
app.include_router(budgets.router)
app.include_router(orders.router)
app.include_router(feedbacks.router)
app.include_router(reviews.router)
app.include_router(reminders.router)
app.include_router(attachments.router)
app.include_router(collaborators.router)
app.include_router(common.router)


@app.get("/", tags=["健康检查"])
def health_check():
    return {"service": "副业实验室", "version": "1.0.0", "status": "running"}
