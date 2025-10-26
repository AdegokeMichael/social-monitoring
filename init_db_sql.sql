-- Database Initialization Script for Social Media Monitoring
-- This script creates the complete database schema with indexes and views

-- Create schema
CREATE SCHEMA IF NOT EXISTS social_monitoring;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For fuzzy text search

-- ============================================================================
-- RAW POSTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS social_monitoring.raw_posts (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(255) UNIQUE NOT NULL,
    platform VARCHAR(50) NOT NULL,
    title TEXT,
    content TEXT,
    author VARCHAR(255),
    created_utc BIGINT,
    url TEXT,
    score INTEGER DEFAULT 0,
    num_comments INTEGER DEFAULT 0,
    subreddit VARCHAR(255),
    keywords_matched JSONB,
    collected_at TIMESTAMP,
    inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for raw_posts
CREATE INDEX IF NOT EXISTS idx_raw_posts_post_id ON social_monitoring.raw_posts(post_id);
CREATE INDEX IF NOT EXISTS idx_raw_posts_platform ON social_monitoring.raw_posts(platform);
CREATE INDEX IF NOT EXISTS idx_raw_posts_created_utc ON social_monitoring.raw_posts(created_utc);
CREATE INDEX IF NOT EXISTS idx_raw_posts_subreddit ON social_monitoring.raw_posts(subreddit);
CREATE INDEX IF NOT EXISTS idx_raw_posts_collected_at ON social_monitoring.raw_posts(collected_at);
CREATE INDEX IF NOT EXISTS idx_raw_posts_keywords ON social_monitoring.raw_posts USING GIN(keywords_matched);
CREATE INDEX IF NOT EXISTS idx_raw_posts_title_trgm ON social_monitoring.raw_posts USING GIN(title gin_trgm_ops);

-- ============================================================================
-- PROCESSED POSTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS social_monitoring.processed_posts (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(255) NOT NULL,
    sentiment_label VARCHAR(20),
    sentiment_score FLOAT,
    topics JSONB,
    entities JSONB,
    processed_at TIMESTAMP,
    alert_triggered BOOLEAN DEFAULT FALSE,
    alert_reasons JSONB,
    model_version VARCHAR(50),
    inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES social_monitoring.raw_posts(post_id) ON DELETE CASCADE
);

-- Create indexes for processed_posts
CREATE INDEX IF NOT EXISTS idx_processed_posts_post_id ON social_monitoring.processed_posts(post_id);
CREATE INDEX IF NOT EXISTS idx_processed_posts_sentiment ON social_monitoring.processed_posts(sentiment_label);
CREATE INDEX IF NOT EXISTS idx_processed_posts_alert ON social_monitoring.processed_posts(alert_triggered);
CREATE INDEX IF NOT EXISTS idx_processed_posts_processed_at ON social_monitoring.processed_posts(processed_at);
CREATE INDEX IF NOT EXISTS idx_processed_posts_entities ON social_monitoring.processed_posts USING GIN(entities);
CREATE INDEX IF NOT EXISTS idx_processed_posts_topics ON social_monitoring.processed_posts USING GIN(topics);

-- ============================================================================
-- ALERTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS social_monitoring.alerts (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(255) NOT NULL,
    alert_type VARCHAR(100),
    severity VARCHAR(20),
    message TEXT,
    reasons JSONB,
    triggered_at TIMESTAMP,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP,
    acknowledged_by VARCHAR(255),
    inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for alerts
CREATE INDEX IF NOT EXISTS idx_alerts_post_id ON social_monitoring.alerts(post_id);
CREATE INDEX IF NOT EXISTS idx_alerts_triggered_at ON social_monitoring.alerts(triggered_at);
CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON social_monitoring.alerts(acknowledged);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON social_monitoring.alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON social_monitoring.alerts(alert_type);

-- ============================================================================
-- PIPELINE METRICS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS social_monitoring.pipeline_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100),
    metric_value FLOAT,
    metric_metadata JSONB,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for pipeline_metrics
CREATE INDEX IF NOT EXISTS idx_metrics_name ON social_monitoring.pipeline_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_metrics_recorded_at ON social_monitoring.pipeline_metrics(recorded_at);
CREATE INDEX IF NOT EXISTS idx_metrics_name_time ON social_monitoring.pipeline_metrics(metric_name, recorded_at);

-- ============================================================================
-- VIEWS FOR ANALYTICS
-- ============================================================================

-- Sentiment summary view
CREATE OR REPLACE VIEW social_monitoring.sentiment_summary AS
SELECT 
    DATE(p.processed_at) as date,
    p.sentiment_label,
    COUNT(*) as count,
    AVG(p.sentiment_score) as avg_score,
    MIN(p.sentiment_score) as min_score,
    MAX(p.sentiment_score) as max_score,
    COUNT(CASE WHEN p.alert_triggered THEN 1 END) as alerts_count,
    AVG(r.score) as avg_engagement_score,
    AVG(r.num_comments) as avg_comments
FROM social_monitoring.processed_posts p
JOIN social_monitoring.raw_posts r ON p.post_id = r.post_id
GROUP BY DATE(p.processed_at), p.sentiment_label
ORDER BY date DESC, p.sentiment_label;

-- Top entities view
CREATE OR REPLACE VIEW social_monitoring.top_entities AS
SELECT 
    entity->>'text' as entity_text,
    entity->>'label' as entity_type,
    COUNT(*) as mention_count,
    COUNT(DISTINCT p.post_id) as post_count,
    AVG((SELECT sentiment_score FROM social_monitoring.processed_posts WHERE post_id = p.post_id)) as avg_sentiment
FROM social_monitoring.processed_posts p,
     jsonb_array_elements(entities) as entity
GROUP BY entity->>'text', entity->>'label'
HAVING COUNT(*) > 1
ORDER BY mention_count DESC
LIMIT 100;

-- Alert summary view
CREATE OR REPLACE VIEW social_monitoring.alert_summary AS
SELECT 
    DATE(a.triggered_at) as date,
    a.severity,
    a.alert_type,
    COUNT(*) as alert_count,
    COUNT(CASE WHEN a.acknowledged THEN 1 END) as acknowledged_count,
    AVG(r.score) as avg_post_score
FROM social_monitoring.alerts a
JOIN social_monitoring.raw_posts r ON a.post_id = r.post_id
GROUP BY DATE(a.triggered_at), a.severity, a.alert_type
ORDER BY date DESC, alert_count DESC;

-- Pipeline health view
CREATE OR REPLACE VIEW social_monitoring.pipeline_health AS
SELECT 
    DATE_TRUNC('hour', recorded_at) as hour,
    metric_name,
    COUNT(*) as execution_count,
    AVG(metric_value) as avg_value,
    MIN(metric_value) as min_value,
    MAX(metric_value) as max_value,
    STDDEV(metric_value) as stddev_value
FROM social_monitoring.pipeline_metrics
WHERE recorded_at > NOW() - INTERVAL '7 days'
GROUP BY DATE_TRUNC('hour', recorded_at), metric_name
ORDER BY hour DESC, metric_name;

-- Engagement trends view
CREATE OR REPLACE VIEW social_monitoring.engagement_trends AS
SELECT 
    DATE(r.collected_at) as date,
    r.subreddit,
    COUNT(*) as post_count,
    AVG(r.score) as avg_score,
    MAX(r.score) as max_score,
    AVG(r.num_comments) as avg_comments,
    SUM(CASE WHEN p.sentiment_label = 'POSITIVE' THEN 1 ELSE 0 END) as positive_count,
    SUM(CASE WHEN p.sentiment_label = 'NEGATIVE' THEN 1 ELSE 0 END) as negative_count,
    SUM(CASE WHEN p.sentiment_label = 'NEUTRAL' THEN 1 ELSE 0 END) as neutral_count
FROM social_monitoring.raw_posts r
LEFT JOIN social_monitoring.processed_posts p ON r.post_id = p.post_id
GROUP BY DATE(r.collected_at), r.subreddit
ORDER BY date DESC, post_count DESC;

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to acknowledge alert
CREATE OR REPLACE FUNCTION social_monitoring.acknowledge_alert(
    alert_id_param INTEGER,
    acknowledged_by_param VARCHAR
)
RETURNS VOID AS $$
BEGIN
    UPDATE social_monitoring.alerts
    SET 
        acknowledged = TRUE,
        acknowledged_at = CURRENT_TIMESTAMP,
        acknowledged_by = acknowledged_by_param
    WHERE id = alert_id_param;
END;
$$ LANGUAGE plpgsql;

-- Function to get recent high-priority alerts
CREATE OR REPLACE FUNCTION social_monitoring.get_recent_high_priority_alerts(hours_back INTEGER DEFAULT 24)
RETURNS TABLE (
    alert_id INTEGER,
    post_title TEXT,
    severity VARCHAR,
    triggered_at TIMESTAMP,
    post_score INTEGER,
    alert_reasons JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.id,
        r.title,
        a.severity,
        a.triggered_at,
        r.score,
        a.reasons
    FROM social_monitoring.alerts a
    JOIN social_monitoring.raw_posts r ON a.post_id = r.post_id
    WHERE 
        a.triggered_at > NOW() - INTERVAL '1 hour' * hours_back
        AND a.severity IN ('high', 'critical')
        AND a.acknowledged = FALSE
    ORDER BY a.triggered_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate sentiment trend
CREATE OR REPLACE FUNCTION social_monitoring.calculate_sentiment_trend(days_back INTEGER DEFAULT 7)
RETURNS TABLE (
    date DATE,
    positive_pct FLOAT,
    negative_pct FLOAT,
    neutral_pct FLOAT,
    total_posts INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        DATE(p.processed_at) as date,
        (COUNT(CASE WHEN p.sentiment_label = 'POSITIVE' THEN 1 END)::FLOAT / COUNT(*)::FLOAT * 100) as positive_pct,
        (COUNT(CASE WHEN p.sentiment_label = 'NEGATIVE' THEN 1 END)::FLOAT / COUNT(*)::FLOAT * 100) as negative_pct,
        (COUNT(CASE WHEN p.sentiment_label = 'NEUTRAL' THEN 1 END)::FLOAT / COUNT(*)::FLOAT * 100) as neutral_pct,
        COUNT(*)::INTEGER as total_posts
    FROM social_monitoring.processed_posts p
    WHERE p.processed_at > NOW() - INTERVAL '1 day' * days_back
    GROUP BY DATE(p.processed_at)
    ORDER BY date DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SAMPLE DATA (for testing)
-- ============================================================================

-- Insert sample raw posts
INSERT INTO social_monitoring.raw_posts (post_id, platform, title, content, author, created_utc, url, score, num_comments, subreddit, keywords_matched, collected_at)
VALUES 
    ('sample1', 'reddit', 'Amazing new AI breakthrough in natural language processing', 'Researchers have developed a new model that achieves state-of-the-art results...', 'ai_researcher', 1699123456, 'https://reddit.com/r/artificial/sample1', 1250, 340, 'artificial', '["AI", "breakthrough"]', NOW() - INTERVAL '2 hours'),
    ('sample2', 'reddit', 'Major data breach reported at tech company', 'Security experts discovered a significant vulnerability...', 'security_pro', 1699123500, 'https://reddit.com/r/cybersecurity/sample2', 890, 210, 'technology', '["breach", "security"]', NOW() - INTERVAL '1 hour'),
    ('sample3', 'reddit', 'New machine learning library released', 'This library makes it easier to build ML models...', 'ml_dev', 1699123600, 'https://reddit.com/r/MachineLearning/sample3', 450, 85, 'MachineLearning', '["machine learning"]', NOW() - INTERVAL '30 minutes')
ON CONFLICT (post_id) DO NOTHING;

-- Insert sample processed posts
INSERT INTO social_monitoring.processed_posts (post_id, sentiment_label, sentiment_score, topics, entities, processed_at, alert_triggered, alert_reasons, model_version)
VALUES 
    ('sample1', 'POSITIVE', 0.92, '["breakthrough", "research", "language", "processing", "model"]', '[{"text": "AI", "label": "TECH", "start": 0, "end": 2}]', NOW() - INTERVAL '2 hours', FALSE, '[]', 'v1.0'),
    ('sample2', 'NEGATIVE', 0.94, '["breach", "security", "vulnerability", "data", "company"]', '[{"text": "tech company", "label": "ORG", "start": 40, "end": 52}]', NOW() - INTERVAL '1 hour', TRUE, '["High negative sentiment (0.94) with high engagement", "Critical keywords detected: breach"]', 'v1.0'),
    ('sample3', 'POSITIVE', 0.85, '["library", "machine", "learning", "models", "development"]', '[{"text": "ML", "label": "TECH", "start": 0, "end": 2}]', NOW() - INTERVAL '30 minutes', FALSE, '[]', 'v1.0')
ON CONFLICT DO NOTHING;

-- Insert sample alerts
INSERT INTO social_monitoring.alerts (post_id, alert_type, severity, message, reasons, triggered_at, acknowledged)
VALUES 
    ('sample2', 'content_alert', 'high', 'Alert triggered for: Major data breach reported at tech company', '["High negative sentiment (0.94) with high engagement", "Critical keywords detected: breach"]', NOW() - INTERVAL '1 hour', FALSE)
ON CONFLICT DO NOTHING;

-- Insert sample metrics
INSERT INTO social_monitoring.pipeline_metrics (metric_name, metric_value, metric_metadata, recorded_at)
VALUES 
    ('posts_collected', 150, '{"status": "success"}', NOW() - INTERVAL '1 hour'),
    ('posts_processed', 150, '{"status": "success"}', NOW() - INTERVAL '1 hour'),
    ('alerts_generated', 5, '{"status": "success"}', NOW() - INTERVAL '1 hour'),
    ('execution_time', 45.3, '{"status": "success"}', NOW() - INTERVAL '1 hour');

-- ============================================================================
-- GRANTS AND PERMISSIONS
-- ============================================================================

-- Grant permissions to application user (create this user first if needed)
-- CREATE USER app_user WITH PASSWORD 'secure_password';

-- GRANT USAGE ON SCHEMA social_monitoring TO app_user;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA social_monitoring TO app_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA social_monitoring TO app_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA social_monitoring TO app_user;

-- ============================================================================
-- MAINTENANCE
-- ============================================================================

-- Create a function to clean old data
CREATE OR REPLACE FUNCTION social_monitoring.cleanup_old_data(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Delete old raw posts (cascades to processed posts)
    DELETE FROM social_monitoring.raw_posts
    WHERE inserted_at < NOW() - INTERVAL '1 day' * days_to_keep;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- Delete old acknowledged alerts
    DELETE FROM social_monitoring.alerts
    WHERE acknowledged = TRUE 
    AND acknowledged_at < NOW() - INTERVAL '1 day' * days_to_keep;
    
    -- Delete old metrics
    DELETE FROM social_monitoring.pipeline_metrics
    WHERE recorded_at < NOW() - INTERVAL '1 day' * days_to_keep;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Database initialization completed!';
    RAISE NOTICE 'Schema: social_monitoring';
    RAISE NOTICE 'Tables: 4 (raw_posts, processed_posts, alerts, pipeline_metrics)';
    RAISE NOTICE 'Views: 5 (sentiment_summary, top_entities, alert_summary, pipeline_health, engagement_trends)';
    RAISE NOTICE 'Functions: 4 (acknowledge_alert, get_recent_high_priority_alerts, calculate_sentiment_trend, cleanup_old_data)';
    RAISE NOTICE 'Sample data: Inserted for testing';
    RAISE NOTICE '========================================';
END $$;
