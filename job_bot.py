#!/usr/bin/env python3
"""
Job Bot — pulls from Greenhouse API + Indeed RSS
Posts top 7 AI-scored picks + batch to Slack at 9:30am & 7pm EST
Also triggered on-demand via /jobs Slack slash command
"""

import json
import os
import re
import xml.etree.ElementTree as ET
import requests
from datetime import datetime

# ── CONFIG ───────────────────────────────────────────────────────────────────

SLACK_WEBHOOK  = os.environ["SLACK_WEBHOOK"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SEEN_FILE      = "seen_jobs.json"

# ── COMPANIES (Greenhouse public API — no auth, no scraping) ──────────────────

GREENHOUSE_SLUGS = [
    # Big Tech
    ("Spotify",           "spotify"),
    ("Stripe",            "stripe"),
    ("Instacart",         "instacart"),
    ("Canva",             "canva"),
    ("Pinterest",         "pinterest"),
    ("Airbnb",            "airbnb"),
    ("Snap",              "snap"),
    ("Adobe",             "adobe"),
    ("Dropbox",           "dropbox"),
    # Product / Growth Startups
    ("Anthropic",         "anthropic"),
    ("Notion",            "notion"),
    ("Figma",             "figma"),
    ("Discord",           "discord"),
    ("Airtable",          "airtable"),
    ("Loom",              "loom"),
    ("Replit",            "replit"),
    ("Perplexity AI",     "perplexityai"),
    ("Substack",          "substack"),
    ("Beehiiv",           "beehiiv"),
    ("Linear",            "linear"),
    ("Webflow",           "webflow"),
    ("Miro",              "miro"),
    ("Gamma",             "gamma"),
    # Research / Insights / Media
    ("Morning Brew",      "morningbrew"),
    ("Axios",             "axios"),
    ("YPulse",            "ypulse"),
    ("Vox Media",         "voxmedia"),
    ("The Atlantic",      "theatlantic"),
    ("Puck News",         "puck"),
    # Creative Tech / Ad Agencies
    ("VaynerMedia",       "vaynermedia"),
    ("R/GA",              "rga"),
    ("Huge",              "hugeinc"),
    ("Ogilvy",            "ogilvy"),
    ("Droga5",            "droga5"),
    ("Wieden+Kennedy",    "wiedenkennedy"),
    ("MediaMonks",        "mediamonks"),
    ("BBDO",              "bbdo"),
    ("Grey",              "grey"),
    ("72andSunny",        "72andsunny"),
    ("Anomaly",           "anomaly"),
    # Strategy / Consulting / Social Impact
    ("Dalberg",           "dalberg"),
    ("Bridgespan",        "thebridgespangroup"),
    ("Teach For America", "teachforamerica"),
    ("IDEO",              "ideo"),
    ("GLAAD",             "glaad"),
    ("Omidyar Network",   "omidyarnetwork"),
]

# ── INDEED RSS QUERIES ────────────────────────────────────────────────────────
# Google, Microsoft, YouTube, Netflix don't use Greenhouse
# so we catch them via Indeed RSS instead

INDEED_QUERIES = [
    # NYC
    ("strategy associate",       "New York, NY"),
    ("research analyst",         "New York, NY"),
    ("creative technologist",    "New York, NY"),
    ("product associate",        "New York, NY"),
    ("growth analyst",           "New York, NY"),
    ("insights analyst",         "New York, NY"),
    ("associate consultant",     "New York, NY"),
    ("brand strategist",         "New York, NY"),
    ("program associate",        "New York, NY"),
    ("associate strategist",     "New York, NY"),
    ("content strategist",       "New York, NY"),
    # Bay Area
    ("strategy associate",       "San Francisco, CA"),
    ("product associate",        "San Francisco, CA"),
    ("research analyst",         "San Francisco, CA"),
    # Seattle
    ("research analyst",         "Seattle, WA"),
    ("strategy associate",       "Seattle, WA"),
    # Remote
    ("creative technologist",    "Remote"),
    ("associate strategist",     "Remote"),
    ("research analyst",         "Remote"),
]

# ── FILTERS ───────────────────────────────────────────────────────────────────

POSITIVE_KEYWORDS = [
    "strategy", "strategist", "analyst", "associate", "researcher",
    "research", "insights", "insight", "product", "growth", "creative",
    "program", "consultant", "consulting", "marketing", "brand",
    "content", "operations", "generalist", "technologist", "coordinator",
]

NEGATIVE_PATTERNS = [
    r"\bsenior\b", r"\bsr\.?\b", r"\bdirector\b", r"\bvp\b",
    r"\bprincipal\b", r"\bstaff\b", r"\bchief\b", r"\bhead of\b",
    r"\bvice president\b", r"\bengineering manager\b",
    r"\baccounting\b", r"\blegal counsel\b",
]

LOCATION_KEYWORDS = [
    "new york", "nyc", "brooklyn", "manhattan", "ny,", "new york,",
    "san francisco", "bay area", "sf,", "oakland",
    "seattle", "remote", "anywhere", "distributed", "hybrid",
]

# ── E-VERIFY LIST ─────────────────────────────────────────────────────────────

EVERIFY_CONFIRMED = {
    "spotify", "stripe", "instacart", "canva", "pinterest", "airbnb",
    "snap", "adobe", "dropbox", "anthropic", "notion", "figma",
    "discord", "airtable", "loom", "replit", "perplexity ai",
    "vaynermedia", "r/ga", "ogilvy", "droga5", "wieden+kennedy",
    "mediamonks", "bbdo", "grey", "morning brew", "axios", "vox media",
    "the atlantic", "teach for america", "ideo", "dalberg", "bridgespan",
    "google", "microsoft", "youtube", "netflix", "amazon", "meta",
    "deloitte", "accenture", "bcg", "mckinsey", "kpmg", "pwc",
    "miro", "webflow", "linear", "beehiiv", "substack", "gamma",
}

# ── MEG'S PROFILE ─────────────────────────────────────────────────────────────

MEG_PROFILE = """
Candidate: Meg — early-career generalist (0-3 yrs exp), NYC-based, international student (needs E-Verify employer).

Background:
- Strategy & research consulting at Birthvue (healthtech startup): GTM, mixed-method research, analytics, A/B testing, stakeholder management, retention (+18% Day-7, -25% churn)
- Product management at nonprofits via Develop For Good: agile sprints, PRDs, user research, accessibility, GraphQL/Node.js/React awareness
- Digital marketing analytics at Kepler Group: Google Ads, Search Query Analysis, campaign performance, client presentations
- Creative coding & AI builds: p5.js, Three.js, React — shipped 5+ independent products
- Led Design For America NYU (50+ members): design sprints for 10+ NYC nonprofits, launched student incubator Forge
- Music/culture community building since 2019 (M99 Studio): audience intelligence, social listening, brand strategy

Ideal roles: strategy, research & insights, creative technologist, product adjacent, generalist cross-functional
Ideal companies: media, social impact tech, consulting, creative agencies, big tech with creative culture (Spotify, Google, Netflix), startups with traction

Score HIGH (80-100) if:
- Generalist or cross-functional role
- Involves strategy, research, insights, or creative/build work
- Company has strong brand or creative culture
- Clear growth path, 0-3 years experience required
- NYC, Bay Area, Seattle, or Remote

Score MEDIUM (50-79) if:
- Somewhat specialized but still uses research or strategy skills
- Role is more execution-heavy but at a great company
- Location not ideal but remote is possible

Score LOW (0-49) if:
- Hyper-specialized (pure engineering, pure finance, pure legal)
- Requires 4+ years experience
- No creative, strategic, or research element
"""

# ── HELPERS ───────────────────────────────────────────────────────────────────

def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(list(seen)), f, indent=2)

