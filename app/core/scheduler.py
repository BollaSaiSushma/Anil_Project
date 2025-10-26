from apscheduler.schedulers.background import BackgroundScheduler
from app.utils.logger import logger
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz
from app.dev_pipeline import run_pipeline
from app.utils.logger import logger
from app.utils.config_loader import SETTINGS

class PipelineScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.timezone = pytz.timezone('America/New_York')
        
    def start(self):
        """Start the scheduler with configured jobs"""
        # Daily full scan at 1 AM ET
        self.scheduler.add_job(
            run_pipeline,
            trigger=CronTrigger(hour=1, minute=0, timezone=self.timezone),
            id='daily_scan',
            name='Daily Property Scan',
            replace_existing=True
        )
        
        # Mid-day price check at 2 PM ET
        self.scheduler.add_job(
            self._run_price_update,
            trigger=CronTrigger(hour=14, minute=0, timezone=self.timezone),
            id='price_check',
            name='Price Update Check',
            replace_existing=True
        )
        
        # Start the scheduler
        try:
            self.scheduler.start()
            logger.info("Scheduler started successfully")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
    
    def _run_price_update(self):
        """Run a targeted update to check for price changes"""
        try:
            run_pipeline(mode="price_update")
            logger.info("Price update completed successfully")
        except Exception as e:
            logger.error(f"Price update failed: {e}")
    
    def get_next_run_time(self, job_id='daily_scan'):
        """Get the next scheduled run time for a job"""
        job = self.scheduler.get_job(job_id)
        if job:
            return job.next_run_time
        return None
    
    def get_status(self):
        """Get the current status of all scheduled jobs"""
        status = {
            'running': self.scheduler.running,
            'jobs': []
        }
        
        for job in self.scheduler.get_jobs():
            status['jobs'].append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'active': True
            })
            
        return status

# Initialize global scheduler instance
scheduler = PipelineScheduler()

def start_scheduler(every_hours: int = 6):
    sched = BackgroundScheduler()
    sched.add_job(
        lambda: _safe_run(),
        'interval',
        hours=every_hours,
        id='dev_pipeline_job',
        replace_existing=True
    )
    sched.start()
    logger.info("Scheduler started: every %s hours", every_hours)

def _safe_run():
    try:
        run_pipeline()
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
