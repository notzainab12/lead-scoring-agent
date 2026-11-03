
"""
Optional Groq LLM layer for lead-scoring explanations.
The numeric score is NEVER produced or changed by the LLM.
"""

import json
import os

from groq import Groq
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


def llm_explanation(lead: dict, result: dict):
    """Returns (text, error). Uses rule-based fallback if Groq fails."""

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return None, "GROQ_API_KEY not found in .env file."

    try:
        # Initialize Groq client
        client = Groq(api_key=api_key)

        # Prepare scoring result safely
        scoring_data = {
            "score": result.get("score"),
            "classification": result.get("classification"),
            "confidence": result.get("confidence"),
            "factors": result.get("factors"),
            "missing_fields": result.get("missing_fields"),
        }

        # Build prompt

        prompt = (
            "Act as an experienced sales development representative "
            "analyzing a potential business lead.\n\n"
            "Write a concise, natural, professional assessment "
            "for a sales team member. Avoid robotic language, "
            "generic phrases, and unnecessary repetition.\n\n"
            "Explain:\n"
            "1. Why this lead received its score.\n"
            "2. The strongest buying signals.\n"
            "3. Missing information or potential concerns.\n"
            "4. A practical, personalized next step for the sales rep.\n\n"
            "Use the provided scoring data as the only source "
            "for numerical scores and classifications. "
            "Never modify or recalculate the score.\n\n"
            "Write 4-6 conversational but professional sentences.\n\n"
            "LEAD INFORMATION:\n"
            + json.dumps(lead, indent=2)
            + "\n\nSCORING RESULT:\n"
            + json.dumps(scoring_data, indent=2)
        )


        # Call Groq API
        response = client.chat.completions.create(
            model=os.getenv(
                "GROQ_MODEL",
                "llama-3.3-70b-versatile"
            ),
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            max_tokens=500,
            temperature=0,
        )

        # Extract explanation
        explanation = response.choices[0].message.content

        return explanation, None

    except Exception as e:
        return None, f"Groq API error ({type(e).__name__}): {e}"
