from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import random
import os
import re
import google.generativeai as genai
from dotenv import load_dotenv
from bs4 import BeautifulSoup
# ChatSession type is often implicitly handled or part of the genai object directly
# No explicit import for ChatSession type is typically needed for basic usage.
# If type hinting is desired, it might be genai.GenerativeModel.start_chat().__class__ or similar.

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure Gemini API
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if not gemini_api_key:
    print("Error: GEMINI_API_KEY environment variable not set.")
    print("Please set it in your .env file or as an environment variable.")
    # Exit or handle this more gracefully in a production environment
    exit(1) # Exiting for development clarity

genai.configure(api_key=gemini_api_key)
# Using 'gemini-1.0-pro' as it's often more universally available or the updated name.
# If this still fails, the user might need to check available models via Google AI Studio.
# Using 'gemini-1.5-pro' as it's the latest available model.
# If this still fails, the user might need to check available models via Google AI Studio.
model = genai.GenerativeModel(
    'gemini-2.5-flash',
    system_instruction="You are a compassionate and knowledgeable Quranic assistant. Your primary goal is to provide comfort, guidance, and relevant Quranic verses to users based on their emotional state. Always maintain a respectful and empathetic tone. When providing verses, ensure they are accompanied by a brief, insightful explanation that connects the verse to the user's mood or query. If a mood is unclear, gently ask for clarification. If a mood is detected but not directly mapped, offer a general comforting verse or explain why a specific verse might be hard to find for that particular mood."
)

# A simple mapping of moods to themes or keywords for Quranic verses
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

# Base URL for a public Quran API (using Quran.com API as an example)
# This API allows searching by keyword, which can be mapped from moods.
QURAN_API_BASE_URL = "http://api.alquran.cloud/v1"

def get_random_quran_quote():
    """
    Fetches a random Quran quote.
    """
    try:
        surah_num = random.randint(1, 114)
        response = requests.get(f"{QURAN_API_BASE_URL}/surah/{surah_num}")
        response.raise_for_status()
        surah_data = response.json()
        
        ayahs = surah_data['data']['ayahs']
        random_ayah = random.choice(ayahs)
        
        text = random_ayah['text']
        surah_name = surah_data['data']['englishName']
        ayah_number = random_ayah['numberInSurah']
        
        return f'"{text}" (Quran {surah_name}:{ayah_number})'

    except requests.exceptions.RequestException as e:
        print(f"Error fetching random Quran quote: {e}")
        return "I'm sorry, I couldn't fetch a Quran quote at this moment. Please try again later."
    except Exception as e:
        print(f"An unexpected error occurred while fetching a random quote: {e}")
        return "An unexpected error occurred while fetching your quote."

def extract_user_message(payload):
    """
    Extracts the real user message from a Telex.im payload based on the observed structure.
    It targets the last text entry within the 'data' part of the message.
    """
    try:
        # Navigate to the list of message parts
        parts = payload['params']['message']['parts']
        
        # Find the 'data' part and its 'data' list
        messages = []
        for part in parts:
            if part.get('kind') == 'data' and 'data' in part:
                messages = part['data']
                break
        
        # Ensure the messages list is not empty
        if not messages:
            return ""
            
        # The real user message is the last element
        last_message = messages[-1]
        
        # Extract the text content
        text = last_message.get('text', '')
        
        # Strip HTML tags and normalize whitespace
        if text:
            # Remove HTML tags
            clean_text = re.sub(r'<[^>]+>', '', text)
            # Replace non-breaking spaces with regular spaces and strip
            clean_text = clean_text.replace('\xa0', ' ').strip()
            return clean_text
            
    except (KeyError, IndexError, TypeError):
        # Return "" if the payload structure is not as expected
        return ""
        
    return ""

