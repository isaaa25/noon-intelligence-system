from datetime import datetime, timedelta
from decimal import Decimal
import random

from pipeline.models import (
    Product,
    PriceSnapshot,
)

from pipeline.loader import check_and_create_alerts
from config import settings

# -----------------------------------
# Base prices by model
# -----------------------------------

BASE_PRICES = {
    "iPhone 15 128GB": Decimal("3399"),
    "iPhone 15 256GB": Decimal("3799"),
    "iPhone 15 Pro 256GB": Decimal("4499"),
    "iPhone 15 Pro Max 256GB": Decimal("4999"),
    "Galaxy S25": Decimal("2999"),
    "Galaxy S25 Plus": Decimal("3499"),
    "Galaxy S25 Ultra": Decimal("4799"),
    "AirPods Pro 2": Decimal("949"),
    "Apple Watch Series 10": Decimal("1799"),
    "iPad Air M3": Decimal("2499"),
}


# -----------------------------------
# Price logic
# -----------------------------------

def generate_price(base_price, seller_slug, day):

    price = base_price

    # Sharaf runs aggressive promotions
    if seller_slug == "sharaf":

        if day >= 8:
            price *= Decimal("0.90")

        if day >= 21:
            price *= Decimal("0.95")

    # TechZone reacts 2 days later
    elif seller_slug == "techzone":

        if day >= 10:
            price *= Decimal("0.90")

        if day >= 23:
            price *= Decimal("0.95")

    # Virgin fluctuates slightly
    elif seller_slug == "virgin":

        fluctuation = Decimal(
            str(random.uniform(0.98, 1.02))
        )

        price *= fluctuation

    # iStyle stays premium
    elif seller_slug == "istyle":

        if day >= 27:
            price *= Decimal("0.97")

    return price.quantize(Decimal("0.01"))


# -----------------------------------
# Stock logic
# -----------------------------------

def generate_stock(seller_slug, day):

    stock_status = "in_stock"

    # Virgin stock outage
    if (
        seller_slug == "virgin"
        and 15 <= day <= 17
    ):
        stock_status = "out_of_stock"

    return stock_status


# -----------------------------------
# Snapshot Seeder
# -----------------------------------

def seed_snapshots(session):

    products = session.query(Product).all()

    start_date = datetime.now() - timedelta(days=30)

    total_snapshots = 0
    total_alerts = 0

    for product in products:

        seller_slug = product.seller.store_slug

        base_price = BASE_PRICES.get(
            product.model,
            Decimal("1000")
        )

        previous_snapshot = None

        for day in range(30):

            current_price = generate_price(
                base_price,
                seller_slug,
                day
            )

            stock_status = generate_stock(
                seller_slug,
                day
            )

            discount_pct = round(
                (
                    (base_price - current_price)
                    / base_price
                )
                * 100,
                2,
            )

            snapshot = PriceSnapshot(
                product_id=product.id,
                current_price=current_price,
                original_price=base_price,
                discount_pct=discount_pct,
                currency="AED",
                stock_status=stock_status,
                rating=round(
                    random.uniform(4.1, 4.9),
                    1
                ),
                review_count=random.randint(
                    50,
                    5000
                ),
                is_sponsored=random.random() < 0.15,
                search_position=random.randint(
                    1,
                    40
                ),
                source="search",
                scraped_at=start_date + timedelta(days=day),
            )

            session.add(snapshot)

            session.flush()

            clean_snapshot = {
                "current_price": current_price,
                "stock_status": stock_status,
            }

            alerts_created = (
                check_and_create_alerts(
                    session=session,
                    product_id=product.id,
                    clean_snapshot=clean_snapshot,
                    previous=previous_snapshot,
                )
            )

            total_alerts += alerts_created

            previous_snapshot = snapshot

            total_snapshots += 1

    session.commit()

    print(
        f"Created {total_snapshots} snapshots"
    )

    print(
        f"Created {total_alerts} alerts"
    )