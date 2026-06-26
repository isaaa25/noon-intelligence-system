# demo/constants.py

from decimal import Decimal

SELLERS = [
    {
        "store_name": "TechZone UAE",
        "store_slug": "techzone",
        "is_client": True,
        "profile": "reactive"
    },
    {
        "store_name": "Sharaf DG",
        "store_slug": "sharaf",
        "is_client": False,
        "profile": "aggressive"
    },
    {
        "store_name": "Virgin Megastore",
        "store_slug": "virgin",
        "is_client": False,
        "profile": "moderate"
    },
    {
        "store_name": "iStyle",
        "store_slug": "istyle",
        "is_client": False,
        "profile": "premium"
    }
]

PRODUCTS = [
    {
        "brand": "Apple",
        "model": "iPhone 15 128GB",
        "base_price": Decimal("3399")
    },
    {
        "brand": "Apple",
        "model": "iPhone 15 256GB",
        "base_price": Decimal("3799")
    },
    {
        "brand": "Apple",
        "model": "iPhone 15 Pro 256GB",
        "base_price": Decimal("4499")
    },
    {
        "brand": "Apple",
        "model": "iPhone 15 Pro Max 256GB",
        "base_price": Decimal("4999")
    },
    {
        "brand": "Samsung",
        "model": "Galaxy S25",
        "base_price": Decimal("2999")
    },
    {
        "brand": "Samsung",
        "model": "Galaxy S25 Plus",
        "base_price": Decimal("3499")
    },
    {
        "brand": "Samsung",
        "model": "Galaxy S25 Ultra",
        "base_price": Decimal("4799")
    },
    {
        "brand": "Apple",
        "model": "AirPods Pro 2",
        "base_price": Decimal("949")
    },
    {
        "brand": "Apple",
        "model": "Apple Watch Series 10",
        "base_price": Decimal("1799")
    },
    {
        "brand": "Apple",
        "model": "iPad Air M3",
        "base_price": Decimal("2499")
    }
]