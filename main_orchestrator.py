"""
Main Orchestration Pipeline
Coordinates the entire social media monitoring workflow
"""

import logging
import time
import traceback
from datetime import datetime
from typing import Dict, List
import json
import os
from dataclasses import asdict

# Import custom modules
from social_collector import SocialMediaCollector, SocialPost
from ml_processor import MLProcessor
from db_handler import DatabaseHandler
from alert_system import AlertNotifier, AlertManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PipelineMetrics:
    """Track pipeline execution metrics"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.posts_collected = 0
        self.posts_processed = 0
        self.posts_stored = 0
        self.alerts_generated = 0
        self.errors = []
        self.stage_durations = {}
    
    def start_stage(self, stage_name: str):
        """Start timing a stage"""
        self.stage_durations[stage_name] = {'start': time.time()}
    
    def end_stage(self, stage_name: str):
        """End timing a stage"""
        if stage_name in self.stage_durations:
            self.stage_durations[stage_name]['end'] = time.time()
            self.stage_durations[stage_name]['duration'] = (
                self.stage_durations[stage_name]['end'] - 
                self.stage_durations[stage_name]['start']
            )
    
    def add_error(self, stage: str, error: str):
        """Record an error"""
        self.errors.append({
            'stage': stage,
            'error': error,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def get_summary(self) -> Dict:
        """Get metrics summary"""
        total_duration = (self.end_time - self.start_time) if self.end_time and self.start_time else 0
        
        return {
            'execution_time': total_duration,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'posts_collected': self.posts_collected,
            'posts_processed': self.posts_processed,
            'posts_stored': self.posts_stored,
            'alerts_generated': self.alerts_generated,
            'error_count': len(self.errors),
            'errors': self.errors,
            'stage_durations': {
                k: v.get('duration', 0) for k, v in self.stage_durations.items()
            }
        }


class SocialMonitoringPipeline:
    """Main orchestration pipeline"""
    
    def __init__(self, config: Dict):
        """
        Initialize pipeline with configuration
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.metrics = PipelineMetrics()
        
        # Initialize components
        try:
            self.collector = SocialMediaCollector(
                client_id=config['reddit']['client_id'],
                client_secret=config['reddit']['client_secret'],
                user_agent=config['reddit']['user_agent']
            )
            
            self.ml_processor = MLProcessor(
                model_name=config['ml']['sentiment_model']
            )
            
            self.db_handler = DatabaseHandler(
                host=config['database']['host'],
                database=config['database']['database'],
                user=config['database']['user'],
                password=config['database']['password'],
                port=config['database']['port']
            )
            
            self.notifier = AlertNotifier(
                smtp_host=config['alerts'].get('smtp_host'),
                smtp_port=config['alerts'].get('smtp_port', 587),
                smtp_user=config['alerts'].get('smtp_user'),
                smtp_password=config['alerts'].get('smtp_password'),
                from_email=config['alerts'].get('from_email'),
                slack_webhook_url=config['alerts'].get('slack_webhook_url')
            )
            
            self.alert_manager = AlertManager(self.db_handler, self.notifier)
            
            logger.info("Pipeline components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize pipeline: {str(e)}")
            raise
    
    def run(self):
        """Execute the complete pipeline"""
        logger.info("=" * 80)
        logger.info("STARTING SOCIAL MEDIA MONITORING PIPELINE")
        logger.info("=" * 80)
        
        self.metrics.start_time = time.time()
        
        try:
            # Stage 1: Data Collection
            raw_posts = self._collect_data()
            
            if not raw_posts:
                logger.warning("No posts collected, exiting pipeline")
                return
            
            # Stage 2: ML Processing
            processed_posts = self._process_data(raw_posts)
            
            if not processed_posts:
                logger.warning("No posts processed, exiting pipeline")
                return
            
            # Stage 3: Data Storage
            self._store_data(raw_posts, processed_posts)
            
            # Stage 4: Alert Generation
            self._generate_alerts(processed_posts)
            
            # Stage 5: Record Metrics
            self._record_metrics()
            
            logger.info("=" * 80)
            logger.info("PIPELINE COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {str(e)}")
            logger.error(traceback.format_exc())
            self.metrics.add_error('pipeline', str(e))
            raise
        
        finally:
            self.metrics.end_time = time.time()
            self._print_summary()
    
    def _collect_data(self) -> List[SocialPost]:
        """Stage 1: Collect social media data"""
        logger.info("STAGE 1: Data Collection")
        logger.info("-" * 80)
        
        self.metrics.start_stage('collection')
        posts = []
        
        try:
            keywords = self.config['monitoring']['keywords']
            subreddits = self.config['monitoring']['subreddits']
            limit = self.config['monitoring'].get('posts_per_subreddit', 50)
            
            logger.info(f"Collecting posts for keywords: {keywords}")
            logger.info(f"From subreddits: {subreddits}")
            
            posts = self.collector.collect_posts(
                keywords=keywords,
                subreddits=subreddits,
                limit=limit,
                time_filter='day'
            )
            
            self.metrics.posts_collected = len(posts)
            logger.info(f"✓ Collected {len(posts)} posts")
            
        except Exception as e:
            logger.error(f"Data collection failed: {str(e)}")
            self.metrics.add_error('collection', str(e))
            raise
        
        finally:
            self.metrics.end_stage('collection')
        
        return posts
    
    def _process_data(self, raw_posts: List[SocialPost]) -> List[Dict]:
        """Stage 2: Process data with ML models"""
        logger.info("\nSTAGE 2: ML Processing")
        logger.info("-" * 80)
        
        self.metrics.start_stage('processing')
        processed_posts = []
        
        try:
            # Convert to dictionaries
            raw_posts_dict = [asdict(post) for post in raw_posts]
            
            logger.info("Running sentiment analysis, NER, and topic modeling...")
            processed_posts = self.ml_processor.process_posts(raw_posts_dict)
            
            self.metrics.posts_processed = len(processed_posts)
            
            # Log sentiment distribution
            sentiment_counts = {}
            for post in processed_posts:
                label = post.sentiment_label
                sentiment_counts[label] = sentiment_counts.get(label, 0) + 1
            
            logger.info(f"✓ Processed {len(processed_posts)} posts")
            logger.info(f"  Sentiment distribution: {sentiment_counts}")
            logger.info(f"  Alerts triggered: {sum(1 for p in processed_posts if p.alert_triggered)}")
            
        except Exception as e:
            logger.error(f"Data processing failed: {str(e)}")
            self.metrics.add_error('processing', str(e))
            raise
        
        finally:
            self.metrics.end_stage('processing')
        
        return [asdict(post) for post in processed_posts]
    
    def _store_data(self, raw_posts: List[SocialPost], processed_posts: List[Dict]):
        """Stage 3: Store data in database"""
        logger.info("\nSTAGE 3: Data Storage")
        logger.info("-" * 80)
        
        self.metrics.start_stage('storage')
        
        try:
            # Store raw posts
            raw_posts_dict = [asdict(post) for post in raw_posts]
            raw_count = self.db_handler.insert_raw_posts(raw_posts_dict)
            logger.info(f"✓ Stored {raw_count} raw posts")
            
            # Store processed posts
            processed_count = self.db_handler.insert_processed_posts(
                processed_posts,
                model_version=self.config['ml'].get('model_version', 'v1.0')
            )
            logger.info(f"✓ Stored {processed_count} processed posts")
            
            self.metrics.posts_stored = raw_count
            
        except Exception as e:
            logger.error(f"Data storage failed: {str(e)}")
            self.metrics.add_error('storage', str(e))
            raise
        
        finally:
            self.metrics.end_stage('storage')
    
    def _generate_alerts(self, processed_posts: List[Dict]):
        """Stage 4: Generate and send alerts"""
        logger.info("\nSTAGE 4: Alert Generation")
        logger.info("-" * 80)
        
        self.metrics.start_stage('alerts')
        
        try:
            email_recipients = self.config['alerts'].get('email_recipients', [])
            
            # Process alerts
            self.alert_manager.process_alerts(processed_posts, email_recipients)
            
            alert_count = sum(1 for p in processed_posts if p.get('alert_triggered', False))
            self.metrics.alerts_generated = alert_count
            
            logger.info(f"✓ Generated and sent {alert_count} alerts")
            
        except Exception as e:
            logger.error(f"Alert generation failed: {str(e)}")
            self.metrics.add_error('alerts', str(e))
            # Don't raise - alerts are not critical
        
        finally:
            self.metrics.end_stage('alerts')
    
    def _record_metrics(self):
        """Record pipeline metrics to database"""
        logger.info("\nSTAGE 5: Recording Metrics")
        logger.info("-" * 80)
        
        try:
            summary = self.metrics.get_summary()
            
            # Record key metrics
            self.db_handler.record_metric('posts_collected', summary['posts_collected'])
            self.db_handler.record_metric('posts_processed', summary['posts_processed'])
            self.db_handler.record_metric('alerts_generated', summary['alerts_generated'])
            self.db_handler.record_metric('execution_time', summary['execution_time'])
            self.db_handler.record_metric('error_count', summary['error_count'])
            
            logger.info("✓ Metrics recorded to database")
            
        except Exception as e:
            logger.error(f"Failed to record metrics: {str(e)}")
            # Don't raise - metrics are not critical
    
    def _print_summary(self):
        """Print execution summary"""
        summary = self.metrics.get_summary()
        
        logger.info("\n" + "=" * 80)
        logger.info("PIPELINE EXECUTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Execution Time: {summary['execution_time']:.2f} seconds")
        logger.info(f"Posts Collected: {summary['posts_collected']}")
        logger.info(f"Posts Processed: {summary['posts_processed']}")
        logger.info(f"Posts Stored: {summary['posts_stored']}")
        logger.info(f"Alerts Generated: {summary['alerts_generated']}")
        logger.info(f"Errors: {summary['error_count']}")
        
        logger.info("\nStage Durations:")
        for stage, duration in summary['stage_durations'].items():
            logger.info(f"  {stage}: {duration:.2f}s")
        
        if summary['errors']:
            logger.info("\nErrors:")
            for error in summary['errors']:
                logger.info(f"  [{error['stage']}] {error['error']}")
        
        logger.info("=" * 80 + "\n")
        
        # Save summary to file
        with open('pipeline_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)


def load_config(config_path: str = 'config.json') -> Dict:
    """Load configuration from file"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        logger.info(f"Configuration loaded from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load config: {str(e)}")
        raise


def main():
    """Main entry point"""
    try:
        # Load configuration
        config = load_config('config.json')
        
        # Initialize and run pipeline
        pipeline = SocialMonitoringPipeline(config)
        pipeline.run()
        
        return 0
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    exit(main())
