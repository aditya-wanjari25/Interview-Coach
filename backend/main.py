import os
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from langgraph.types import Command
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore  
from psycopg_pool import AsyncConnectionPool
from typing import Optional
from agents.screening_agent import graph

DATABASE_URL = os.environ["DATABASE_URL"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncConnectionPool(
        conninfo=DATABASE_URL,
        max_size=20,
        kwargs={"autocommit": True, "prepare_threshold": 0},
    ) as pool:
        checkpointer = AsyncPostgresSaver(pool) #short term memory
        postgres_store = AsyncPostgresStore(pool) #long term memory
        await checkpointer.setup() 
        await postgres_store.setup()
        app.state.compiled_graph = graph.compile(checkpointer=checkpointer)
        app.state.store = postgres_store
        yield


app = FastAPI(lifespan=lifespan)


class StartInterviewRequest(BaseModel):
    job_description: str
    user_id: str


class StartInterviewResponse(BaseModel):
    session_id: str
    question: str
    question_key: str

class AnswerRequest(BaseModel):
    session_id: str
    answer: str

class AnswerResponse(BaseModel):
    status: str  # "in_progress" or "completed"
    question: Optional[str] = None
    question_key: Optional[str] = None
    result: Optional[bool] = None
    feedback_output: Optional[str] = None

@app.get("/")
def root():
    return {"hello": "this is root!"}

@app.post("/interview/start", response_model=StartInterviewResponse)
async def start_interview(request: Request, body: StartInterviewRequest):
    session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    result = await request.app.state.compiled_graph.ainvoke(
        {"job_description": body.job_description, "user_id": body.user_id},
        config=config,
    )

    if "__interrupt__" not in result:
        raise HTTPException(status_code=500, detail="Graph did not pause as expected")

    payload = result["__interrupt__"][0].value

    return StartInterviewResponse(
        session_id=session_id,
        question=payload["question"],
        question_key=payload["question_key"],
    )




@app.post("/interview/answer", response_model=AnswerResponse)
async def submit_answer(request: Request, body: AnswerRequest):
    config = {"configurable": {"thread_id": body.session_id}}

    try:
        result = await request.app.state.compiled_graph.ainvoke(Command(resume=body.answer), config=config)
    except Exception:
        raise HTTPException(status_code=404, detail="Session not found or already completed")

    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        return AnswerResponse(
            status="in_progress",
            question=payload["question"],
            question_key=payload["question_key"],
        )

    return AnswerResponse(
        status="completed",
        result=result.get("result"),
        feedback_output=result.get("feedback_output"),
    )