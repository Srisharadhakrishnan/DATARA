from fastapi import APIRouter, HTTPException, status
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_engine import chat_engine

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
def chat_query(request: ChatRequest):
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        response_data = chat_engine.process_question(request.question)
        return ChatResponse(**response_data)
    except Exception as e:
        return ChatResponse(
            answer="I don't have that information in the uploaded data.",
            cypher="MATCH (r:Row) RETURN count(r)",
            result=[],
            grounded=False
        )
