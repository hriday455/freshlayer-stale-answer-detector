# FreshLayer ⚡
> Stale-answer detector & live fact verification engine built for the Geek Room Global AI Hackathon (Tavily Track).

LLMs answer queries with high confidence, but their knowledge cutoffs cause them to repeatedly hallucinate outdated facts—citing former CEOs, deprecated library methods, and discontinued pricing plans.

**FreshLayer** acts as an automated verification proxy between an LLM's output and the end user. It extracts verifiable claims, checks them against the live web using the **Tavily Search API**, computes an isolated Freshness Score per claim, and synthesizes an up-to-date answer with citations.

---

## 🛠️ The Pipeline
[ Input Text / LLM Output ]
│
▼
Claim Extraction
↳ Identifies time-sensitive claims (leadership, pricing, specs, sports).
│
▼
Targeted Web Queries
↳ Transforms claims into neutral, present-day verification queries.
│
▼
Ground-Truth Verification (Tavily API)
↳ Fetches live web results, titles, and snippets.
│
▼
Freshness Scoring & Auto-Correction
↳ Assigns 0–100% freshness per claim, flags stale data, and rewrites the text.
---

## ✨ Features

- **Granular Claim Auditing:** Evaluates claims individually instead of rating the entire paragraph as a black box.
- **Tavily Live Ground Truth:** Uses live web retrieval rather than relying on another model's frozen internal weights.
- **Traffic-Light Freshness Scoring:**
  - 🟢 **Fresh (75–100%):** Verified accurate today.
  - 🟡 **Questionable (45–74%):** Partially accurate or altered criteria.
  - 🔴 **Stale (0–44%):** Outdated, discontinued, or factually replaced.
- **Automated Modernization:** Produces an updated paragraph replacing stale facts with current truth and markdown citations.
- **Zero-Dependency Lightweight UI:** Built with standard Python networking and Tailwind CSS—no heavy build tooling required.

---

## 🧰 Tech Stack

- **Backend:** Python (Built-in HTTP server, `requests`)
- **Search Backbone:** [Tavily Search API](https://tavily.com)
- **Inference Engine:** Groq API (`llama-3.3-70b-versatile` / `qwen/qwen3.8-27b`)
- **Frontend:** Vanilla HTML5, Tailwind CSS, Lucide Icons

---

## 🚀 Quickstart

### 1. Clone the repository
```bash
git clone https://github.com/your-username/freshlayer.git
cd freshlayer
2. Install dependencies
pip install -r requirements.txt
3. Configure environment variables
Create a .env file in the root directory:
TAVILY_API_KEY=your_tavily_key
GROQ_API_KEY=your_groq_key
4. Run the server
python main.py
Open http://localhost:8000 in your browser.