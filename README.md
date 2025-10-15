# 🤖 Social Media Auto Crawler

Automated crawler for Facebook, Shopee, TikTok, and YouTube using Playwright and MongoDB.

## 📋 Features

- ✅ Facebook post scraping with GraphQL interception
- 🗄️ MongoDB storage with metrics tracking
- 🤖 GitHub Actions automation
- 📊 Trending posts analysis
- 🔍 Multi-keyword search support

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Python 3.11+
python --version

# MongoDB (local or cloud)
# Get free MongoDB Atlas: https://www.mongodb.com/cloud/atlas
```

### 2. Installation

```bash
# Clone repository
git clone <your-repo>
cd auto-crawler

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 3. Configuration

Create `.env` file:

```env
# MongoDB Configuration
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/
MONGO_DB=facebook_scraper

# Facebook Configuration
FACEBOOK_COOKIE=c_user=123456789; xs=12%3Aabcd...; datr=xyz123...; sb=abc...
FACEBOOK_KEYWORDS=tủ lạnh,máy giặt,nồi cơm điện

# Crawler Settings
MAX_SCROLLS=5
SCROLL_DELAY=2500
LOG_LEVEL=INFO
```

### 4. Get Facebook Cookie

**Method 1: Chrome DevTools**
1. Open Facebook in Chrome
2. Login to your account
3. Press `F12` → `Application` tab → `Cookies` → `https://www.facebook.com`
4. Copy all cookies in format: `name1=value1; name2=value2; ...`

**Important cookies:**
- `c_user` - User ID
- `xs` - Session token
- `datr` - Device token
- `sb` - Session browser

**Method 2: Cookie Editor Extension**
1. Install "Cookie Editor" extension
2. Login to Facebook
3. Click extension → Export → Copy as `Netscape` format
4. Convert to format: `name=value; name2=value2; ...`

### 5. Run Locally

```bash
# Test with debug output
python test_facebook.py

# Run full crawler
python -m src.main facebook

# Run all platforms (when implemented)
python -m src.main all
```

## 🔧 GitHub Actions Setup

### 1. Set Repository Secrets

Go to: **Settings → Secrets and variables → Actions → New repository secret**

Add these secrets:

| Secret Name | Description | Example |
|------------|-------------|---------|
| `MONGO_URI` | MongoDB connection string | `mongodb+srv://user:pass@cluster.mongodb.net/` |
| `MONGO_DB` | Database name | `facebook_scraper` |
| `FACEBOOK_COOKIE` | Full Facebook cookie string | `c_user=123; xs=abc; datr=xyz; sb=def` |
| `FACEBOOK_KEYWORDS` | Comma-separated keywords | `tủ lạnh,máy giặt,nồi cơm điện` |

### 2. Verify Cookie

**Test cookie validity:**
```bash
# Set cookie
export FACEBOOK_COOKIE="your_cookie_here"

# Quick test
python test_facebook.py
```

**Cookie should include at least:**
- `c_user` (User ID)
- `xs` (Session - most important)
- `datr` (Device)
- `sb` (Secure browser)

### 3. Trigger Workflow

**Manual trigger:**
1. Go to **Actions** tab
2. Select **Facebook Crawler**
3. Click **Run workflow**
4. Set `max_scrolls` (default: 5)

**Automatic schedule:**
- Runs every 6 hours: 0:00, 6:00, 12:00, 18:00 UTC

## 🐛 Troubleshooting

### ❌ Empty Results (`facebook_posts.json` = `[]`)

**Check logs:**
```bash
# Download artifacts from GitHub Actions
# Extract and check: facebook-logs-XXX/facebook_scraper_YYYYMMDD.log
```

**Common issues:**

#### 1. Cookie Expired/Invalid
**Symptoms:**
- Redirected to login page
- Screenshot shows "Log in to continue"

**Solution:**
```bash
# Get fresh cookie
1. Clear browser cookies
2. Login to Facebook again
3. Copy new cookie string
4. Update GitHub secret FACEBOOK_COOKIE
```

#### 2. Bot Detection
**Symptoms:**
- Security checkpoint
- "Unusual activity detected"

**Solutions:**
- Use cookie from personal account (not business)
- Don't scrape too frequently
- Reduce `MAX_SCROLLS` to 3
- Add delays between runs

#### 3. GraphQL Not Captured
**Symptoms:**
- Log shows "0 responses captured"
- Screenshots look normal

**Solution:**
```bash
# Increase wait times in workflow
# Edit .github/workflows/crawl-facebook.yml
timeout-minutes: 60  # Increase from 45
```

#### 4. Network Timeout
**Symptoms:**
- "timeout" errors in logs
- Workflow times out

**Solution:**
- Check MongoDB connection
- Verify network settings
- Increase timeout