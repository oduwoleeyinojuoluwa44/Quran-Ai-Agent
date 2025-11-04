# app.py
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import requests
import random
import os
import re
import json
import html
import google.generativeai as genai
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

app = FastAPI(title="Quran Mood Agent (FastAPI)")

# Add CORS middleware
origins = ["*"] # Allows all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

# Configure Gemini API
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if not gemini_api_key:
    print("Error: GEMINI_API_KEY environment variable not set.")
    print("Please set it in your .env file or as an environment variable.")
    raise SystemExit(1)

genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel(
    'gemini-2.5-flash',
    system_instruction=(
        "You are a compassionate and knowledgeable Quranic assistant. Your primary "
        "goal is to provide comfort, guidance, and relevant Quranic verses to users "
        "based on their emotional state. Keep responses empathetic and concise."
    )
)

# Simple mood mapping
MOOD_MAPPING = {
    "happy": ["joy", "gratitude", "blessing"],
    "sad": ["patience", "hope", "comfort", "grief"],
    "anxious": ["peace", "trust", "guidance"],
    "angry": ["forgiveness", "patience", "calm"],
    "grateful": ["gratitude", "thanks", "blessing"],
    "stressed": ["peace", "reliance", "ease"],
    "hopeful": ["hope", "mercy", "future"],
    "fearful": ["protection", "trust", "strength"],
    "calm": ["tranquility", "reflection", "peace"],
    "lonely": ["companionship", "Allah", "nearness"],
    "confused": ["guidance", "clarity", "wisdom"],
    "motivated": ["strive", "success", "effort"],
    "tired": ["rest", "ease", "strength"],
    "thankful": ["gratitude", "thanks", "blessing"],
    "inspired": ["creation", "signs", "knowledge"]
}

QURAN_API_BASE_URL = "http://api.alquran.cloud/v1"


# -------------------------
# Pydantic Generic models
# -------------------------
class TelexInputMessage(BaseModel): # Retained for generic parsing compatibility
    kind: str
    role: Optional[str] = None
    content: Optional[str] = None

class SimpleMessageInput(BaseModel): # Retained for generic parsing compatibility
    message: str

class GenericResponse(BaseModel):
    response: str
    mood: str
    source: str = "Quran Mood Agent"

# -------------------------
# Pydantic Telex JSON-RPC models
# -------------------------
class TelexMessagePart(BaseModel):
    type: str
    text: str

class TelexMessageContent(BaseModel):
    role: str
    parts: List[TelexMessagePart]

class TelexRpcParams(BaseModel):
    message: TelexMessageContent

class TelexRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    id: Optional[Any] = None # Can be string, number, or null
    params: TelexRpcParams

class TelexRpcResult(BaseModel):
    role: str
    parts: List[TelexMessagePart]
    kind: str = "message"
    message_id: str = "generated-msg-id" # Placeholder, can be generated dynamically

class TelexRpcSuccessResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    result: TelexRpcResult

class TelexRpcError(BaseModel):
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None

class TelexRpcErrorResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    error: TelexRpcError

# -------------------------
# Utilities
# -------------------------
def pretty_log(title: str, data: Any):
    try:
        print("\n" + "=" * 60)
        print(f"📥 {title}")
        print("=" * 60)
        print(json.dumps(data, indent=4, ensure_ascii=False))
        print("=" * 60 + "\n")
    except Exception as e:
        print("pretty_log error:", e)


def clean_html_text(raw: Optional[str]) -> str:
    if not raw:
        return ""
    unescaped = html.unescape(raw)
    soup = BeautifulSoup(unescaped, "html.parser")
    cleaned = soup.get_text(separator=" ", strip=True)
    cleaned = cleaned.replace("\xa0", " ").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def get_random_quran_quote() -> str:
    try:
        surah_num = random.randint(1, 114)
        response = requests.get(f"{QURAN_API_BASE_URL}/surah/{surah_num}")
        response.raise_for_status()
        surah_data = response.json()
        ayahs = surah_data["data"]["ayahs"]
        random_ayah = random.choice(ayahs)
        text = random_ayah["text"]
        surah_name = surah_data["data"]["englishName"]
        ayah_number = random_ayah["numberInSurah"]
        return f'"{text}" (Quran {surah_name}:{ayah_number})'
    except Exception as e:
        print("get_random_quran_quote error:", e)
        return "I'm sorry, I couldn't fetch a Quran quote at this moment. Please try again later."


# -------------------------
# Message extraction
# -------------------------


