"""Deterministic, weighted lead-scoring engine (no LLM involved in the score)."""
import re
from dataclasses import dataclass, asdict

# ---------------- Configuration ----------------
WEIGHTS = {  # must sum to 100
    "Job Title / Authority": 20,
    "Requirement Fit & Intent": 20,
    "Company Size": 15,
    "Lead Source": 10,
    "Industry Fit": 10,
    "Contact Quality": 10,
    "Company Credibility": 10,
    "Location": 5,
}
MISSING_CREDIT = 0.30          # fraction of weight given when data is absent
HOT_MIN, WARM_MIN = 70, 40     # classification thresholds
FIELDS = ["name", "company", "website", "job_title", "industry",
          "location", "company_size", "lead_source", "requirement", "email", "phone"]
FIELD_IMPORTANCE = {"job_title": 3, "requirement": 3, "company_size": 2, "email": 1.5,
                    "industry": 1, "location": 1, "lead_source": 1, "phone": 1,
                    "website": 1, "company": 0.5, "name": 0.5}

TITLE_LOW = r"intern|student|trainee|fresher|freelanc"
TITLE_TOP = (r"founder|owner|proprietor|\bceo\b|\bcto\b|\bcfo\b|\bcoo\b|\bcmo\b|\bcio\b|chief|"
             r"president|managing director|director|\bvp\b|vice president|\bhead\b|partner")
TITLE_MID = r"manager|lead|principal|supervisor"
TITLE_JR = r"engineer|developer|analyst|executive|associate|consultant|assistant|coordinator"

FIT_KW = ["crm", "sales automation", "lead management", "customer management", "sales pipeline"]
GENERAL_KW = ["software", "platform", "tool", "solution", "erp", "automation", "saas", "system"]
INTENT_KW = ["looking for", "need", "want", "require", "evaluate", "implement", "buy", "purchase",
             "demo", "pricing", "quote", "budget", "urgent", "asap", "immediately", "migrate", "replace"]
NEGATIVE_KW = ["just exploring", "just browsing", "student", "college", "assignment", "research",
               "free", "job", "internship", "curious"]

SOURCES = {"referral": 1.0, "demo": 0.95, "website": 0.9, "inbound": 0.9, "partner": 0.85,
           "webinar": 0.7, "event": 0.7, "linkedin": 0.6, "email": 0.5, "social": 0.4,
           "advert": 0.4, "ads": 0.4, "cold": 0.3, "purchased": 0.2, "list": 0.25}

IND_HIGH = ["it services", "software", "saas", "technology", "consult", "real estate",
            "finance", "fintech", "banking", "insurance", "marketing", "agency", "e-commerce", "ecommerce"]
IND_MID = ["manufactur", "retail", "health", "education", "logistics", "telecom", "travel", "media"]

METROS = ["bangalore", "bengaluru", "mumbai", "delhi", "gurgaon", "gurugram", "noida",
          "hyderabad", "pune", "chennai", "ncr", "kolkata"]
FREE_MAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "rediffmail.com", "icloud.com"}
PLACEHOLDER = {"example.com", "test.com", "domain.com", "email.com", "abc.com", "xyz.com"}


@dataclass
class Factor:
    name: str
    weight: int
    earned: float
    value: str
    note: str
    impact: str  # positive | neutral | negative | missing


@dataclass
class ScoreResult:
    score: int
    classification: str
    quality: str
    confidence: str
    completeness: float
    factors: list
    positives: list
    negatives: list
    missing_fields: list
    next_action: str
    explanation: str

    def to_dict(self):
        d = asdict(self)
        return d


# ---------------- Helpers ----------------
def _clean(v):
    return str(v).strip() if v is not None and str(v).strip().lower() not in ("", "nan", "none", "n/a") else ""


def _domain(url_or_email):
    s = url_or_email.lower().strip()
    s = s.split("@")[-1] if "@" in s else re.sub(r"^https?://", "", s).split("/")[0]
    return re.sub(r"^www\.", "", s)


def _impact(frac):
    return "positive" if frac >= 0.7 else "negative" if frac < 0.45 else "neutral"


def _missing(name, w, what):
    return Factor(name, w, round(w * MISSING_CREDIT, 1), "—", f"{what} not provided; neutral partial credit given", "missing")


