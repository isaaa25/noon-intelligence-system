import os
from dotenv import load_dotenv

load_dotenv()


REQUIRED_VARS = ["DB_HOST","DB_PORT","DB_NAME","DB_USER","DB_PASSWORD"]

missing = [var for var in REQUIRED_VARS if not os.getenv(var)]

if missing:
    raise EnvironmentError(
        f"Missing required environment variables: {', '.join(missing)}\n"
        f"Check your .env file"
    )
# let's make the database url 

DATABASE_URL = (
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

# scraper settings 
DELAY_MIN = 2.0
DELAY_MAX = 5.0
MAX_RETRIES = 3
PAGES_PER_KEYWORD = 2 

# alert settings 
PRICE_DROP_THRESHOLD_PCT = 5.0

# User agents 
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]