def extract_user_message_generic(payload: Dict[str, Any]) -> str:
    """
    Generic extractor that supports:
    - Telex observed shape: payload['messages'][0]['messages'] list of dicts with 'text'
    - A2A-like nested shapes (as a raw dict)
    - Simple shapes {'message': '...'} or {'content': '...'}
    Strategy: look for obvious places and return the last non-empty text.
    """
    try:
        # 1) Telex double nested 'messages' shape
        outer = payload.get("messages")
        if isinstance(outer, list) and outer:
            first = outer[0]
            inner = first.get("messages")
            if isinstance(inner, list) and inner:
                # scan reversed to pick last meaningful text
                for entry in reversed(inner):
                    if not isinstance(entry, dict):
                        continue
                    # common keys: 'text', 'content'
                    raw = entry.get("text") or entry.get("content") or entry.get("message")
                    cleaned = clean_html_text(raw)
                    if cleaned:
                        return cleaned

        # 2) A2A raw shape (removed as A2A is now handled by / endpoint)
        # if "params" in payload and isinstance(payload["params"], dict):
        #     msg = payload["params"].get("message")
        #     if isinstance(msg, dict):
        #         parts = msg.get("parts", [])
        #         for part in parts:
        #             if isinstance(part, dict) and part.get("kind") == "data":
        #                 data_list = part.get("data", [])
        #                 if isinstance(data_list, list) and data_list:
        #                     last = data_list[-1]
        #                     if isinstance(last, dict) and "text" in last:
        #                         return clean_html_text(last["text"])

        # 3) simple shapes
        if "message" in payload and isinstance(payload["message"], str):
            return clean_html_text(payload["message"])
        if "content" in payload and isinstance(payload["content"], str):
            return clean_html_text(payload["content"])
        if "text" in payload and isinstance(payload["text"], str):
            return clean_html_text(payload["text"])

        # 4) scan whole payload for dicts with 'text'
        def collect_texts(obj):
            found = []
            if obj is None:
                return found
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "text" and isinstance(v, str) and v.strip():
                        found.append(v)
                    else:
                        found.extend(collect_texts(v))
            elif isinstance(obj, list):
                for item in obj:
                    found.extend(collect_texts(item))
            return found

        all_texts = collect_texts(payload)
        if all_texts:
            return clean_html_text(all_texts[-1])

        return ""
    except Exception as e:
        print("extract_user_message_generic error:", e)
        return ""


# -------------------------
# Gemini helpers
# -------------------------
def get_smart_quran_response(mood: str, user_message: str) -> str:
    try:
        prompt_direct_verse = (
            f"The user is feeling {mood} because they said: \"{user_message}\".\n"
            "Provide a highly relevant Quranic verse (Surah:Ayah) and a brief explanation of how it addresses their mood.\n"
            "If you cannot find a specific verse, just say 'NO_VERSE_FOUND'.\n"
            "Format your response strictly as:\n"
            "Verse: [Surah:Ayah] - [English Translation]\n"
            "Explanation: [Your explanation]"
        )
        print("--- PROMPT FOR VERSE ---")
        print(prompt_direct_verse)
        response_direct = model.generate_content(prompt_direct_verse)
        gemini_output = response_direct.text.strip()
        print("--- GEMINI OUTPUT ---")
        print(gemini_output)

        if "NO_VERSE_FOUND" not in gemini_output and "Verse:" in gemini_output and "Explanation:" in gemini_output:
            return gemini_output

        # fallback
        random_quote = get_random_quran_quote()
        prompt_explain_random = (
            f"The user is feeling {mood} because they said: \"{user_message}\".\n"
            f"Here is a Quranic verse: {random_quote}.\n"
            "Explain how this verse can be relevant or comforting to someone feeling {mood}.\n"
            "Format your response strictly as:\n"
            f"Verse: {random_quote}\nExplanation:"
        )
        response_explain = model.generate_content(prompt_explain_random)
        return response_explain.text.strip()

    except Exception as e:
        print("get_smart_quran_response error:", e)
        fallback = get_random_quran_quote()
        return f"I'm sorry — couldn't get a tailored verse. Here's something to reflect on: {fallback}"


def detect_mood_with_gemini(text: str) -> str:
    try:
        prompt = (
            f"Analyze the following text and identify the primary mood expressed. "
            f"Respond with a single word (e.g., happy, sad, anxious, angry, grateful, stressed, hopeful, fearful, calm, lonely, confused, motivated, tired, thankful, inspired). "
            f"If the mood is unclear or neutral, respond with 'unknown'.\n\nText: '{text}'\nMood:"
        )
        print("--- PROMPT FOR MOOD ---")
        print(prompt)
        response = model.generate_content(prompt)
        response_text = response.text.strip().lower()
        print("--- GEMINI MOOD OUTPUT ---")
        print(response_text)

        for mood in MOOD_MAPPING.keys():
            if mood in response_text:
                return mood
        return "unknown"
    except Exception as e:
        print("detect_mood_with_gemini error:", e)
        return "unknown"