def title_passes(title: str) -> bool:
    t = title.lower()
    if not any(kw in t for kw in POSITIVE_KEYWORDS):
        return False
    if any(re.search(pat, t) for pat in NEGATIVE_PATTERNS):
        return False
    return True

def location_ok(loc: str) -> bool:
    if not loc or not loc.strip():
        return True
    return any(kw in loc.lower() for kw in LOCATION_KEYWORDS)

def everify_badge(company: str) -> str:
    return "✅ E-Verify" if company.lower() in EVERIFY_CONFIRMED else "❓ Check E-Verify"

# ── FETCH: GREENHOUSE ─────────────────────────────────────────────────────────

def fetch_greenhouse(company: str, slug: str) -> list:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return []
        results = []
        for j in r.json().get("jobs", []):
            results.append({
                "title":    j.get("title", ""),
                "url":      j.get("absolute_url", ""),
                "company":  company,
                "location": j.get("location", {}).get("name", ""),
                "content":  (j.get("content") or "")[:2000],
                "source":   "Greenhouse",
            })
        return results
    except Exception as e:
        print(f"  Greenhouse error ({company}): {e}")
        return []

# ── FETCH: INDEED RSS ─────────────────────────────────────────────────────────

def fetch_indeed_rss(query: str, location: str) -> list:
    q   = query.replace(" ", "+")
    loc = location.replace(", ", "%2C+").replace(" ", "+")
    url = f"https://rss.indeed.com/rss?q={q}&l={loc}&sort=date&fromage=1&limit=20"
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return []
        root    = ET.fromstring(r.content)
        results = []
        for item in root.findall(".//item"):
            title_el  = item.find("title")
            link_el   = item.find("link")
            desc_el   = item.find("description")
            raw_title = (title_el.text or "") if title_el is not None else ""
            parts     = raw_title.rsplit(" - ", 1)
            title     = parts[0].strip()
            company   = parts[1].strip() if len(parts) > 1 else "Unknown"
            raw_desc  = (desc_el.text or "") if desc_el is not None else ""
            desc      = re.sub(r"<[^>]+>", " ", raw_desc).strip()[:1500]
            results.append({
                "title":    title,
                "url":      (link_el.text or "") if link_el is not None else "",
                "company":  company,
                "location": location,
                "content":  desc,
                "source":   "Indeed",
            })
        return results
    except Exception as e:
        print(f"  Indeed error ({query}): {e}")
        return []

