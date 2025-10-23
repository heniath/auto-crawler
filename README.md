# 🤖 Social Media Auto Crawler

Automated crawler for Facebook, YouTube, TikTok, and Shopee using Playwright and MongoDB.

## 📋 Features

- ✅ **Facebook**: Post scraping with GraphQL interception
- ✅ **YouTube**: Video scraping via YouTube Data API v3
- ✅ **TikTok**: Video scraping with network interception
- ✅ **Shopee**: Product scraping with network interception
- 🗄️ MongoDB storage with master/history pattern
- 🤖 GitHub Actions automation
- 📊 Trending content analysis
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
MONGO_DB=social_media_data

# Database names for each platform
FACEBOOK_DB=facebook_data
YOUTUBE_DB=youtube_data
SHOPEE_DB=shopee_data
TIKTOK_DB=TikTok_Data

# Facebook Configuration
FACEBOOK_COOKIE=c_user=123456789; xs=12%3Aabcd...; datr=xyz123...; sb=abc...
FACEBOOK_KEYWORDS=tủ lạnh,máy giặt,nồi cơm điện

# YouTube Configuration
YOUTUBE_API_KEYS=AIzaSyXXXXXXXXXXXXXXXXXXXXXX
YOUTUBE_KEYWORDS=Nồi cơm điện,Tủ lạnh,Bếp,Máy giặt
YOUTUBE_MAX_VIDEOS_PER_KEYWORD=400

# Shopee Configuration
SHOPEE_CATEGORIES=Tủ lạnh,Bếp,Máy giặt,Quạt,Ấm siêu tốc,Nồi cơm điện
SHOPEE_HEADLESS=true
SHOPEE_VARIANTS_PER_CATEGORY=10
SHOPEE_MAX_PAGES_PER_VARIANT=2
SHOPEE_TARGET_PER_CATEGORY=500

# TikTok Configuration
TIKTOK_KEYWORDS=Tủ lạnh,Bếp,Máy giặt,Quạt,Ấm siêu tốc
TIKTOK_HEADLESS=true
TIKTOK_TARGET_PER_CATEGORY=100

# Crawler Settings
MAX_SCROLLS=5
LOG_LEVEL=INFO
```

### 4. Run Locally

```bash
# Run Facebook crawler
python -m src.main facebook

# Run YouTube crawler
python -m src.main youtube

# Run TikTok crawler
python -m src.main tiktok

# Run Shopee crawler
python -m src.main shopee

# Run all crawlers
python -m src.main all
```

## 📚 Platform-Specific Setup

### Facebook

**Get Facebook Cookie:**

1. Open Facebook in Chrome
2. Login to your account
3. Press `F12` → `Application` tab → `Cookies` → `https://www.facebook.com`
4. Copy: `c_user`, `xs`, `datr`, `sb` cookies
5. Format: `c_user=123; xs=abc; datr=xyz; sb=def`

### YouTube

**Get YouTube API Key:**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable "YouTube Data API v3"
4. Create credentials → API Key
5. Copy the API key to `.env`

**Multiple API Keys:**
```env
YOUTUBE_API_KEYS=key1,key2,key3
```
The scraper will automatically rotate keys when quota is exceeded.

### TikTok

**No API key required!** TikTok crawler uses Playwright to intercept network responses.

**Configuration options:**
- `TIKTOK_HEADLESS=true`: Run browser in background (recommended for production)
- `TIKTOK_HEADLESS=false`: Show browser window (useful for debugging)
- `TIKTOK_TARGET_PER_CATEGORY=100`: Number of videos to collect per keyword

### Shopee

**No API key required!** Shopee crawler uses Playwright to intercept network responses.

**Configuration options:**
- `SHOPEE_HEADLESS=true`: Run browser in background (recommended for production)
- `SHOPEE_HEADLESS=false`: Show browser window (useful for debugging)
- `SHOPEE_CATEGORIES`: Comma-separated product categories
- `SHOPEE_VARIANTS_PER_CATEGORY=10`: Number of keyword variations per category
- `SHOPEE_MAX_PAGES_PER_VARIANT=2`: Max pages to scrape per keyword variant
- `SHOPEE_TARGET_PER_CATEGORY=500`: Target number of products per category

**How it works:**
1. Generates keyword variations (e.g., "tủ lạnh", "tủ lạnh giá rẻ", "mua tủ lạnh")
2. Searches each variation across multiple pages
3. Intercepts API responses to capture product data
4. Stores products in master collection with history snapshots

## 🔧 GitHub Actions Setup

### 1. Set Repository Secrets

Go to: **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Description | Required For |
|------------|-------------|--------------|
| `MONGO_URI` | MongoDB connection string | All platforms |
| `FACEBOOK_COOKIE` | Facebook cookie string | Facebook |
| `FACEBOOK_KEYWORDS` | Comma-separated keywords | Facebook |
| `YOUTUBE_API_KEYS` | Comma-separated API keys | YouTube |
| `YOUTUBE_KEYWORDS` | Comma-separated keywords | YouTube |
| `SHOPEE_CATEGORIES` | Comma-separated categories | Shopee |
| `TIKTOK_KEYWORDS` | Comma-separated keywords | TikTok |

### 2. Trigger Workflows

**Manual trigger:**
1. Go to **Actions** tab
2. Select the desired workflow (Facebook/YouTube/TikTok/Shopee/All)
3. Click **Run workflow**

