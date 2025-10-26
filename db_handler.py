"""
Database Handler
Manages PostgreSQL database operations for social media monitoring
"""

import psycopg2
from psycopg2.extras import execute_batch, Json
from psycopg2.pool import SimpleConnectionPool
import logging
from typing import List, Dict, Optional
from datetime import datetime
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('database.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DatabaseHandler:
    """Handle PostgreSQL database operations"""
    
    # Database schema
    SCHEMA_SQL = """
    -- Create schema if not exists
    CREATE SCHEMA IF NOT EXISTS social_monitoring;
    
    -- Raw posts table
    CREATE TABLE IF NOT EXISTS social_monitoring.raw_posts (
        id SERIAL PRIMARY KEY,
        post_id VARCHAR(255) UNIQUE NOT NULL,
        platform VARCHAR(50) NOT NULL,
        title TEXT,
        content TEXT,
        author VARCHAR(255),
        created_utc BIGINT,
        url TEXT,
        score INTEGER,
        num_comments INTEGER,
        subreddit VARCHAR(255),
        keywords_matched JSONB,
        collected_at TIMESTAMP,
        inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_post_id (post_id),
        INDEX idx_platform (platform),
        INDEX idx_created_utc (created_utc),
        INDEX idx_keywords (keywords_matched)
    );
    
    -- Processed posts table
    CREATE TABLE IF NOT EXISTS social_monitoring.processed_posts (
        id SERIAL PRIMARY KEY,
        post_id VARCHAR(255) NOT NULL REFERENCES social_monitoring.raw_posts(post_id),
        sentiment_label VARCHAR(20),
        sentiment_score FLOAT,
        topics JSONB,
        entities JSONB,
        processed_at TIMESTAMP,
        alert_triggered BOOLEAN DEFAULT FALSE,
        alert_reasons JSONB,
        model_version VARCHAR(50),
        inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_post_id_processed (post_id),
        INDEX idx_sentiment (sentiment_label),
        INDEX idx_alert (alert_triggered),
        INDEX idx_processed_at (processed_at)
    );
    
    -- Alerts table
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
        inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_post_id_alert (post_id),
        INDEX idx_triggered_at (triggered_at),
        INDEX idx_acknowledged (acknowledged)
    );
    
    -- Monitoring metrics table
    CREATE TABLE IF NOT EXISTS social_monitoring.pipeline_metrics (
        id SERIAL PRIMARY KEY,
        metric_name VARCHAR(100),
        metric_value FLOAT,
        metric_metadata JSONB,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_metric_name (metric_name),
        INDEX idx_recorded_at (recorded_at)
    );
    
    -- Create views for analytics
    CREATE OR REPLACE VIEW social_monitoring.sentiment_summary AS
    SELECT 
        DATE(processed_at) as date,
        sentiment_label,
        COUNT(*) as count,
        AVG(sentiment_score) as avg_score,
        COUNT(CASE WHEN alert_triggered THEN 1 END) as alerts_count
    FROM social_monitoring.processed_posts
    GROUP BY DATE(processed_at), sentiment_label;
    
    CREATE OR REPLACE VIEW social_monitoring.top_entities AS
    SELECT 
        entity->>'text' as entity_text,
        entity->>'label' as entity_type,
        COUNT(*) as mention_count
    FROM social_monitoring.processed_posts,
         jsonb_array_elements(entities) as entity
    GROUP BY entity->>'text', entity->>'label'
    ORDER BY mention_count DESC
    LIMIT 100;
    """
    
    def __init__(self, host: str, database: str, user: str, password: str, port: int = 5432):
        """
        Initialize database connection pool
        
        Args:
            host: Database host
            database: Database name
            user: Database user
            password: Database password
            port: Database port
        """
        try:
            self.pool = SimpleConnectionPool(
                1, 20,
                host=host,
                database=database,
                user=user,
                password=password,
                port=port
            )
            logger.info("Database connection pool initialized")
            self.init_schema()
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise
    
    def get_connection(self):
        """Get connection from pool"""
        return self.pool.getconn()
    
    def return_connection(self, conn):
        """Return connection to pool"""
        self.pool.putconn(conn)
    
    def init_schema(self):
        """Initialize database schema"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(self.SCHEMA_SQL)
            conn.commit()
            logger.info("Database schema initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing schema: {str(e)}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def insert_raw_posts(self, posts: List[Dict]) -> int:
        """
        Insert raw posts into database
        
        Args:
            posts: List of post dictionaries
            
        Returns:
            Number of inserted posts
        """
        conn = None
        inserted_count = 0
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            insert_query = """
            INSERT INTO social_monitoring.raw_posts 
            (post_id, platform, title, content, author, created_utc, url, 
             score, num_comments, subreddit, keywords_matched, collected_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (post_id) DO NOTHING
            """
            
            values = [
                (
                    post['post_id'],
                    post['platform'],
                    post['title'],
                    post['content'],
                    post['author'],
                    post['created_utc'],
                    post['url'],
                    post['score'],
                    post['num_comments'],
                    post['subreddit'],
                    Json(post['keywords_matched']),
                    post['collected_at']
                )
                for post in posts
            ]
            
            execute_batch(cursor, insert_query, values)
            inserted_count = cursor.rowcount
            conn.commit()
            logger.info(f"Inserted {inserted_count} raw posts")
            
        except Exception as e:
            logger.error(f"Error inserting raw posts: {str(e)}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.return_connection(conn)
        
        return inserted_count
    
    def insert_processed_posts(self, posts: List[Dict], model_version: str = "v1.0") -> int:
        """
        Insert processed posts into database
        
        Args:
            posts: List of processed post dictionaries
            model_version: ML model version identifier
            
        Returns:
            Number of inserted posts
        """
        conn = None
        inserted_count = 0
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            insert_query = """
            INSERT INTO social_monitoring.processed_posts 
            (post_id, sentiment_label, sentiment_score, topics, entities, 
             processed_at, alert_triggered, alert_reasons, model_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = [
                (
                    post['post_id'],
                    post['sentiment_label'],
                    post['sentiment_score'],
                    Json(post['topics']),
                    Json(post['entities']),
                    post['processed_at'],
                    post['alert_triggered'],
                    Json(post['alert_reasons']),
                    model_version
                )
                for post in posts
            ]
            
            execute_batch(cursor, insert_query, values)
            inserted_count = cursor.rowcount
            conn.commit()
            logger.info(f"Inserted {inserted_count} processed posts")
            
        except Exception as e:
            logger.error(f"Error inserting processed posts: {str(e)}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.return_connection(conn)
        
        return inserted_count
    
    def insert_alert(self, post_id: str, alert_type: str, severity: str, 
                     message: str, reasons: List[str]) -> int:
        """
        Insert alert into database
        
        Args:
            post_id: Post identifier
            alert_type: Type of alert
            severity: Alert severity (low, medium, high, critical)
            message: Alert message
            reasons: List of reasons for alert
            
        Returns:
            Alert ID
        """
        conn = None
        alert_id = None
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            insert_query = """
            INSERT INTO social_monitoring.alerts 
            (post_id, alert_type, severity, message, reasons, triggered_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """
            
            cursor.execute(insert_query, (
                post_id, alert_type, severity, message, 
                Json(reasons), datetime.utcnow()
            ))
            
            alert_id = cursor.fetchone()[0]
            conn.commit()
            logger.info(f"Inserted alert {alert_id} for post {post_id}")
            
        except Exception as e:
            logger.error(f"Error inserting alert: {str(e)}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.return_connection(conn)
        
        return alert_id
    
    def record_metric(self, metric_name: str, metric_value: float, 
                      metadata: Optional[Dict] = None):
        """
        Record pipeline metric
        
        Args:
            metric_name: Name of metric
            metric_value: Metric value
            metadata: Additional metadata
        """
        conn = None
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            insert_query = """
            INSERT INTO social_monitoring.pipeline_metrics 
            (metric_name, metric_value, metric_metadata)
            VALUES (%s, %s, %s)
            """
            
            cursor.execute(insert_query, (
                metric_name, metric_value, Json(metadata or {})
            ))
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Error recording metric: {str(e)}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                self.return_connection(conn)
    
    def get_unacknowledged_alerts(self) -> List[Dict]:
        """Get all unacknowledged alerts"""
        conn = None
        alerts = []
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT a.*, r.title, r.url, r.score, r.num_comments
            FROM social_monitoring.alerts a
            JOIN social_monitoring.raw_posts r ON a.post_id = r.post_id
            WHERE a.acknowledged = FALSE
            ORDER BY a.triggered_at DESC
            """
            
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            alerts = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Error fetching alerts: {str(e)}")
        finally:
            if conn:
                self.return_connection(conn)
        
        return alerts
    
    def close(self):
        """Close all connections"""
        if self.pool:
            self.pool.closeall()
            logger.info("Database connections closed")


# Example usage
if __name__ == "__main__":
    import os
    
    # Database configuration
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'social_monitoring'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'password'),
        'port': int(os.getenv('DB_PORT', 5432))
    }
    
    # Initialize database
    db = DatabaseHandler(**DB_CONFIG)
    
    # Load and insert data
    with open('collected_posts.json', 'r') as f:
        raw_posts = json.load(f)
    
    with open('processed_posts.json', 'r') as f:
        processed_posts = json.load(f)
    
    # Insert data
    db.insert_raw_posts(raw_posts)
    db.insert_processed_posts(processed_posts)
    
    # Insert alerts
    for post in processed_posts:
        if post['alert_triggered']:
            db.insert_alert(
                post_id=post['post_id'],
                alert_type='sentiment_alert',
                severity='high',
                message=f"Alert for post: {post['title'][:100]}",
                reasons=post['alert_reasons']
            )
    
    # Close connections
    db.close()
