def build_prompt(question: str, instruction: dict, action_result: dict):
    """
    Builds the final prompt sent to the LLM.
    It includes:
    - The user's question
    - The parsed instruction
    - The structured action result
    """

    return f"""
You are GOAM AI, the golf analytics assistant.

USER QUESTION:
{question}

PARSED INSTRUCTION:
{instruction}

STRUCTURED DATA FROM GOAM ENGINE:
{action_result}

TASK:
Answer the user's question using ONLY the structured data above.
Do NOT invent numbers or players.
Be concise, friendly, and accurate.
"""
