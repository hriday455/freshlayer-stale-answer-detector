import os
import json
import requests
from http.server import HTTPServer, SimpleHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

ACTIVE_MODEL = "qwen/qwen3.8-27b"

def get_best_groq_model() -> str:
    return "qwen/qwen3.8-27b"

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    try:
        res = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=10)
        data = res.json()
        if "data" in data and len(data["data"]) > 0:
            # Pick the best text-generation model (skip audio/whisper models)
            for m in data["data"]:
                m_id = m.get("id", "")
                if "whisper" not in m_id and "orpheus" not in m_id:
                    ACTIVE_MODEL = m_id
                    print(f"✅ Auto-selected Active Groq Model: '{ACTIVE_MODEL}'")
                    return ACTIVE_MODEL
    except Exception as e:
        print(f"⚠️ Model detection error: {e}")

    # Fallback default
    ACTIVE_MODEL = "openai/gpt-oss-20b"
    return ACTIVE_MODEL

def call_groq(prompt: str, json_mode: bool = False) -> tuple[str, str]:
    if not GROQ_API_KEY:
        return "", "GROQ_API_KEY is missing in your .env file!"

    model_name = get_best_groq_model()

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 400
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=25)
        data = res.json()
        if "error" in data:
            err_msg = data["error"].get("message", "Unknown Groq Error")
            print(f"❌ Groq Error: {err_msg}")
            return "", f"Groq Error: {err_msg}"
        return data["choices"][0]["message"]["content"], ""
    except Exception as e:
        print(f"❌ LLM Connection Exception: {e}")
        return "", str(e)

def search_tavily(query: str) -> tuple[list, str]:
    if not TAVILY_API_KEY:
        return [], "TAVILY_API_KEY is missing in your .env file!"

    print(f"🌐 [TAVILY SEARCH]: '{query}'")
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "max_results": 3
    }
    try:
        res = requests.post(url, json=payload, timeout=15)
        data = res.json()
        if "error" in data:
            print(f"❌ Tavily Error: {data['error']}")
            return [], data["error"]
        sources = []
        for r in data.get("results", []):
            sources.append({
                "title": r.get("title", "Live Web Result"),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:300]
            })
        return sources, ""
    except Exception as e:
        return [], str(e)

def run_pipeline(text: str) -> dict:
    print(f"\n--- [RUNNING FACT-CHECK PIPELINE] ---")
    print(f"Input: {text}")

    extract_prompt = f"""
    You are a fact-checking extraction engine.
    Extract EVERY factual claim (leadership, company names, pricing, rules, sports stats).
    Text: \"\"\"{text}\"\"\"

    IMPORTANT: When creating the "search_query", phrase it neutrally to find the CURRENT, LATEST reality today (e.g. use words like 'current', 'latest', 'today', 'who is current CEO of X'). DO NOT just repeat the old claim!

    Return ONLY a JSON object:
    {{
      "claims": [
        {{
          "claim_id": 1,
          "claim_text": "the exact claim made",
          "category": "leadership | pricing | general",
          "search_query": "neutral query with 'current' or 'today' to check real status right now"
        }}
      ]
    }}
    """
    raw_llm, error = call_groq(extract_prompt, json_mode=True)
    
    if error:
        return {
            "overall_freshness": 0,
            "verified_claims": [{
                "claim_id": 1,
                "original_claim": text,
                "category": "API_ERROR",
                "freshness_score": 0,
                "status": "ERROR",
                "verdict": error,
                "current_fact": "Check your API keys in the .env file.",
                "sources": []
            }],
            "updated_text": f"SYSTEM ERROR: {error}"
        }

    try:
        parsed = json.loads(raw_llm)
        claims = parsed.get("claims", [])
    except Exception:
        claims = []

    if not claims:
        claims = [{
            "claim_id": 1,
            "claim_text": text,
            "category": "general",
            "search_query": text
        }]

    verified_claims = []
    total_score = 0

    for c in claims:
        sources, _ = search_tavily(c["search_query"])
        context = "\n".join([f"- [{s['title']}]: {s['content']}" for s in sources])

        judge_prompt = f"""
        Compare this claim against live search results retrieved right now:
        CLAIM: "{c['claim_text']}"
        WEB RESULTS:
        {context if context else "No web results found."}

        Task:
        1. Determine if this claim is STILL completely accurate today, or if it is OUTDATED / FALSE / REPLACED.
        2. STRICT FRESHNESS SCORING RULES:
           - Give EXACTLY 0 if the claim is false, outdated, or no longer holds true today (e.g. someone is no longer captain/CEO, a price changed, a method was removed). DO NOT give 10 or 20 for past truth!
           - Give 50-70 ONLY if the claim is mostly true but has minor changes.
           - Give 100 ONLY if the claim is 100% completely true right now.
        3. Status: "FRESH" (if >=75), "QUESTIONABLE" (if 45-74), "STALE" (if <45).

        Return ONLY a JSON object:
        {{
          "freshness_score": <int 0-100>,
          "status": "FRESH" | "QUESTIONABLE" | "STALE",
          "verdict": "<short 1-2 sentence explanation of why it is right or wrong>",
          "current_fact": "<the actual verified truth today>"
        }}
        """
        judge_raw, _ = call_groq(judge_prompt, json_mode=True)
        try:
            verdict_data = json.loads(judge_raw)
        except Exception:
            verdict_data = {
                "freshness_score": 0,
                "status": "STALE",
                "verdict": "Could not judge against web results.",
                "current_fact": "Unverified"
            }

        verdict_data["claim_id"] = c["claim_id"]
        verdict_data["original_claim"] = c["claim_text"]
        verdict_data["category"] = c["category"]
        verdict_data["sources"] = [{"title": s["title"], "url": s["url"]} for s in sources]
        
        verified_claims.append(verdict_data)
        total_score += verdict_data["freshness_score"]

    overall = round(total_score / len(verified_claims))

    # Rewrite
    rewrite_prompt = f"Original text: {text}\nFact Check Audit: {json.dumps(verified_claims)}\nRewrite the text correcting all false or stale facts with the actual current facts."
    updated_text, _ = call_groq(rewrite_prompt)
    if not updated_text:
        updated_text = text

    return {
        "overall_freshness": overall,
        "verified_claims": verified_claims,
        "updated_text": updated_text
    }

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            with open("templates/index.html", "rb") as f:
                self.wfile.write(f.read())
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/analyze":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8"))

            result = run_pipeline(payload.get("text", ""))

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8000), Handler)
    print("==========================================")
    print("🚀 FreshLayer Live at: http://localhost:8000")
    print("⚡ Tavily Live Search + Auto-Detected Groq Model")
    print("==========================================")
    server.serve_forever()