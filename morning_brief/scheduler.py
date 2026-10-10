import asyncio
import logging
import signal
import sys
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from morning_brief.config import settings
from morning_brief.main import run_briefing_pipeline

logger = logging.getLogger("morning_brief.scheduler")


def scheduled_job():
    """Wrapper to run async pipeline from APScheduler blocking job."""
    logger.info("Triggering scheduled morning briefing job...")
    asyncio.run(run_briefing_pipeline())


def start_scheduler():
    """Start APScheduler listening for 07:30 IST daily trigger."""
    time_parts = settings.briefing_time.split(":")
    hour = int(time_parts[0])
    minute = int(time_parts[1]) if len(time_parts) > 1 else 0

    scheduler = BlockingScheduler(timezone=settings.timezone)
    trigger = CronTrigger(hour=hour, minute=minute, timezone=settings.timezone)

    scheduler.add_job(
        scheduled_job,
        trigger=trigger,
        id="morning_brief_job",
        name="Morning Briefing Daily Execution",
        replace_existing=True,
    )

    logger.info(
        f"Scheduler started. Daily briefing scheduled for {settings.briefing_time} ({settings.timezone})."
    )

    def shutdown_handler(signum, frame):
        logger.info("Received shutdown signal. Stopping scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
