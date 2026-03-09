import os
import argparse
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import anthropic

# ---------------------------------------------------------
# The definitive YC Demo: One-Line Veritas Integration
# ---------------------------------------------------------
import veritas

# We wrap the standard client with the Veritas proxy.
# Everything else in this file is standard Anthropic code.
client = veritas.Anthropic(
    anthropic.AsyncAnthropic(), 
    feature_name="beach_recommendation"
)
# ---------------------------------------------------------

app = FastAPI(title="Beach Guesser UI")

# We serve the local HTML file for the UI
# In a real app we'd use StaticFiles, but for absolute simplicity we'll just read the file directly.
import pathlib
BASE_DIR = pathlib.Path(__file__).parent

class RecommendRequest(BaseModel):
    user_preference: str

@app.get("/", response_class=HTMLResponse)
async def get_ui():
    index_path = BASE_DIR / "index.html"
    return index_path.read_text(encoding="utf-8")

@app.post("/recommend")
async def recommend(req: RecommendRequest):
    """
    The Core Feature endpoint. 
    In the DEMO narrative, we will manually change the `prompt` string below 
    to simulate a "code change" that heavily inflates token usage.
    """
    
    # ------------------------------------------------------------------------------------------------
    # DEMO INSTRUCTIONS: 
    # Run 1 (Base): Keep this prompt short and cheap. Run with `--mock-commit abc123`
    # Run 2 (Target): Uncomment the massive prompt below to cause a regression. Run with `--mock-commit def456`
    # ------------------------------------------------------------------------------------------------
    
    # BASE PROMPT (Cheap, fast)
    system_prompt = "You are a travel agent. Recommend exactly one beach based on the user's input in exactly one short sentence."
    
    # TARGET PROMPT (Massively Inflated for the Regression Demo)
    # system_prompt = (
    #    "You are an over-eager travel agent. Recommend the absolutely perfect beach. "
    #    "You must write a comprehensive, 10-paragraph itinerary. "
    #    "Include historical details about the sand, local cuisine, the history of surfing in the region, "
    #    "and a minute-by-minute breakdown of a 7-day vacation. Give me as much detail as humanly possible."
    # )
    
    response = await client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": req.user_preference}]
    )
    
    return {"recommendation": response.content[0].text}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Beach Guesser End-to-End Demo.")
    parser.add_argument("--mock-commit", type=str, help="Mock the Git commit hash for Veritas tracking.")
    parser.add_argument("--port", type=int, default=8080, help="Port to run the demo app on.")
    args = parser.parse_args()
    
    if args.mock_commit:
        # Veritas SDK checks this environment variable automatically.
        os.environ["VERITAS_MOCK_COMMIT"] = args.mock_commit
        print(f"[Veritas] Mocking Git Commit: {args.mock_commit}")
        
    # We must also ensure the API key is set so the events actually route to the Dashboard!
    if not os.environ.get("VERITAS_API_URL"):
        os.environ["VERITAS_API_URL"] = "http://localhost:8000/api/v1/events"
        
    # We need a fallback API key for the local dev server
    if not os.environ.get("VERITAS_API_KEY"):
        os.environ["VERITAS_API_KEY"] = "sk-vrt-demo-local"
        
    print(f"Starting Beach Guesser UI on http://localhost:{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
