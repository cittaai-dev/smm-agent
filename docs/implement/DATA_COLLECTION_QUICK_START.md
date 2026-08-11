# Data Collection Quick Start — Steps 5-6

**What changed:** Steps 5 and 6 now integrate live data collection with trust boundaries and production
status streaming. The agent can automatically discover competitors, extract metrics, and chunk data into Core KB.

## 1. Setup: One-Time Configuration per Brand

### Add API Credentials (Encrypted)

```python
# Python API call or UI form — saves credentials encrypted
POST /api/brands/{brand_id}/data-sources/credentials
{
  "source": "google_trends",
  "api_key": "optional—Trends doesn't need one",
  "rate_limit_per_hour": 60
}

POST /api/brands/{brand_id}/data-sources/credentials
{
  "source": "newsapi",
  "api_key": "your-newsapi-key-from-newsapi.org",
  "rate_limit_per_hour": 100
}

POST /api/brands/{brand_id}/data-sources/credentials
{
  "source": "youtube",
  "api_key": "your-youtube-api-key-from-google-cloud",
  "rate_limit_per_hour": 200
}
```

### Define Competitor Market Segment

```python
# Step 5 Part D §5 — confines competitor discovery to explicit whitelist
POST /api/brands/{brand_id}/market-segments
{
  "segment_name": "fitness_wellness",
  "youtube_channel_keywords": [
    "vegan fitness",
    "plant-based wellness",
    "athletic recovery"
  ],
  "news_sources": [
    "techcrunch.com",
    "forbes.com",
    "medium.com"
  ],
  "reddit_communities": [
    "r/fitness",
    "r/vegan",
    "r/bodyweightfitness"
  ],
  "website_urls": [
    "competitor-a.com/blog",
    "competitor-b.com"
  ],
  "max_competitors_to_track": 5
}
```

**Key constraint:** Competitor discovery is bounded to this segment. Open-ended crawling is not allowed.

## 2. Watch Live Data Collection

### UI: Live Run Page

After starting a data collection job, navigate to:

```
http://localhost:3000/brands/{brand_id}/live-run
```

You'll see **real-time status updates:**

```
🔍 Discovering competitors...
  Found 3 YouTube channels
  Found 8 news articles
  Found 12 Reddit discussions

📥 Extracting data...
  Fetching YouTube analytics... ✓ 245 posts
  Fetching news content... ✓ 89 articles
  Crawling competitor sites... ⏳

📦 Chunking and embedding...
  Processing 334 raw items... ✓
  Embedding 324 chunks... ✓

✅ Complete — 324 chunks ingested to market-intel@v1
Staleness: all data < 2 hours old
```

### WebSocket: Raw Status Feed

```typescript
// React hook (see step6.md §4)
const status = useDataCollectionStatus(brandId);

// Messages stream in real-time:
// { timestamp, message, phase, item_count }
```

## 3. How Data Gets to Synthesis

### Data Collection → Core KB → Synthesis

```
Google Trends (weekly)
  ↓ discover trending keywords
  ↓ chunks: { "fitness" trend +12% YoY, ... }
  ↓ ingested to core:market-intel@v1
  
NewsAPI (daily)
  ↓ discover brand + competitor mentions
  ↓ chunks: { "Competitor X launches new product", ... }
  ↓ ingested to core:market-intel@v1
  
YouTube API (daily)
  ↓ discover owned + competitor channels
  ↓ chunks: { "Owned channel: 487k followers, 3.2% engagement", ... }
  ↓ ingested to core:market-intel@v1
  
Competitor crawl (weekly)
  ↓ scrape whitelisted sites (robots.txt aware)
  ↓ chunks: { "Competitor A blog: Q3 strategy pivot to TikTok", ... }
  ↓ ingested to core:market-intel@v1

All chunks carry: { collected_at, valid_until, data_source, chunk_id, text }
```

When synthesis runs (Step 3), it searches Core KB with freshness filters (Step 5 Part D §6):

```
"Get market share trends"
  → retrieval.hybrid_search() finds 15 chunks
  → filter: only chunks where valid_until > now()
  → if < MIN_GROUNDING (e.g., 3 chunks), degrade to insufficient_grounding
  → else synthesize with claims
```

## 4. Data Freshness & Staleness

### TTL Model

```python
# Every collected datum has:
collected_at = datetime.utcnow()  # when it was pulled
valid_until = datetime.utcnow() + timedelta(hours=24)  # expires after 24h

# Synthesis won't use data older than valid_until
# If all evidence is stale → "data_staleness" degradation → auto-retry collection job
```

### Monitor Staleness