# ── FETCH ALL ─────────────────────────────────────────────────────────────────

def fetch_all_jobs() -> list:
    all_jobs = []
    print("  Greenhouse...")
    for company, slug in GREENHOUSE_SLUGS:
        jobs = fetch_greenhouse(company, slug)
        if jobs:
            print(f"    {company}: {len(jobs)}")
        all_jobs.extend(jobs)
    print("  Indeed RSS...")
    for query, location in INDEED_QUERIES:
        jobs = fetch_indeed_rss(query, location)
        if jobs:
            print(f"    '{query}' / {location}: {len(jobs)}")
        all_jobs.extend(jobs)
    return all_jobs

# ── FILTER ────────────────────────────────────────────────────────────────────

def filter_jobs(jobs: list, seen: set) -> list:
    filtered  = []
    seen_urls = set()
    for j in jobs:
        url = j.get("url", "")
        if not url or url in seen or url in seen_urls:
            continue
        if not title_passes(j["title"]):
            continue
        if j["location"] and not location_ok(j["location"]):
            continue
        filtered.append(j)
        seen_urls.add(url)
    return filtered

# ── GEMINI SCORING ────────────────────────────────────────────────────────────

def score_with_gemini(candidates: list) -> list:
    if not candidates:
        return []
    job_list = ""
    for i, j in enumerate(candidates[:20]):
        job_list += f"\n[{i}] {j['title']} @ {j['company']} | {j['location']}\n"
        if j["content"]:
            job_list += j["content"][:600] + "\n"
    prompt = f"""{MEG_PROFILE}

Review these job listings. Return ONLY a valid JSON array — no markdown, no explanation.
Format: [{{"index": 0, "score": 85, "reason": "one sentence on fit"}}]
Return top 7 by score only.

JOBS:
{job_list}
"""
    api_url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    )
    try:
        r    = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        raw  = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        raw  = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)
        data.sort(key=lambda x: x.get("score", 0), reverse=True)
        return data[:7]
    except Exception as e:
        print(f"  Gemini error: {e}")
        return []

# ── SLACK POST ────────────────────────────────────────────────────────────────

def post_to_slack(scored: list, candidates: list, batch_jobs: list, total: int, on_demand: bool = False):
    hour  = datetime.utcnow().hour
    emoji = "⚡" if on_demand else ("☀️" if hour < 18 else "🌆")
    label = "On-Demand Scan" if on_demand else f"Job Drop — {datetime.utcnow().strftime('%b %d')}"

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{emoji} {label}"}},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"*{total}* new jobs · *{len(scored)}* top picks · *{len(batch_jobs)}* batch"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": "*⭐ TOP PICKS*"}},
    ]

    for item in scored:
        idx = item.get("index", -1)
        if idx < 0 or idx >= len(candidates):
            continue
        j = candidates[idx]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": (
                f"*<{j['url']}|{j['title']}>*\n"
                f"{j['company']} · {j['location'] or 'Remote'} · "
                f"{everify_badge(j['company'])} · _{j['source']}_\n"
                f"_{item.get('reason', '')}_"
            )}
        })

    if batch_jobs:
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*📋 BATCH*"}})
        chunk, chunk_len = [], 0
        for j in batch_jobs[:40]:
            line = f"• <{j['url']}|{j['title']}> — {j['company']} · {j['location'] or 'Remote'} · {everify_badge(j['company'])}"
            if chunk_len + len(line) > 2800:
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(chunk)}})
                chunk, chunk_len = [], 0
            chunk.append(line)
            chunk_len += len(line)
        if chunk:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(chunk)}})

    requests.post(SLACK_WEBHOOK, json={"blocks": blocks}, timeout=10)

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    on_demand = os.environ.get("ON_DEMAND", "false").lower() == "true"
    print(f"\nJob Bot — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} {'(on-demand)' if on_demand else ''}")

    seen     = load_seen()
    all_jobs = fetch_all_jobs()
    new_jobs = filter_jobs(all_jobs, seen)

    print(f"Fetched: {len(all_jobs)} | New after filter: {len(new_jobs)}")

    if not new_jobs:
        if on_demand:
            requests.post(SLACK_WEBHOOK, json={"text": "⚡ Nothing new since last scan. Check back later!"}, timeout=10)
        else:
            print("Nothing new. Skipping Slack post.")
        return

    candidates = new_jobs[:20]
    scored     = score_with_gemini(candidates)
    scored_idx = {s["index"] for s in scored}
    batch_jobs = [j for i, j in enumerate(new_jobs) if i not in scored_idx]

    post_to_slack(scored, candidates, batch_jobs, len(new_jobs), on_demand=on_demand)

    for j in new_jobs:
        seen.add(j["url"])
    save_seen(seen)
    print("Done.")

if __name__ == "__main__":
    main()
