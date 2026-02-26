# News Crawler — Cloud Functions + BigQuery

A **learning project** for crawling news, storing data in Google BigQuery, and running crawlers on Cloud Functions (simple) and Cloud Run (headless browser).

> **Disclaimer:** This project is for **educational and learning purposes only**. If any content or use infringes your rights, please contact the author for **immediate removal**.

---

## Features

- **Serverless**: Cloud Functions for on-demand runs
- **Storage**: BigQuery with date partitioning and SQL access
- **Deduplication**: In-memory link cache at startup + partition-aware queries
- **Concurrency**: Multiple sources run in parallel
- **Scheduling**: Cloud Scheduler (e.g. every 10–30 minutes)
- **Low cost**: Roughly **$4–7/month** for the simple setup

## Tech Stack

- **Runtime**: Python 3.11
- **Compute**: Google Cloud Functions (Gen 2), Cloud Run (browser)
- **Database**: Google BigQuery (partitioned by date)
- **Scheduling**: Google Cloud Scheduler
- **Dependencies**: BeautifulSoup4, requests, google-cloud-bigquery; Playwright + Firefox for browser crawlers

## Project Structure

```
news-google/
├── main.py                      # Dual entry: crawl_news (simple) + crawl_news_browser (headless)
├── Makefile                     # Local run & deploy (make run / deploy / deploy-browser)
├── requirements.txt             # Simple crawler deps
├── requirements-browser.txt    # Headless browser deps (playwright, etc.)
├── config.yaml                  # Config (GCP, concurrency)
├── scrapers/
│   ├── base_scraper.py
│   ├── simple/                  # Simple crawlers (requests/BeautifulSoup, no browser)
│   │   ├── techcrunch.py
│   │   ├── apnews.py
│   │   └── coinlive.py
│   └── browser/                 # Headless browser crawlers (Playwright, crawl_news_browser only)
│       ├── base_browser_scraper.py
│       ├── stcn.py
│       ├── koreatimes.py
│       └── __init__.py          # SCRAPER_REGISTRY_BROWSER
├── utils/
└── deploy/
    ├── deploy.sh                # Deploy crawl-news (simple) → Cloud Functions
    ├── deploy_cloudrun_browser.sh  # Browser crawler → Cloud Run (+ Scheduler)
    ├── setup_scheduler.sh        # Schedule crawl-news
    └── create_bigquery_table.sql
└── Dockerfile.firefox           # Cloud Run image (Firefox only)
```

**Two entry points (separate dependencies)**

| Type              | Entry                 | Deps                         | Deploy target        |
|-------------------|-----------------------|-----------------------------|----------------------|
| Simple crawlers   | `crawl_news`         | requirements.txt            | Cloud Functions       |
| Headless browser  | `crawl_news_browser` | requirements-browser + browser binary | Cloud Run (Dockerfile.firefox) |

Headless crawlers need Playwright’s browser binary → deploy via **Cloud Run + Dockerfile.firefox**.

## Quick Start

### 1. Prerequisites

- Install [Google Cloud SDK](https://cloud.google.com/sdk) and log in:
  ```bash
  gcloud auth login
  gcloud auth application-default login
  ```
- Set env and config:
  ```bash
  export GCP_PROJECT_ID="your-project-id"
  export GCP_REGION="us-central1"
  ```
  Edit `config.yaml` and replace `your-project-id` with your GCP project ID.

### 2. Create BigQuery resources

```bash
bq query --use_legacy_sql=false < deploy/create_bigquery_table.sql
```

### 3. Deploy

**Using Makefile (recommended)**
```bash
make deploy              # Simple crawler → Cloud Functions
make deploy-browser      # Browser crawler → Cloud Run + Scheduler
make deploy-all         # Both
```

**Or run scripts directly**
```bash
sh deploy/deploy.sh
sh deploy/deploy_cloudrun_browser.sh
```

- Simple crawler schedule (e.g. every 10 min): `./deploy/setup_scheduler.sh`
- Browser crawler: Scheduler is set up by `deploy_cloudrun_browser.sh` (e.g. every 30 min).

### 4. Test

**Trigger via HTTP**
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"sources": "techcrunch"}' \
  https://REGION-PROJECT.cloudfunctions.net/crawl-news

curl -X POST -H "Content-Type: application/json" \
  -d '{"sources": "all"}' \
  https://REGION-PROJECT.cloudfunctions.net/crawl-news
```

**Local run** (from repo root; GCP auth required for non-test)

- Simple crawlers: `make run` or `uv run python main.py`
- Browser crawlers: `make install-browser` once, then `make run-browser` or `uv run python main.py browser`  
  Local default is `test=True` (no BigQuery writes).

### 5. Query data

Table is partitioned by `pub_date`; queries must include a `pub_date` filter.

```sql
SELECT title, link, source, pub_date, crawled_at
FROM `YOUR_PROJECT_ID.news_project.news_articles`
WHERE DATE(pub_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
ORDER BY crawled_at DESC
LIMIT 20;

SELECT source, COUNT(*) AS cnt
FROM `YOUR_PROJECT_ID.news_project.news_articles`
WHERE DATE(pub_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY source
ORDER BY cnt DESC;
```

## Supported sources

**Simple (Cloud Functions)**  
- techcrunch, apnews, coinlive  

**Headless browser (Cloud Run)**  
- stcn, koreatimes  

## Adding a new crawler

- **Simple**: Add a module under `scrapers/simple/`, extend `BaseScraper`, register in `main.py` → `SCRAPER_REGISTRY`, then `make deploy`.
- **Browser**: Add a module under `scrapers/browser/`, extend `BaseBrowserScraper` and implement `_run_impl()`, register in `scrapers/browser/__init__.py` → `SCRAPER_REGISTRY_BROWSER`, then `make deploy-browser`.

Example (simple):

```python
# scrapers/simple/example.py
from scrapers.base_scraper import BaseScraper

class ExampleScraper(BaseScraper):
    def __init__(self, bq_client):
        super().__init__('example', bq_client)

    def run(self):
        new_articles = []
        # ... fetch data, use self.is_link_exists(link) for dedup ...
        if new_articles:
            self.save_articles(new_articles)
        return self.get_stats()
```

Register in `main.py`: `from scrapers.simple.example import ExampleScraper` and add to `SCRAPER_REGISTRY`.

## Cost (approx.)

- Cloud Functions: ~$3–5/month
- BigQuery: ~$1–2/month  
- **Total**: about **$4–7/month** for the simple pipeline. Cloud Run adds cost based on usage.

## Deduplication

- At startup, latest 20 URLs per source are loaded into memory; link existence checks use this cache to reduce BigQuery calls.
- Table is partitioned by `pub_date`; all queries must include a partition filter.

## Monitoring

```bash
bq query --use_legacy_sql=false \
  "SELECT source, COUNT(*) as count
   FROM \`YOUR_PROJECT_ID.news_project.news_articles\`
   WHERE DATE(pub_date) >= CURRENT_DATE()
   GROUP BY source"
```

## Troubleshooting

- **BigQuery errors**: Check table exists (`bq show news_project.news_articles`) and service account permissions.
- **Timeouts**: Increase function timeout (e.g. `--timeout=540s`) or reduce `max_workers` in `config.yaml`.

## References

- [Cloud Functions](https://cloud.google.com/functions/docs)
- [BigQuery](https://cloud.google.com/bigquery/docs)
- [Cloud Scheduler](https://cloud.google.com/scheduler/docs)

## License

MIT License. This is a learning project; if you believe any use infringes your rights, please contact the author for immediate removal.