```
Health endpoint: GET /health/data-sources

Response:
{
  "youtube": {
    "last_run": "2024-03-15T02:00:00Z",
    "staleness_hours": 2.5,
    "status": "ok",  # < 24h
    "error_rate_24h": 0.02,
    "chunks_collected_24h": 245
  },
  "newsapi": {
    "last_run": "2024-03-14T14:30:00Z",
    "staleness_hours": 35.5,
    "status": "stale",  # > 24h — ALERT
    "error_rate_24h": 0.08,
    "chunks_collected_24h": 89
  }
}
```

**Alert fires if any source > 24h old.** Check logs, verify API credentials, retry via:**

```bash
curl -X POST http://localhost:8000/api/admin/retry-collection-job \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"brand_id": "brand-x", "source": "newsapi"}'
```

## 5. What Happens if a Data Source Fails?

### Graceful Degradation (P5)

```python
# Step 6 Part B §3 — error handling

If YouTube API fails:
  ✓ log error, mark job phase as "failed"
  ✓ continue with NewsAPI, trends, crawls (don't cascade fail)
  ✓ synthesis uses whatever data *did* come through
  ✓ if too little data, degrade to insufficient_grounding (not crash)

If ALL sources fail:
  ✗ collection_job status = "failed"
  → manual retry available via health dashboard
  → synthesis skips live data, uses cached Core KB chunks
  → output = partial, but not a hard failure
```

### Rate Limiting

Each source has per-brand rate limits:

```python
# Step 5 Part D §7
Credentials {
  source: "youtube",
  rate_limit_per_hour: 200
}

If you hit the limit:
  → task backs off exponentially (1 min, 5 min, 15 min)
  → retries automatically
  → never drops data
```

## 6. Cost: Free & Open-Source Stack

| Source | Cost | Latency | Notes |
|--------|------|---------|-------|
| **Google Trends** | Free | Varies | No API key needed; unofficial pytrends client |
| **NewsAPI** | Free–$50/mo | Real-time | 100 req/day free; paid tiers available |
| **YouTube API** | Free (quota limited) | Real-time | 10k quota/day; 1 call = 1–100 units |
| **Competitor Crawl** | $0 | Hourly | Self-hosted Scrapy + BeautifulSoup; respect robots.txt |

**Total for MVP:** $0–$50/mo if you upgrade NewsAPI to paid tier.

## 7. Schedule: Automated Jobs

### Default Beat Schedule (Step 6 Part B)

```python
# runs automatically, no manual trigger needed

Daily (5 AM UTC):
  collect_all_for_brand_batch() → runs for all active brands
  
Weekly (Sundays, 3 AM UTC):
  discover_competitors_batch() → refreshes competitor list per segment
  
On-demand:
  POST /api/brands/{brand_id}/collect-now → trigger immediately
```

## 8. Tests — What to Validate

### End-to-End Test Suite (Step 5 §15 + Step 6 §12)

```python
# Run once after setup to verify the pipeline works

test_competitor_discovery_respects_segment_whitelist()
test_stale_data_degrades_to_insufficient_grounding()
test_data_collection_phases_broadcast_correctly()
test_data_source_health_endpoint_shows_staleness()
test_rate_limit_blocks_and_retries()
```

Run via:

```bash
cd backend
pytest tests/ -k "data_collection or live_run" -v
```

## 9. Migration Path to Premium Data Providers (Step 7+)

Once this foundation is solid, adding paid providers is mechanical:

```python
# Step 7+: Rivals IQ for real-time competitor metrics

1. Add new data source type: "data_provider"
2. Create worker: workers/data_providers/rivals_iq.py
3. Register in beat schedule
4. Credentials: POST /api/brands/{brand_id}/data-sources/credentials
5. Data automatically chunks and ingests to Core KB
6. No changes to synthesis, retrieval, or UI

Same architecture, different data source.
```

---

## Quick Troubleshooting

| Issue | Fix |
|-------|-----|
| Data isn't updating (stale warning) | Check `/health/data-sources`, verify API credentials in Settings, manually retry with `/collect-now` |
| "Found 0 competitors" | Review market segment whitelist — keywords/sites may be too narrow |
| Synthesis says "data_staleness" | Collection job failed; check Celery logs, verify rate limits, retry |
| WebSocket shows "extract" forever | Check worker pool size; may be queued behind other jobs |
| API rate limit errors in logs | Increase `rate_limit_per_hour` in credentials, or upgrade to paid plan |

---

**Next:** When Step 7 ships, you'll add Rivals IQ ($400/mo) for real-time competitor metrics. The foundation
is ready.