**Automatic schedules:**
- **Facebook**: Every 6 hours (0:00, 6:00, 12:00, 18:00 UTC)
- **YouTube**: Twice daily (7:00, 19:00 UTC)
- **TikTok**: Twice daily (1:00, 13:00 UTC)
- **Shopee**: Twice daily (4:00, 16:00 UTC)
- **All Crawlers**: Daily at 2:00 AM UTC

## 📊 Database Structure

### Facebook Database (`facebook_data`)

**Collections:**
- `posts`: Master collection (unique posts)
- `metrics_snapshot`: Historical metrics snapshots

### YouTube Database (`youtube_data`)

**Collections:**
- `videos`: Master collection (unique videos)
- `snapshots`: Historical metrics snapshots

### Shopee Database (`shopee_data`)

**Collections:**
- `Shopee_ProductCategory`: Master collection (unique products)
- `Shopee_ProductCategory_History`: Historical price/metrics snapshots

**Document Structure:**
```javascript
// Master Collection
{
  "itemid": 123456789,
  "shopid": 987654321,
  "name": "Tủ lạnh Samsung 234L",
  "price": 5990000,
  "price_before_discount": 7990000,
  "discount": "25%",
  "sold_recent": 150,
  "sold_total": 2500,
  "rating_star": 4.8,
  "rating_count": 320,
  "flash_sale": false,
  "ctime": "2024-01-15",
  "category": "Tủ lạnh",
  "first_day_crawling": "2025-01-01 10:00:00",
  "last_day_crawling": "2025-01-15 14:30:00"
}

// History Collection
{
  "itemid": 123456789,
  "price": 5990000,
  "sold_recent": 150,
  "rating_star": 4.8,
  "category": "Tủ lạnh",
  "crawl_date": "2025-01-15 14:30:00"
}
```

### TikTok Database (`TikTok_Data`)

**Collections:**
- `Video_Category`: Master collection (unique videos)
- `Video_Category_Details_History`: Historical metrics snapshots

## 🐛 Troubleshooting

### Shopee Issues

#### No products collected
**Check:**
1. Network connectivity
2. Shopee might be blocking your IP (try using proxy)
3. Increase `SHOPEE_TARGET_PER_CATEGORY` if getting partial results
4. Check if keyword variations are appropriate

#### Browser crashes
**Solution:**
```bash
# Install system dependencies
playwright install-deps chromium
```

#### Rate limiting / CAPTCHA
**Solutions:**
1. Run in headless mode: `SHOPEE_HEADLESS=true`
2. Reduce `SHOPEE_MAX_PAGES_PER_VARIANT`
3. Add delays between requests (already implemented)
4. Use residential proxy if available

### TikTok Issues

#### No videos collected
**Check:**
1. Network connectivity
2. TikTok might be blocking your IP (try using proxy)
3. Increase `TIKTOK_TARGET_PER_CATEGORY` if getting partial results

### YouTube Issues

#### Quota exceeded
**Solution:**
- Add multiple API keys: `YOUTUBE_API_KEYS=key1,key2,key3`
- Each key has 10,000 units/day
- Scraper automatically rotates keys

### Facebook Issues

#### Cookie expired
**Solution:**
1. Clear browser cookies
2. Login to Facebook again
3. Copy fresh cookie
4. Update `FACEBOOK_COOKIE` in `.env` or GitHub secrets

## 📈 Usage Examples

### Python Script

```python
import asyncio
from src.crawlers.shopee.scraper import run_shopee_scraper

# Run Shopee scraper
run_shopee_scraper(
    categories=['Tủ lạnh', 'Máy giặt'],
    headless=True,
    target_per_category=100
)
```

### Command Line

```bash
# Run with custom environment variables
SHOPEE_HEADLESS=false SHOPEE_TARGET_PER_CATEGORY=50 python -m src.main shopee
```

## 🎯 Platform Comparison

| Platform | Method | Auth Required | Quota Limits | Headless |
|----------|--------|---------------|--------------|----------|
| **Facebook** | GraphQL Interception | ✅ Cookie | None | ✅ Yes |
| **YouTube** | Data API v3 | ✅ API Key | 10K units/day | N/A |
| **TikTok** | Network Interception | ❌ None | None | ✅ Yes |
| **Shopee** | Network Interception | ❌ None | None | ✅ Yes |

## 📂 Project Structure

```
auto-crawler/
├── src/
│   ├── crawlers/
│   │   ├── facebook/       # Facebook GraphQL scraper
│   │   ├── youtube/        # YouTube API scraper
│   │   ├── tiktok/         # TikTok network scraper
│   │   └── shopee/         # Shopee network scraper
│   ├── configs/            # Configuration management
│   └── core/               # Database & utilities
├── .github/workflows/      # GitHub Actions
├── logs/                   # Application logs
├── data/                   # Output data
├── .env                    # Environment variables
└── requirements.txt        # Python dependencies
```

## 🔒 Security Notes

- Never commit `.env` file to git
- Rotate API keys regularly
- Use environment-specific secrets in GitHub Actions
- Monitor your MongoDB connection string
- Keep Facebook cookies fresh (they expire)

## 📝 License

MIT License - see LICENSE file for details

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## 📮 Support

For issues and questions:
- Open an issue on GitHub
- Check existing issues for solutions

---

**Made with ❤️ for social media data collection**