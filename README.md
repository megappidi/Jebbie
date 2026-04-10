# Job Bot

Finds relevant jobs from Greenhouse + Indeed RSS. Posts to Slack at **9:30am and 7pm EST** daily.  
Type `/jobs` in Slack for an on-demand scan anytime.

Zero scraping. Zero monthly cost.

---

## One-time setup (~15 min total)

---

### Step 1 — Create a private GitHub repo

1. Go to github.com → **New repository**
2. Name it `job-bot`, set to **Private**
3. Upload all files from this folder, keeping the folder structure:
   ```
   job-bot/
   ├── job_bot.py
   ├── seen_jobs.json
   ├── requirements.txt
   ├── vercel.json
   ├── api/
   │   └── index.py
   └── .github/
       └── workflows/
           └── job-scan.yml
   ```

---

### Step 2 — Add secrets to GitHub

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `SLACK_WEBHOOK` | Your Slack webhook URL |
| `GEMINI_API_KEY` | Your Gemini API key |

---

### Step 3 — Create a GitHub Personal Access Token (for /jobs command)

1. Go to **github.com → Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. Click **Generate new token (classic)**
3. Name it `job-bot-dispatch`
4. Check these scopes: `repo` and `workflow`
5. Copy the token — you'll need it in Step 5

---

### Step 4 — Deploy to Vercel (for /jobs Slack command)

1. Go to **vercel.com** → sign up free with your GitHub account
2. Click **Add New Project** → import your `job-bot` repo
3. Click **Deploy** (defaults are fine)
4. Once deployed, copy your Vercel URL — looks like `https://job-bot-xyz.vercel.app`

---

### Step 5 — Add env vars to Vercel

Go to your Vercel project → **Settings → Environment Variables**

| Variable | Value |
|---|---|
| `GITHUB_PAT` | Your token from Step 3 |
| `GITHUB_REPO` | `yourusername/job-bot` |
| `SLACK_WEBHOOK` | Same webhook URL as GitHub |
| `GEMINI_API_KEY` | Same Gemini key as GitHub |

After adding them, go to **Deployments → Redeploy** so the vars take effect.

---

### Step 6 — Create the /jobs Slack slash command

1. Go to **api.slack.com/apps** → open your job-bot app
2. Left sidebar → **Slash Commands → Create New Command**
3. Fill in:
   - **Command:** `/jobs`
   - **Request URL:** `https://your-vercel-url.vercel.app/jobs`
   - **Short Description:** `Scan for new jobs now`
4. Save
5. Reinstall the app to your workspace when prompted

---

### Step 7 — Test it

**Test the scheduled bot:**
Go to GitHub repo → **Actions → Job Bot → Run workflow** → click the button.
Check your Slack in ~90 seconds.

**Test /jobs:**
Open Slack, type `/jobs` in your channel. You should see "Scanning now..." and results ~90 seconds later.

---

## Customizing

**Add a Greenhouse company:**
Find their slug in their careers URL (e.g. `jobs.greenhouse.io/notion` → slug is `notion`).
Add to `GREENHOUSE_SLUGS` in `job_bot.py`.

**Add an Indeed search:**
Add `("query terms", "City, ST")` to `INDEED_QUERIES` in `job_bot.py`.

**Adjust title filters:**
Edit `POSITIVE_KEYWORDS` or `NEGATIVE_PATTERNS` in `job_bot.py`.

**Mark a company as E-Verify confirmed:**
Add the company name (lowercase) to `EVERIFY_CONFIRMED` in `job_bot.py`.

---

## Cost breakdown

| Service | Cost |
|---|---|
| GitHub Actions | Free (2000 min/month) |
| Greenhouse API | Free, public |
| Indeed RSS | Free, public |
| Gemini 1.5 Flash | Free tier |
| Vercel | Free tier |
| Slack | Free |

**Total: $0/month**

---

## Notes

- Google, Microsoft, YouTube, and Netflix are caught via Indeed RSS (they don't use Greenhouse)
- Bad Greenhouse slugs are skipped silently — the bot won't crash
- `seen_jobs.json` is auto-committed back to the repo after each run to prevent duplicates
- The `/jobs` command shows jobs not yet in your seen list — if you ran it recently, results may be sparse
