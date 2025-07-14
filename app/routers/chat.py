from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.mistral_chat import query_mistral
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class ChatRequest(BaseModel):
    client_id: int
    message: str

class ChatResponse(BaseModel):
    client_id: int
    response: str

@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Chat endpoint that processes messages using the Mistral model
    
    Args:
        request: ChatRequest containing client_id and message
    
    Returns:
        ChatResponse with the AI-generated response
    """
    try:
        logger.info(f"Processing chat request for client {request.client_id}")
        
        # Query the Mistral model
        response = query_mistral(request.message, request.client_id)
        
        logger.info(f"Successfully processed chat request for client {request.client_id}")
        
        return ChatResponse(
            client_id=request.client_id,
            response=response
        )
        
    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to process chat request"
        ) 