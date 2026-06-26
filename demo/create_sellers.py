# demo/create_sellers.py

from pipeline.models import Seller
from demo.constants import SELLERS


def seed_sellers(session):

    sellers = {}

    for seller_data in SELLERS:

        seller = Seller(
            store_name=seller_data["store_name"],
            store_slug=seller_data["store_slug"],
            is_client=seller_data["is_client"],
            is_tracked=True,
            country="UAE"
        )

        session.add(seller)

    session.commit()

    all_sellers = session.query(Seller).all()

    for s in all_sellers:
        sellers[s.store_slug] = s

    return sellers