# demo/create_products.py

from pipeline.models import Product
from demo.constants import PRODUCTS


def make_sku(store_slug, model):

    clean_model = (
        model
        .replace(" ", "-")
        .replace("+", "PLUS")
        .upper()
    )

    return f"{store_slug.upper()}-{clean_model}"


def seed_products(session, sellers):

    products = []

    for seller_slug, seller in sellers.items():

        for p in PRODUCTS:

            sku = make_sku(
                seller_slug,
                p["model"]
            )

            product = Product(
                noon_sku=sku,
                seller_id=seller.id,
                name=p["model"],
                brand=p["brand"],
                model=p["model"],
                category="Electronics",
                subcategory="Mobile Devices",
                search_keyword=p["brand"],
                is_active=True
            )

            session.add(product)
            products.append(product)

    session.commit()

    return products