# -------------------------
# Core Logic Functions
# -------------------------
async def handle_message_send(params: TelexRpcParams) -> TelexRpcResult:
    user_message = ""
    # Extract user message from TelexRpcParams
    if params.message and params.message.parts:
        for part in params.message.parts:
            if part.type == "text" and part.text:
                user_message = clean_html_text(part.text)
                break # Take the first text part

    if not user_message or not user_message.strip():
        raise HTTPException(status_code=400, detail="I didn't receive a clear message. Please try again.")

    # handle simple conversational queries
    text_lower = user_message.lower()
    if any(g in text_lower for g in ["hello", "hi", "hey"]):
        general_response = "Assalamu Alaikum! I am your Quran Mood Agent. Tell me how you're feeling, and I'll find a relevant Quranic verse for you."
        return TelexRpcResult(
            role="agent",
            parts=[TelexMessagePart(type="text", text=general_response)]
        )

    # mood detection
    mood = detect_mood_with_gemini(user_message)
    if mood == "unknown":
        response_text = "I couldn't understand your mood. Please try expressing it more clearly so I can find a relevant Quran quote."
        return TelexRpcResult(
            role="agent",
            parts=[TelexMessagePart(type="text", text=response_text)]
        )

    # get the smart response (Gemini)
    smart_response = get_smart_quran_response(mood, user_message)
    return TelexRpcResult(
        role="agent",
        parts=[TelexMessagePart(type="text", text=smart_response)]
    )

# -------------------------
# Endpoints
# -------------------------
@app.post("/")
async def handle_telex_rpc_request(request: Request):
    try:
        request_body = await request.json()
        pretty_log("RAW TELEX JSON-RPC PAYLOAD", request_body)

        rpc_request = TelexRpcRequest(**request_body)
        
        if rpc_request.jsonrpc != "2.0":
            error_data = TelexRpcError(code=-32600, message="Invalid JSON-RPC version. Must be '2.0'.")
            return JSONResponse(status_code=400, content=TelexRpcErrorResponse(id=rpc_request.id, error=error_data).model_dump(), media_type="application/json")

        if rpc_request.method == "message/send":
            result = await handle_message_send(rpc_request.params)
            return JSONResponse(content=TelexRpcSuccessResponse(id=rpc_request.id, result=result).model_dump(), media_type="application/json")
        else:
            error_data = TelexRpcError(code=-32601, message="Method not found")
            return JSONResponse(status_code=405, content=TelexRpcErrorResponse(id=rpc_request.id, error=error_data).model_dump(), media_type="application/json")

    except HTTPException as e:
        error_data = TelexRpcError(code=e.status_code, message=e.detail)
        return JSONResponse(status_code=e.status_code, content=TelexRpcErrorResponse(id=request_body.get("id", None), error=error_data).model_dump(), media_type="application/json")
    except Exception as e:
        print("Unhandled exception in /:", e)
        error_data = TelexRpcError(code=500, message="An internal error occurred while processing your request.")
        return JSONResponse(status_code=500, content=TelexRpcErrorResponse(id=request_body.get("id", None), error=error_data).model_dump(), media_type="application/json")

@app.post("/agent")
async def agent_endpoint(request: Request):
    # This endpoint will now serve generic non-Telex requests
    is_a2a_request: bool = False # Initialize here to ensure it's always bound
    try:
        request_body = await request.json()
        pretty_log("RAW GENERIC PAYLOAD", request_body)

        user_message = ""
        # request_id = "generated-req-id" # Not needed for generic response
        # thread_id = "generated-thread-id" # Not needed for generic response

        # Try structured parses first
        parsed = False
        # 1) TelexInputMessage shape (for generic compatibility)
        try:
            tin = TelexInputMessage(**request_body)
            if tin.content:
                user_message = clean_html_text(tin.content)
                parsed = True
        except Exception:
            pass

        # 2) SimpleMessageInput (for generic compatibility)
        if not parsed:
            try:
                sim = SimpleMessageInput(**request_body)
                user_message = clean_html_text(sim.message)
                parsed = True
            except Exception:
                pass

        # 3) Generic extractor fallback
        if not parsed:
            user_message = extract_user_message_generic(request_body)

        if not user_message or not user_message.strip():
            raise HTTPException(status_code=400, detail="I didn't receive a clear message. Please try again.")

        # handle simple conversational queries
        text_lower = user_message.lower()
        if any(g in text_lower for g in ["hello", "hi", "hey"]):
            general_response = "Assalamu Alaikum! I am your Quran Mood Agent. Tell me how you're feeling, and I'll find a relevant Quranic verse for you."
            return JSONResponse(content=GenericResponse(response=general_response, mood="greeting").model_dump(), media_type="application/json")

        # mood detection
        mood = detect_mood_with_gemini(user_message)
        if mood == "unknown":
            response_text = "I couldn't understand your mood. Please try expressing it more clearly so I can find a relevant Quran quote."
            return JSONResponse(content=GenericResponse(response=response_text, mood="unknown").model_dump(), media_type="application/json")

        # get the smart response (Gemini)
        smart_response = get_smart_quran_response(mood, user_message)
        return JSONResponse(content=GenericResponse(response=smart_response, mood=mood).model_dump(), media_type="application/json")

    except HTTPException as e:
        error_detail = e.detail
        status_code = e.status_code
        return JSONResponse(status_code=status_code, content={"error": error_detail, "code": status_code}, media_type="application/json")

    except Exception as e:
        print("Unhandled exception in /agent:", e)
        error_detail = "An internal error occurred while processing your request."
        return JSONResponse(status_code=500, content={"error": error_detail, "code": 500}, media_type="application/json")


@app.get("/")
async def home():
    return {"status": "running", "service": "Quran Mood Agent"}


# -------------------------
# Run (for local testing)
# -------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