def get_smart_quran_response(mood, user_message):
    """
    Generates a smart Quranic response using Gemini, with a fallback mechanism.
    This is a stateless function that does not use chat history.
    """
    try:
        # Primary approach: Gemini directly provides a relevant verse and explanation
        prompt_direct_verse = f"""The user is feeling {mood} because they said: "{user_message}".
        Provide a highly relevant Quranic verse (Surah:Ayah) and a brief explanation of how it addresses their mood.
        If you cannot find a specific verse, just say 'NO_VERSE_FOUND'.
        Format your response strictly as:
        Verse: [Surah:Ayah] - [English Translation]
        Explanation: [Your explanation]
        """
        print(f"--- PROMPT FOR VERSE ---\n{prompt_direct_verse}\n------------------------")
        response_direct = model.generate_content(prompt_direct_verse)
        gemini_output = response_direct.text.strip()
        print(f"--- GEMINI RESPONSE FOR VERSE ---\n{gemini_output}\n-------------------------------")

        if "NO_VERSE_FOUND" not in gemini_output and "Verse:" in gemini_output and "Explanation:" in gemini_output:
            return gemini_output
        else:
            print("Gemini did not provide a direct verse, falling back to random verse with explanation.")
            # Fallback approach: Get a random verse and ask Gemini to explain its relevance (Option A)
            random_quote = get_random_quran_quote()
            if "I'm sorry" in random_quote or "An unexpected error" in random_quote:
                return random_quote # Return API error if fallback also fails

            prompt_explain_random = f"""The user is feeling {mood} because they said: "{user_message}".
            Here is a Quranic verse: {random_quote}.
            Explain how this verse can be relevant or comforting to someone feeling {mood}.
            Format your response strictly as:
            Verse: {random_quote}
            Explanation: [Your explanation]
            """
            response_explain = model.generate_content(prompt_explain_random)
            return response_explain.text.strip()

    except Exception as e:
        print(f"Error in get_smart_quran_response (Gemini interaction): {e}")
        # If Gemini fails entirely, fall back to just a random quote
        random_quote_fallback = get_random_quran_quote()
        if "I'm sorry" in random_quote_fallback or "An unexpected error" in random_quote_fallback:
            return "I'm sorry, I encountered an issue and couldn't provide a relevant Quran quote at this moment. Please try again later."
        return f"I'm sorry, I had trouble finding a perfectly tailored quote, but here's a verse for reflection: {random_quote_fallback}"


@app.route('/agent', methods=['POST'])
def agent_endpoint():
    """
    Receives messages and responds with a Quran quote.
    Handles both complex Telex.im payloads and simple JSON for testing.
    This endpoint is stateless and does not maintain conversation history.
    """
    try:
        data = request.get_json()
        if not data:
            print("Received empty or invalid JSON payload.")
            return jsonify({"response": "Invalid request: Empty or malformed JSON payload."}), 400
        print(f"Received data: {data}")

        user_message = ""
        # Check for a simple test payload (e.g., {"message": "I am sad"})
        if 'message' in data and isinstance(data.get('message'), str):
            user_message = data['message']
        # Otherwise, assume it's a complex Telex payload and parse it
        else:
            user_message = extract_user_message(data)

        if not user_message.strip():
            print("Received empty user message after parsing.")
            return jsonify({"response": "I didn't receive a clear message. Please try again."}), 400

        # Handle general conversational queries first (no AI needed)
        general_response = handle_general_queries(user_message)
        if general_response:
            return jsonify({"response": general_response})

        # If not a general query, proceed with mood detection using a stateless AI call
        mood = detect_mood_with_gemini(user_message)
        
        if mood == "unknown":
            return jsonify({"response": "I couldn't understand your mood. Please try expressing it more clearly so I can find a relevant Quran quote."})

        # Use the smart response function to get a relevant verse
        smart_response = get_smart_quran_response(mood, user_message)

        return jsonify({"response": smart_response})

    except Exception as e:
        print(f"Error in agent_endpoint: {e}")
        return jsonify({"response": "An internal error occurred while processing your request."}), 500

def handle_general_queries(text):
    """
    Handles general conversational queries like greetings or self-introduction.
    """
    text_lower = text.lower()
    if any(greeting in text_lower for greeting in ["hello", "hi", "hey"]):
        return "Assalamu Alaikum! I am your Quran Mood Agent. Tell me how you're feeling, and I'll find a relevant Quranic verse for you."
    elif any(query in text_lower for query in ["who are you", "what are you", "what do you do"]):
        return "I am the Quran Mood Agent. My purpose is to provide you with comforting and relevant Quranic verses based on your current mood. Just tell me how you feel!"
    return None # No general query matched

@app.route('/')
def home():
    return "Quran Mood Agent is running!"

def detect_mood_with_gemini(text):
    """
    Detects the user's mood using a stateless call to the Gemini model.
    It checks the model's response for any valid mood keyword.
    """
    try:
        prompt = f"Analyze the following text and identify the primary mood expressed. Respond with a single word representing the mood (e.g., happy, sad, anxious, angry, grateful, stressed, hopeful, fearful, calm, lonely, confused, motivated, tired, thankful, inspired). If the mood is unclear or neutral, respond with 'unknown'.\n\nText: '{text}'\nMood:"
        print(f"--- PROMPT FOR MOOD ---\n{prompt}\n-----------------------")
        response = model.generate_content(prompt)
        response_text = response.text.strip().lower()
        print(f"--- GEMINI RESPONSE FOR MOOD ---\n{response_text}\n------------------------------")
        
        # Find the first valid mood keyword in the response text
        for mood in MOOD_MAPPING.keys():
            # Check if the mood keyword is present in the response string.
            # This is more robust than checking against split() words.
            if mood in response_text:
                return mood
                
        return "unknown"
    except Exception as e:
        print(f"Error detecting mood with Gemini: {e}")
        return "unknown"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
