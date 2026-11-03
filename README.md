# AI-Based Lead Scoring System

A lead qualification tool that gives every lead a **0-100 score**, a **Hot / Warm / Cold** class, a quality rating,
positive/negative factors, an explanation, a confidence level and a recommended next action.

**Design principle:** the score comes from a transparent, weighted rule engine (`scoring.py`).
An LLM (optional) is used *only* to write a richer explanation. It never produces or changes the score,
so identical inputs always give identical scores.

## Project structure
```
lead_scoring/
├── app.py              # Streamlit UI (single lead + CSV batch scoring)
├── scoring.py          # Weighted scoring engine (no external dependencies)
├── llm_explainer.py    # Optional LLM explanation layer (Anthropic API)
├── sample_leads.csv    # Sample leads for batch upload
├── tests/test_scoring.py
└── requirements.txt
```

## How to run
Requires Python 3.9+.

```bash
cd lead_scoring
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py              # opens http://localhost:8501
```

1. **Single lead** tab: the sample lead (Rahul Sharma) is pre-filled. Edit any field (or clear fields to test missing data) and click **Score lead**.
2. **Batch (CSV)** tab: upload `sample_leads.csv` to score many leads, ranked by score, and download the results.

**Optional LLM explanation:** set an API key, then switch on *Use LLM for explanation* in the sidebar.
```bash
export ANTHROPIC_API_KEY=your_key      # Windows PowerShell: $env:ANTHROPIC_API_KEY="your_key"
```
Without a key the app works fully and shows the built-in rule-based explanation.

**Run tests:** `python -m unittest discover -s tests`

## Scoring methodology (100 points)
| Parameter | Weight | How it is scored |
|---|---|---|
| Job Title / Authority | 20 | Founder/CEO/Director/VP/Head = 100%, Manager = 60%, Engineer/Executive = 30%, Intern/Student = 10% |
| Requirement Fit & Intent | 20 | Mentions CRM/sales automation (+40%), general software need (+20%), buying-intent words like "need", "demo", "budget", "urgent" (+25%), specific detail (+15%), base credit (+20%); low-intent words ("just exploring", "student", "free") cap at 20% |
| Company Size | 15 | 51-200 employees = 100% (CRM sweet spot), 201-1000 = 90%, 11-50 = 70%, 1000+ = 75%, 2-10 = 40%, solo = 30% |
| Lead Source | 10 | Referral 100%, Demo request 95%, Website 90%, Webinar/Event 70%, LinkedIn 60%, Email 50%, Social 40%, Cold 30%, Purchased list 20% |
| Industry Fit | 10 | IT/Software/SaaS/Finance/Real estate/Consulting = 100%, Manufacturing/Retail/Health/Education = 70%, other = 50% |
| Contact Quality | 10 | Email (business domain 100%, free-mail 60%, placeholder domain 30%, invalid 0%) averaged with phone (valid 100%, invalid 20%) |
| Company Credibility | 10 | Company named (30%) + valid website (40%) + email domain matches website (30%) |
| Location | 5 | Major metro 100%, other 60% |

**Classification:** Hot ≥ 70 · Warm 40-69 · Cold < 40
**Quality:** Excellent ≥ 80, Good ≥ 65, Average ≥ 45, Below Average ≥ 30, Poor < 30

**Missing data:** a missing field is never a crash. That parameter gets 30% of its weight (neutral-low credit), is listed under negative factors as "not provided", and lowers the **Confidence Level**.

**Confidence:** based on the weighted share of fields provided (job title and requirement matter most). High ≥ 85%, Medium ≥ 60%, Low < 60%.

**Consistency:** the engine is pure Python with no randomness, so the same input always returns the same output (covered by a unit test).

All weights, keyword lists and thresholds sit at the top of `scoring.py` so a sales team can tune them.

## Sample test cases (output of the engine)
| # | Lead | Score | Class | Confidence | Why |
|---|---|---|---|---|---|
| 1 | Rahul Sharma, Founder, ABC Technologies, wants CRM (assignment sample) | 92 | Hot | High | Decision-maker, CRM intent, ideal size, inbound; loses points for `example.com` email |
| 2 | Priya Mehta, CEO, Real Estate, referral, "CRM urgently - budget approved" | 100 | Hot | High | Perfect on every parameter |
| 3 | Amit Verma, Intern, purchased list, "free tools for college assignment" | 31 | Cold | High | No authority, low intent, tiny company, invalid phone |
| 4 | Sneha Rao, Marketing Manager, only requirement "CRM" (most fields empty) | 45 | Warm | Low | Partial credit for missing data; low confidence flags enrichment needed |
| 5 | Karan Singh, Sales Manager, SaaS, 200-500 employees, webinar | 88 | Hot | High | Strong fit and intent, manager-level authority |

Automated tests (`tests/test_scoring.py`) also check: weights sum to 100, determinism, empty-lead handling, score range 0-100, business vs placeholder email.

## Demo flow
Run the app → score the pre-filled sample lead → clear Job Title and Requirement to see the score drop and confidence fall → upload `sample_leads.csv` in the Batch tab.

## Limitations / future work
Rules are heuristic (not trained on conversion data). With historical won/lost deals, the weights could be calibrated using logistic regression while keeping the same explainable output.
