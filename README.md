# Social Media Monitoring & Analytics Agent

A complete end-to-end AI Agent and MLOps pipeline for monitoring social media, processing data with machine learning models, and generating intelligent alerts.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Setup Instructions](#setup-instructions)
- [API Integration](#api-integration)
- [ML Model Integration](#ml-model-integration)
- [Database Design](#database-design)
- [Monitoring & Logging](#monitoring--logging)
- [Workflow Orchestration](#workflow-orchestration)
- [Usage](#usage)
- [Screenshots](#screenshots)

## 🎯 Overview

This project implements a production-ready social media monitoring system that:

1. **Collects Data**: Integrates with Reddit API to pull posts based on keywords
2. **Processes Data**: Uses state-of-the-art ML models (sentiment analysis, NER, topic modeling)
3. **Stores Data**: Persists raw and processed data in PostgreSQL
4. **Generates Alerts**: Sends email and Slack notifications based on conditions
5. **Orchestrates**: Manages the entire workflow with n8n and comprehensive monitoring

## 🏗️ Architecture

```
┌─────────────────┐
│  Reddit API     │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Data Collector  │
│   (Python)      │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  ML Processor   │
│ - Sentiment     │
│ - NER           │
│ - Topics        │
└────────┬────────┘
         │
         v
┌─────────────────┐
│   PostgreSQL    │
│   Database      │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Alert System    │
│ - Email         │
│ - Slack         │
└─────────────────┘
         │
         v
┌─────────────────┐
│  N8N Workflow   │
│  Orchestrator   │
└─────────────────┘
```

## ✨ Features

### Data Collection
- Reddit API integration with PRAW
- Keyword-based post collection
- Subreddit monitoring
- Configurable collection intervals
- Robust error handling and retry logic

### ML Processing
- **Sentiment Analysis**: DistilBERT-based sentiment classification
- **Named Entity Recognition**: spaCy-based entity extraction (people, organizations, locations)
- **Topic Modeling**: LDA-based topic discovery
- Confidence scoring for all predictions
- Batch processing for efficiency

### Database Storage
- PostgreSQL with optimized schema
- Separate tables for raw and processed data
- Alert tracking and acknowledgment
- Pipeline metrics storage
- Indexed queries for performance
- Materialized views for analytics

### Alert System
- Multi-channel notifications (Email, Slack)
- Configurable alert conditions:
  - High negative sentiment with engagement
  - Critical keyword detection
  - Viral negative content
  - High entity mentions
- Alert severity levels (low, medium, high, critical)
- HTML-formatted email alerts
- Rich Slack attachments

### Monitoring & Logging
- Comprehensive logging at all stages
- Pipeline execution metrics
- Health checks
- Error tracking and reporting
- Grafana dashboards
- Real-time monitoring

## 🚀 Setup Instructions

### Prerequisites

- Docker & Docker Compose
- Reddit API credentials
- Email account (Gmail recommended)
- Slack webhook URL (optional)

### 1. Clone the Repository

```bash
git clone https://github.com/AdegokeMichael/social-monitoring.git
cd social-monitoring
```

### 2. Configure Environment Variables

Create a `.env` file:

```env
# Reddit API
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here

# Database
DB_PASSWORD=secure_password_here

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your_app_password_here
FROM_EMAIL=your-email@gmail.com

# Slack (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# N8N
N8N_USER=admin
N8N_PASSWORD=secure_password_here

# Grafana
GRAFANA_USER=admin
GRAFANA_PASSWORD=secure_password_here
```

### 3. Update Configuration

Edit `config.json` to customize:
- Keywords to monitor
- Subreddits to track
- Alert thresholds
- Email recipients
- Collection intervals

### 4. Start the Services

```bash
# Build and start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f app
```

### 5. Access Interfaces

- **N8N Workflow**: http://localhost:5678
- **Grafana Dashboard**: http://localhost:3000
- **Database**: localhost:5432

## 🔌 API Integration

### Reddit API Setup

1. Go to https://www.reddit.com/prefs/apps
2. Click "create app" or "create another app"
3. Select "script" as the app type
4. Fill in the details:
   - Name: Social Media Monitor
   - Description: Monitoring social media for analytics
   - Redirect URI: http://localhost:8080
5. Copy the Client ID and Secret

### Data Collection Strategy

The collector uses the following strategy:

1. **Keyword Matching**: Searches posts containing specific keywords
2. **Time-based**: Collects posts from the last 24 hours by default
3. **Rate Limiting**: Respects Reddit API limits (60 requests/minute)
4. **Deduplication**: Uses post IDs to avoid duplicates
5. **Error Recovery**: Automatic retry with exponential backoff

### Collection Flow

```python
# Example collection process
collector = SocialMediaCollector(client_id, client_secret, user_agent)

posts = collector.collect_posts(
    keywords=['AI', 'machine learning'],
    subreddits=['artificial', 'MachineLearning'],
    limit=50,
    time_filter='day'
)
```

## 🤖 ML Model Integration

### Models Used

#### 1. Sentiment Analysis
- **Model**: DistilBERT (distilbert-base-uncased-finetuned-sst-2-english)
- **Task**: Binary sentiment classification
- **Output**: POSITIVE/NEGATIVE/NEUTRAL + confidence score
- **Performance**: 92% accuracy on SST-2 benchmark

#### 2. Named Entity Recognition
- **Model**: spaCy en_core_web_sm
- **Entities**: PERSON, ORG, GPE, PRODUCT, EVENT, etc.
- **Output**: List of entities with type and position
- **Performance**: 85% F1 score on OntoNotes

#### 3. Topic Modeling
- **Model**: Latent Dirichlet Allocation (LDA)
- **Task**: Unsupervised topic discovery
- **Output**: Top 5 topics per document
- **Method**: TF-IDF vectorization + LDA

### Model Integration

```python
# ML Processing Pipeline
processor = MLProcessor(model_name='distilbert-base...')

# Process posts
processed_posts = processor.process_posts(raw_posts)

# Each processed post contains:
# - sentiment_label: POSITIVE/NEGATIVE/NEUTRAL
# - sentiment_score: 0.0 to 1.0
# - entities: [{text, label, start, end}, ...]
# - topics: [word1, word2, ...]
```

### Insights Provided

1. **Sentiment Trends**: Track positive/negative sentiment over time
2. **Entity Extraction**: Identify mentioned brands, people, organizations
3. **Topic Discovery**: Understand what's being discussed
4. **Anomaly Detection**: Flag unusual sentiment patterns
5. **Engagement Correlation**: Link sentiment to engagement metrics

## 🗄️ Database Design

### Schema Overview

```sql
-- Raw posts table
social_monitoring.raw_posts
- id (SERIAL PRIMARY KEY)
- post_id (VARCHAR UNIQUE)
- platform (VARCHAR)
- title (TEXT)
- content (TEXT)
- author (VARCHAR)
- created_utc (BIGINT)
- url (TEXT)
- score (INTEGER)
- num_comments (INTEGER)
- subreddit (VARCHAR)
- keywords_matched (JSONB)
- collected_at (TIMESTAMP)
- inserted_at (TIMESTAMP)

-- Processed posts table
social_monitoring.processed_posts
- id (SERIAL PRIMARY KEY)
- post_id (VARCHAR FK)
- sentiment_label (VARCHAR)
- sentiment_score (FLOAT)
- topics (JSONB)
- entities (JSONB)
- processed_at (TIMESTAMP)
- alert_triggered (BOOLEAN)
- alert_reasons (JSONB)
- model_version (VARCHAR)
- inserted_at (TIMESTAMP)

-- Alerts table
social_monitoring.alerts
- id (SERIAL PRIMARY KEY)
- post_id (VARCHAR)
- alert_type (VARCHAR)
- severity (VARCHAR)
- message (TEXT)
- reasons (JSONB)
- triggered_at (TIMESTAMP)
- acknowledged (BOOLEAN)
- acknowledged_at (TIMESTAMP)
- acknowledged_by (VARCHAR)
- inserted_at (TIMESTAMP)

-- Pipeline metrics table
social_monitoring.pipeline_metrics
- id (SERIAL PRIMARY KEY)
- metric_name (VARCHAR)
- metric_value (FLOAT)
- metric_metadata (JSONB)
- recorded_at (TIMESTAMP)
```

### Sample Data

```sql
-- Example raw post
INSERT INTO social_monitoring.raw_posts VALUES (
    1, 'abc123', 'reddit', 'New AI breakthrough',
    'Details about the breakthrough...', 'user123',
    1699123456, 'https://reddit.com/...', 500, 120,
    'artificial', '["AI", "breakthrough"]',
    '2024-10-23 10:00:00', '2024-10-23 10:05:00'
);

-- Example processed post
INSERT INTO social_monitoring.processed_posts VALUES (
    1, 'abc123', 'POSITIVE', 0.92,
    '["breakthrough", "innovation", "technology"]',
    '[{"text": "OpenAI", "label": "ORG"}]',
    '2024-10-23 10:06:00', false, '[]',
    'v1.0', '2024-10-23 10:07:00'
);
```

### Indexing Strategy

- B-tree indexes on foreign keys and timestamps
- GIN indexes on JSONB columns for fast JSON queries
- Composite indexes for common query patterns

## 📊 Monitoring & Logging

### Logging Architecture

Each component has dedicated logging:

```python
# Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('component.log'),
        logging.StreamHandler()
    ]
)
```

### Log Files

- `pipeline.log`: Main orchestration events
- `social_collector.log`: Data collection activities
- `ml_processor.log`: ML processing events
- `database.log`: Database operations
- `alerts.log`: Alert generation and sending

### Metrics Tracked

1. **Collection Metrics**:
   - Posts collected per run
   - Collection duration
   - API errors

2. **Processing Metrics**:
   - Posts processed per run
   - Processing duration
   - Model inference time
   - Sentiment distribution

3. **Storage Metrics**:
   - Database insert duration
   - Storage errors
   - Database size

4. **Alert Metrics**:
   - Alerts generated
   - Alerts sent successfully
   - Notification failures

### Health Checks

```sql
-- Check pipeline health (last 24 hours)
SELECT 
    DATE_TRUNC('hour', recorded_at) as hour,
    metric_name,
    AVG(metric_value) as avg_value,
    COUNT(*) as count
FROM social_monitoring.pipeline_metrics
WHERE recorded_at > NOW() - INTERVAL '24 hours'
GROUP BY hour, metric_name
ORDER BY hour DESC;
```

### Error Handling

1. **Retry Logic**: Automatic retry with exponential backoff
2. **Error Logging**: All errors logged with stack traces
3. **Graceful Degradation**: Pipeline continues on non-critical errors
4. **Error Notifications**: Critical errors sent via Slack

## 🔄 Workflow Orchestration

### N8N Workflow

The n8n workflow (`n8n_workflow.json`) orchestrates:

1. **Schedule Trigger**: Runs every hour
2. **Data Collection**: Executes collector script
3. **Validation**: Checks collection success
4. **ML Processing**: Runs ML models
5. **Validation**: Checks processing success
6. **Storage**: Inserts data into PostgreSQL
7. **Alert Query**: Fetches triggered alerts
8. **Alert Dispatch**: Sends Slack and email notifications
9. **Metrics Recording**: Logs execution metrics
10. **Health Check**: Monitors pipeline health

### Import Workflow

1. Access N8N at http://localhost:5678
2. Login with credentials from `.env`
3. Click "Import from File"
4. Select `n8n_workflow.json`
5. Configure credentials for:
   - PostgreSQL
   - SMTP
   - Slack webhook
6. Activate the workflow

## 📖 Usage

### Run Complete Pipeline

```bash
# Using Docker
docker-compose up app

# Or directly with Python
python main_orchestrator.py
```

### Run Individual Components

```bash
# Data collection only
python social_collector.py

# ML processing only
python ml_processor.py

# Database operations
python db_handler.py

# Test alerts
python alert_system.py
```

### Query Analytics

```sql
-- Sentiment trends
SELECT * FROM social_monitoring.sentiment_summary
WHERE date > CURRENT_DATE - INTERVAL '7 days'
ORDER BY date DESC;

-- Top entities
SELECT * FROM social_monitoring.top_entities
LIMIT 20;

-- Recent alerts
SELECT * FROM social_monitoring.alerts
WHERE acknowledged = false
ORDER BY triggered_at DESC;
```

## 📸 Screenshots

### 1. Pipeline Execution Log
```
================================================================================
STARTING SOCIAL MEDIA MONITORING PIPELINE
================================================================================
STAGE 1: Data Collection
--------------------------------------------------------------------------------
Collecting posts for keywords: ['AI', 'machine learning']
From subreddits: ['artificial', 'MachineLearning']
✓ Collected 150 posts

STAGE 2: ML Processing
--------------------------------------------------------------------------------
Running sentiment analysis, NER, and topic modeling...
✓ Processed 150 posts
  Sentiment distribution: {'POSITIVE': 80, 'NEGATIVE': 45, 'NEUTRAL': 25}
  Alerts triggered: 5

STAGE 3: Data Storage
--------------------------------------------------------------------------------
✓ Stored 150 raw posts
✓ Stored 150 processed posts

STAGE 4: Alert Generation
--------------------------------------------------------------------------------
✓ Generated and sent 5 alerts

STAGE 5: Recording Metrics
--------------------------------------------------------------------------------
✓ Metrics recorded to database

================================================================================
PIPELINE COMPLETED SUCCESSFULLY
================================================================================
```

### 2. Alert Email Example
```html
🚨 Social Media Monitoring Alert

Alert Summary:
Total Alerts: 3
Generated: 2024-10-23 14:30:00 UTC

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 HIGH SEVERITY

"Major AI Model Failure Reported..."

Severity: HIGH | Post ID: abc123 | Triggered: 2024-10-23 14:28:00

Score: 1250 | Comments: 340

Reasons:
• High negative sentiment (0.94) with high engagement
• Critical keywords detected: failure, outage
• Viral negative content (score: 1250)
```

### 3. Slack Alert
```
🚨 3 New Alert(s) Detected

📋 Major AI Model Failure Reported...
Sentiment: NEGATIVE (0.94)
Score: 1250 | Comments: 340
URL: https://reddit.com/r/technology/...
Reasons: High negative sentiment, Critical keywords

📋 Data Breach at Tech Company
Sentiment: NEGATIVE (0.89)
Score: 890 | Comments: 210
URL: https://reddit.com/r/cybersecurity/...
Reasons: Critical keywords detected: breach, hack
```

## 🧪 Testing

```bash
# Run tests
pytest tests/ -v --cov

# Test specific component
pytest tests/test_collector.py -v

# Test ML models
pytest tests/test_ml_processor.py -v
```

## 📝 License

MIT License - See LICENSE file for details

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request



## 🙏 Acknowledgments

- Reddit for API access
- Hugging Face for transformer models
- spaCy for NER capabilities
- n8n for workflow orchestration
