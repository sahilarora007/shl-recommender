from fastapi import FastAPI
from contextlib import asynccontextmanager
from models import ChatRequest, ChatResponse
from agent import run_agent
from retrieval import load_index

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_index()      # pre-load FAISS at startup
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    return await run_agent(req.messages)
