"""
Authoring service for generating concepts and items from text
"""
import json
import uuid
from typing import Dict, Any, List, Optional
import openai
from pathlib import Path
from app.api.models_simple import Concept, Item
# Simplified - skip validation for now
# from app.api.validators import AuthoringValidator, SchemaValidator
from app.api.storage import storage
import os
from dotenv import load_dotenv

load_dotenv()


class AuthoringService:
    """Service for authoring concepts and items using LLM"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        openai.api_key = self.api_key
        model_name = os.getenv("AUTHORING_MODEL", "gpt-3.5-turbo")
        # Map invalid model names to valid ones
        if model_name == "gpt-5":
            model_name = "gpt-4o"  # Latest GPT-4 model
        self.model = model_name
        self.prompt_version = os.getenv("AUTHORING_PROMPT_VERSION", "authoring_v1")
        
        # Use a simple system prompt for now
        self.system_prompt = """You are an expert at creating learning questions from text. 
        Generate concepts and questions from the provided text in JSON format.
        Return ONLY valid JSON with this structure:
        {
          "concepts": [{"id": "uuid", "title": "Title", "description": "Description"}],
          "items": [{"id": "uuid", "concept_id": "uuid", "kc": "definition", "type": "anchor", "prompt": "Question?", "answer": "Answer"}]
        }"""
    
    async def author_from_text(
        self, 
        text: str, 
        concept_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate concepts and items from source text
        
        Args:
            text: Source text to generate from
            concept_id: Optional existing concept to add items to
        
        Returns:
            Dictionary with concept_id and item_ids
        """
        print(f"[AUTHORING] Starting author_from_text with text length: {len(text)}")
        try:
            # Prepare the user prompt
            user_prompt = f"""
            Generate concepts and items from the following text. 
            Ensure strict JSON output with proper voice-first answer specifications.
            
            SOURCE TEXT:
            {text}
            
            REQUIREMENTS:
            - Create at least 1 concept with title and description
            - Generate at least 1 anchor item per concept
            - Include items for definition, procedure, discrimination, and application KCs
            - Each item must have complete answer_spec for voice grading
            - Ensure cue uniqueness within each concept
            
            Return ONLY valid JSON matching the specified schema.
            """
            
            # Call OpenAI API
            response = await self._call_openai(user_prompt)
            
            # Parse and validate JSON
            try:
                output = json.loads(response)
            except json.JSONDecodeError as e:
                # One retry on JSON failure
                retry_prompt = f"The previous output was not valid JSON. Error: {str(e)}\n\nPlease output ONLY valid JSON:\n\n{user_prompt}"
                response = await self._call_openai(retry_prompt)
                output = json.loads(response)
            
            # Skip validation for simplified version
            # AuthoringValidator.validate_authoring_output(output)
            
            # Save to storage
            saved_concept_ids = []
            saved_item_ids = []
            
            # Save concepts
            print(f"[AUTHORING] Processing {len(output.get('concepts', []))} concepts from LLM")
            for concept_data in output.get("concepts", []):
                # Generate proper UUIDs if needed
                if not concept_data.get("id") or concept_data["id"] == "uuid":
                    concept_data["id"] = str(uuid.uuid4())
                
                concept = Concept(**concept_data)
                await storage.save_concept(concept)
                saved_concept_ids.append(concept.id)
                print(f"[AUTHORING] Saved concept: {concept.id} - {concept.title}")
            
            # Save items
            print(f"[AUTHORING] Processing {len(output.get('items', []))} items from LLM")
            for item_data in output.get("items", []):
                # Generate proper UUIDs if needed
                if not item_data.get("id") or item_data["id"] == "uuid":
                    item_data["id"] = str(uuid.uuid4())
                
                # Ensure concept_id is valid
                if item_data.get("concept_id") == "uuid" and saved_concept_ids:
                    item_data["concept_id"] = saved_concept_ids[0]
                
                item = Item(**item_data)
                await storage.save_item(item)
                saved_item_ids.append(item.id)
                print(f"[AUTHORING] Saved item: {item.id} - {item.prompt[:50]}...")
            
            # Save variant templates if any
            for template_data in output.get("variant_templates", []):
                if not template_data.get("id") or template_data["id"] == "uuid":
                    template_data["id"] = str(uuid.uuid4())
                
                # We'll implement template saving later
                pass
            
            return {
                "concept_ids": saved_concept_ids,
                "item_ids": saved_item_ids,
                "status": "success"
            }
            
        except Exception as e:
            print(f"[AUTHORING] Error in author_from_text: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "error": str(e),
                "concept_ids": [],
                "item_ids": []
            }
    
    async def _call_openai(self, user_prompt: str) -> str:
        """Call OpenAI API with system and user prompts"""
        try:
            client = openai.OpenAI(
                api_key=self.api_key,
                timeout=30.0  # 30 second timeout
            )
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=1,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content
            if not content or content.strip() == "":
                raise ValueError("OpenAI returned empty response")
                
            # Strip markdown code blocks if present
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]  # Remove ```json
            if content.startswith("```"):
                content = content[3:]   # Remove ```
            if content.endswith("```"):
                content = content[:-3]  # Remove closing ```
            content = content.strip()
                
            print(f"OpenAI Response: {content}")  # Debug logging
            return content
            
        except openai.RateLimitError:
            raise Exception("OpenAI rate limit exceeded. Please try again later.")
        except openai.APITimeoutError:
            raise Exception("OpenAI request timed out. Please try again.")
        except openai.APIError as e:
            raise Exception(f"OpenAI API error: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to call OpenAI: {str(e)}")