import requests
import logging

logger = logging.getLogger(__name__)

def query_mistral(prompt: str, client_id: int) -> str:
    """
    Query the Mistral model via Ollama API
    
    Args:
        prompt: The user's message/query
        client_id: The client ID for context
    
    Returns:
        The response from the Mistral model
    """
    try:
        # Enrich the prompt with client context
        enriched_prompt = f"[Client ID: {client_id}]\n{prompt}"
        
        # Use local Ollama instance on macOS from within Docker container
        ollama_url = "http://host.docker.internal:11434/api/generate"
        
        response = requests.post(ollama_url, json={
            "model": "mistral",
            "prompt": enriched_prompt,
            "stream": False
        }, timeout=30)
        
        response.raise_for_status()
        result = response.json()
        
        return result.get("response", "").strip()
        
    except requests.exceptions.ConnectionError:
        logger.error("Failed to connect to Ollama API")
        return "Error: Unable to connect to AI service. Please try again later."
    except requests.exceptions.Timeout:
        logger.error("Ollama API request timed out")
        return "Error: Request timed out. Please try again."
    except requests.exceptions.RequestException as e:
        logger.error(f"Request to Ollama API failed: {e}")
        return "Error: Failed to process your request. Please try again."
    except Exception as e:
        logger.error(f"Unexpected error in query_mistral: {e}")
        return "Error: An unexpected error occurred. Please try again." 