# ---------------- Individual factor scorers ----------------
def f_title(lead):
    n, w = "Job Title / Authority", WEIGHTS["Job Title / Authority"]
    t = _clean(lead.get("job_title"))
    if not t:
        return _missing(n, w, "Job title")
    tl = t.lower()
    if re.search(TITLE_LOW, tl): fr, note = 0.1, "Intern/student-level role; no buying authority"
    elif re.search(TITLE_TOP, tl): fr, note = 1.0, "Decision-maker / senior leadership"
    elif re.search(TITLE_MID, tl): fr, note = 0.6, "Manager-level; influences purchase decisions"
    elif re.search(TITLE_JR, tl): fr, note = 0.3, "Individual contributor; limited authority"
    else: fr, note = 0.25, "Unrecognised title; authority unclear"
    return Factor(n, w, round(w * fr, 1), t, note, _impact(fr))


def f_requirement(lead):
    n, w = "Requirement Fit & Intent", WEIGHTS["Requirement Fit & Intent"]
    r = _clean(lead.get("requirement"))
    if not r:
        return _missing(n, w, "Requirement")
    rl, fr, notes = r.lower(), 0.0, []
    if any(k in rl for k in FIT_KW): fr += 0.4; notes.append("matches our core offering (CRM)")
    elif any(k in rl for k in GENERAL_KW): fr += 0.2; notes.append("related software need")
    if any(k in rl for k in INTENT_KW): fr += 0.25; notes.append("clear buying intent")
    if len(rl.split()) >= 3: fr += 0.15; notes.append("specific requirement")
    fr += 0.2 if fr > 0 else 0.05  # base credit for stating a requirement
    if any(k in rl for k in NEGATIVE_KW):
        fr = min(fr, 0.2); notes.append("low-intent keywords detected")
    fr = min(fr, 1.0)
    return Factor(n, w, round(w * fr, 1), r, "; ".join(notes).capitalize() or "Vague requirement", _impact(fr))


def f_size(lead):
    n, w = "Company Size", WEIGHTS["Company Size"]
    s = _clean(lead.get("company_size"))
    if not s:
        return _missing(n, w, "Company size")
    nums = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", s)]
    if not nums:
        return Factor(n, w, round(w * 0.4, 1), s, "Size could not be parsed; partial credit", "neutral")
    m = sum(nums) / len(nums)
    if m <= 1: fr, note = 0.3, "Solo operation; small budget"
    elif m <= 10: fr, note = 0.4, "Micro company; limited budget"
    elif m <= 50: fr, note = 0.7, "Small company; good CRM fit"
    elif m <= 200: fr, note = 1.0, "SMB / mid-size sweet spot for CRM"
    elif m <= 1000: fr, note = 0.9, "Mid-market; strong budget, longer cycle"
    else: fr, note = 0.75, "Enterprise; large budget but complex procurement"
    return Factor(n, w, round(w * fr, 1), s, note, _impact(fr))


def f_source(lead):
    n, w = "Lead Source", WEIGHTS["Lead Source"]
    s = _clean(lead.get("lead_source"))
    if not s:
        return _missing(n, w, "Lead source")
    sl = s.lower()
    fr = next((v for k, v in SOURCES.items() if k in sl), 0.4)
    note = ("High-intent inbound/referral channel" if fr >= 0.85 else
            "Moderate-intent channel" if fr >= 0.5 else "Low-intent outbound/paid channel")
    return Factor(n, w, round(w * fr, 1), s, note, _impact(fr))


def f_industry(lead):
    n, w = "Industry Fit", WEIGHTS["Industry Fit"]
    i = _clean(lead.get("industry"))
    if not i:
        return _missing(n, w, "Industry")
    il = i.lower()
    if any(k in il for k in IND_HIGH): fr, note = 1.0, "Core target industry"
    elif any(k in il for k in IND_MID): fr, note = 0.7, "Secondary target industry"
    else: fr, note = 0.5, "Industry outside primary focus"
    return Factor(n, w, round(w * fr, 1), i, note, _impact(fr))


def f_location(lead):
    n, w = "Location", WEIGHTS["Location"]
    l = _clean(lead.get("location"))
    if not l:
        return _missing(n, w, "Location")
    fr, note = ((1.0, "Major metro in serviceable region") if any(k in l.lower() for k in METROS)
                else (0.6, "Location outside priority metros"))
    return Factor(n, w, round(w * fr, 1), l, note, _impact(fr))


