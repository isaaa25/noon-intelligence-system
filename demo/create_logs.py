from datetime import datetime, timedelta
from decimal import Decimal
import random

from pipeline.models import ScrapeLog


def seed_logs(session):

    start_date = datetime.now() - timedelta(days=30)

    for day in range(30):

        log = ScrapeLog(
            keyword="electronics",
            pages_scraped=random.randint(2, 6),
            products_found=40,
            products_new=0 if day > 0 else 40,
            products_updated=random.randint(8, 25),
            alerts_triggered=random.randint(1, 6),
            errors=0,
            error_details=None,
            duration_secs=Decimal(
                str(round(random.uniform(15, 45), 2))
            ),
            status="success",
            run_at=start_date + timedelta(days=day)
        )

        session.add(log)

    session.commit()

    print("Created 30 scrape logs")