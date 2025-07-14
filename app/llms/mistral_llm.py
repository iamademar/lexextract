# app/llms/mistral_llm.py
import requests
import logging
from langchain.llms.base import LLM
from typing import Optional, List, Any, Dict
from pydantic import Field

logger = logging.getLogger(__name__)

class MistralLLM(LLM):
    """Custom LLM for Mistral via Ollama API"""
    
    endpoint: str = Field(default="http://host.docker.internal:11434/api/generate")
    model: str = Field(default="mistral")
    timeout: float = Field(default=30.0)

    @property
    def _llm_type(self) -> str:
        return "mistral-ollama"

    def _call(self, prompt: str, stop: Optional[List[str]] = None, run_manager: Optional[Any] = None, **kwargs: Any) -> str:
        """
        Call the Mistral model via Ollama API
        
        Args:
            prompt: The prompt to send to the model
            stop: Optional list of stop sequences
            run_manager: Optional run manager (for newer LangChain versions)
            
        Returns:
            The response from the model
        """
        try:
            resp = requests.post(
                self.endpoint,
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=self.timeout
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.exceptions.ConnectionError:
            logger.error("Failed to connect to Ollama API")
            raise Exception("Unable to connect to AI service")
        except requests.exceptions.Timeout:
            logger.error("Ollama API request timed out")
            raise Exception("Request timed out")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request to Ollama API failed: {e}")
            raise Exception("Failed to process request")
        except Exception as e:
            logger.error(f"Unexpected error in MistralLLM._call: {e}")
            raise Exception("An unexpected error occurred")

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Get the identifying parameters."""
        return {"endpoint": self.endpoint, "model": self.model} 