from pipeline.models import SessionLocal
from demo.create_sellers import seed_sellers
from demo.create_products import seed_products
from demo.create_snapshots import seed_snapshots
from demo.create_logs import seed_logs


def main():

    session = SessionLocal()

    try:

        print("Creating sellers...")
        sellers = seed_sellers(session)

        print("Creating products...")
        seed_products(session, sellers)

        print("Creating snapshots...")
        seed_snapshots(session)

        print("Creating Scrape Logs...")
        seed_logs(session)


        print("Done.")

    finally:
        session.close()


if __name__ == "__main__":
    main()