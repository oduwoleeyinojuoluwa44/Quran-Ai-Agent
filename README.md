# Quran Mood Agent

This is a Python-based AI agent that fetches Quran quotes based on the user's mood. It's designed to be integrated with Telex.im.

## Technical Details

- **Framework:** Flask
- **Dependencies:** `Flask`, `requests`, `google-generativeai`
- **Quran API:** Uses `http://api.alquran.cloud/v1` as a fallback for random Quranic verses.
- **Mood Detection & Smart Response:** Uses Google Gemini 1.5 Pro model for advanced mood detection. It then leverages Gemini to either directly provide a highly relevant Quranic verse with an explanation, or as a fallback, explains the relevance of a randomly fetched verse to the user's mood. The Gemini model is configured with a system instruction to act as a compassionate and knowledgeable Quranic assistant. It also includes basic conversational handling for greetings and self-introduction. **Crucially, the agent now maintains conversational memory using Gemini's chat history feature, allowing for more natural and context-aware interactions.**

## Setup and Installation

1.  **Clone the repository (if applicable) or navigate to the project directory:**
    ```bash
    cd quran-mood-agent-py
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up Gemini API Key using a `.env` file:**
    You need a Google Gemini API key. Obtain one from [Google AI Studio](https://aistudio.google.com/app/apikey).
    Create a file named `.env` in the root of your `quran-mood-agent-py` directory and add your API key to it:
    ```
    GEMINI_API_KEY=YOUR_GEMINI_API_KEY
    ```
    Replace `YOUR_GEMINI_API_KEY` with your actual key. The application will automatically load this key.

4.  **Run the Flask application:**
    ```bash
    python app.py
    ```
    The agent will run locally on `http://0.0.0.0:5000`.

## Exposing the Local Server to the Internet

To integrate with Telex.im, your local server needs to be accessible via a public URL. You can use tools like `ngrok` or `expose` for this.

### Using `ngrok` (Recommended)

1.  **Download ngrok:** Visit [ngrok.com/download](https://ngrok.com/download) and follow the instructions to install it.
2.  **Authenticate ngrok:**
    ```bash
    ngrok authtoken <YOUR_NGROK_AUTH_TOKEN>
    ```
3.  **Expose your Flask app:**
    ```bash
    ngrok http 5000
    ```
    Ngrok will provide you with a public URL (e.g., `https://xxxx-xxxx-xxxx-xxxx.ngrok-free.app`). This URL will be your agent's public endpoint.

## Telex.im Integration

Once your agent is running and exposed via a public URL (e.g., using ngrok), you need to configure it on Telex.im.

1.  **Access Telex.im:** Ensure you have access to the Telex organization. If not, run `/telex-invite your-email@example.com` (replace with your actual email).

2.  **Create a new agent workflow on Telex.im:** You will need to create a new workflow and add an "a2a/mastra-a2a-node" (even though this is a Python agent, the A2A protocol is used for integration).

3.  **Configure the workflow JSON:** Use the following JSON structure as a template. **Replace `YOUR_PUBLIC_AGENT_URL` with the ngrok URL you obtained.**

    ```json
    {
      "active": true,
      "category": "utilities",
      "description": "An AI agent that provides Quran quotes based on user's mood.",
      "id": "quran_mood_agent_workflow",
      "long_description": "You are a helpful Quran Mood Agent. Your primary function is to provide relevant Quranic verses based on the user's emotional state. When a user expresses a mood (e.g., happy, sad, anxious, angry, grateful, stressed, hopeful, fearful, calm, lonely, confused, motivated, tired, thankful, inspired), you will respond with a suitable Quran quote. If the user does not express a mood, you will ask them to specify how they are feeling.",
      "name": "Quran Mood Agent",
      "nodes": [
        {
          "id": "quran_mood_agent_node",
          "name": "Quran Mood Agent Node",
          "parameters": {},
          "position": [
            816,
            -112
          ],
          "type": "a2a/mastra-a2a-node",
          "typeVersion": 1,
          "url": "YOUR_PUBLIC_AGENT_URL/agent"
        }
      ],
      "pinData": {},
      "settings": {
        "executionOrder": "v1"
      },
      "short_description": "Provides Quran quotes based on mood."
    }
    ```

    **Important:**
    *   Set `"active": true` to enable the agent.
    *   The `url` in the `nodes` section should point to your public endpoint followed by `/agent` (e.g., `https://xxxx.ngrok-free.app/agent`).

4.  **Test your agent:** Once configured on Telex.im, you can interact with it by sending messages that express a mood.

## How to Test

1.  Run your Flask app locally (`python app.py`).
2.  Start `ngrok` to expose your app (`ngrok http 5000`).
3.  Configure the workflow on Telex.im with your ngrok URL.
4.  In Telex.im, send messages like:
    *   "Hello" or "Hi" (should get a greeting)
    *   "Who are you?" (should get a self-introduction)
    *   "I'm feeling sad today." (should get a relevant verse and explanation)
    *   "I'm so happy!" (should get a relevant verse and explanation)
    *   "I feel anxious about the future." (should get a relevant verse and explanation)
    *   "I'm grateful for everything." (should get a relevant verse and explanation)
    *   "I'm feeling neutral." (This should prompt you to specify a mood)
    *   "I'm feeling excited!" (should get a response indicating the mood is detected but not mapped, or a fallback verse with explanation)
    *   **Test memory:** After expressing a mood, try a follow-up like "What about when I'm happy?" or "Can you give me another one for that?" (The agent should ideally remember the previous context or mood, though the current implementation focuses on single-turn mood detection for verse retrieval).

## Deliverables

-   **Working AI agent:** The `app.py` file contains the core logic.
-   **Telex.im integration:** Achieved by configuring the workflow JSON with the public endpoint.
-   **Live demo/API endpoint:** Provided by running the Flask app and exposing it with `ngrok`.
-   **Documentation:** This `README.md` serves as the documentation.
-   **Blog post & Tweet:** (To be created by the user based on their experience)

## Error Handling

The agent includes basic error handling for:
-   **Invalid JSON payloads:** The `/agent` endpoint checks for empty or malformed JSON and returns a 400 Bad Request.
-   **Internal server errors:** A general `try-except` block in the `/agent` endpoint catches unexpected errors and returns a 500 Internal Server Error.
-   **Quran API request failures:** The `get_quran_quote` function handles `requests.exceptions.RequestException` and other general exceptions, returning a user-friendly error message.
-   **Gemini mood detection failures:** The `detect_mood_with_gemini` function includes error handling and returns "unknown" if mood detection fails.
-   **Unknown or unmapped moods:** If Gemini detects a mood not in `MOOD_MAPPING`, or if the mood is "unknown", the agent provides appropriate feedback to the user.