def f_contact(lead):
    n, w = "Contact Quality", WEIGHTS["Contact Quality"]
    e, p = _clean(lead.get("email")), _clean(lead.get("phone"))
    if not e and not p:
        return _missing(n, w, "Email and phone")
    notes = []
    if not e: ef = MISSING_CREDIT; notes.append("email missing")
    elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", e): ef = 0.0; notes.append("invalid email format")
    elif _domain(e) in PLACEHOLDER: ef = 0.3; notes.append("placeholder/generic email domain")
    elif _domain(e) in FREE_MAIL: ef = 0.6; notes.append("free-mail address (not a business domain)")
    else: ef = 1.0; notes.append("valid business email")
    digits = re.sub(r"\D", "", p)
    if not p: pf = MISSING_CREDIT; notes.append("phone missing")
    elif 10 <= len(digits) <= 13: pf = 1.0; notes.append("valid phone")
    else: pf = 0.2; notes.append("invalid phone number")
    fr = (ef + pf) / 2
    return Factor(n, w, round(w * fr, 1), f"{e or '—'} / {p or '—'}", "; ".join(notes).capitalize(), _impact(fr))


def f_credibility(lead):
    n, w = "Company Credibility", WEIGHTS["Company Credibility"]
    site, comp, email = _clean(lead.get("website")), _clean(lead.get("company")), _clean(lead.get("email"))
    if not site and not comp:
        return _missing(n, w, "Company name and website")
    notes, fr = [], 0.0
    if comp: fr += 0.3; notes.append("company named")
    if site and re.fullmatch(r"(https?://)?([\w-]+\.)+[A-Za-z]{2,}(/.*)?", site):
        fr += 0.4; notes.append("valid website")
        if email and "@" in email and _domain(email) == _domain(site):
            fr += 0.3; notes.append("email domain matches website")
        elif email and "@" in email:
            notes.append("email domain differs from website")
    elif site: notes.append("website looks invalid")
    else: notes.append("no website")
    return Factor(n, w, round(w * fr, 1), site or comp, "; ".join(notes).capitalize(), _impact(fr))


SCORERS = [f_title, f_requirement, f_size, f_source, f_industry, f_contact, f_credibility, f_location]


# ---------------- Public API ----------------
def classify(score):
    return "Hot" if score >= HOT_MIN else "Warm" if score >= WARM_MIN else "Cold"


def quality(score):
    return ("Excellent" if score >= 80 else "Good" if score >= 65 else
            "Average" if score >= 45 else "Below Average" if score >= 30 else "Poor")


def next_action(cls, lead, missing):
    base = {
        "Hot": "Call within 24 hours and book a product demo; assign to a senior sales rep.",
        "Warm": "Send a personalised email with a CRM case study, then follow up by phone within 3 days; add to nurture sequence.",
        "Cold": "Add to a low-touch email nurture campaign; re-score when new engagement or data arrives.",
    }[cls]
    if missing:
        base += " Enrich the lead first: collect " + ", ".join(m.replace("_", " ") for m in missing[:3]) + "."
    return base


def explain(score, cls, factors, confidence):
    pos = [f for f in factors if f.impact == "positive"]
    neg = [f for f in factors if f.impact in ("negative", "missing")]
    top = sorted(factors, key=lambda f: f.earned, reverse=True)[:2]
    s = (f"The lead scored {score}/100 and is classified as {cls} (confidence: {confidence}). "
         f"The strongest contributors were {top[0].name} ({top[0].earned}/{top[0].weight}) and "
         f"{top[1].name} ({top[1].earned}/{top[1].weight}). ")
    if neg:
        s += "Points were lost mainly on " + ", ".join(f.name for f in neg[:3]) + ". "
    else:
        s += "No significant weaknesses were found. "
    s += f"Thresholds: Hot ≥ {HOT_MIN}, Warm {WARM_MIN}–{HOT_MIN - 1}, Cold < {WARM_MIN}."
    return s


def score_lead(lead: dict) -> ScoreResult:
    factors = [fn(lead) for fn in SCORERS]
    score = int(round(sum(f.earned for f in factors)))
    score = max(0, min(100, score))
    missing = [k for k in FIELDS if not _clean(lead.get(k))]
    total = sum(FIELD_IMPORTANCE.values())
    comp = 1 - sum(FIELD_IMPORTANCE[k] for k in missing) / total
    confidence = "High" if comp >= 0.85 else "Medium" if comp >= 0.6 else "Low"
    cls = classify(score)
    positives = [f"{f.name}: {f.note} ({f.earned}/{f.weight})" for f in factors if f.impact == "positive"]
    negatives = [f"{f.name}: {f.note} ({f.earned}/{f.weight})" for f in factors if f.impact in ("negative", "missing")]
    return ScoreResult(score, cls, quality(score), confidence, round(comp, 2),
                       [asdict(f) for f in factors], positives, negatives, missing,
                       next_action(cls, lead, missing), explain(score, cls, factors, confidence))
