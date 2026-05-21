from sqlalchemy import (
    String,Text,Boolean,Integer,Numeric,Float,DateTime,ForeignKey,
    CheckConstraint,func,text,create_engine
)

from sqlalchemy.orm import (
    DeclarativeBase,Mapped,mapped_column,relationship,sessionmaker
)
from datetime import datetime
from decimal import Decimal
from typing import Optional,List
from config import DATABASE_URL

class Base(DeclarativeBase):
    pass

class Seller(Base):
    __tablename__="sellers"
    id          : Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_name  : Mapped[str]           = mapped_column(String(200), nullable=False, unique=True)
    store_slug  : Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_client   : Mapped[bool]          = mapped_column(Boolean, server_default=text("false"), nullable=False)
    is_tracked  : Mapped[bool]          = mapped_column(Boolean, server_default=text("true"), nullable=False)
    country     : Mapped[str]           = mapped_column(String(10), server_default=text("'UAE'"), nullable=False)
    notes       : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    added_at    : Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    products    : Mapped[List["Product"]] = relationship("Product", back_populates="seller")

class Product(Base):
    __tablename__="products"

    id : Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)
    noon_sku        : Mapped[str]           = mapped_column(String(200), unique=True, nullable=False)
    seller_id       : Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("sellers.id"), nullable=True)
    name            : Mapped[str]           = mapped_column(Text, nullable=False)
    brand           : Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    model           : Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    category        : Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    subcategory     : Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    search_keyword  : Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    product_url     : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url       : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active       : Mapped[bool]          = mapped_column(Boolean, server_default=text("true"), nullable=False)
    first_seen_at   : Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at    : Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    seller          : Mapped[Optional["Seller"]]            = relationship("Seller", back_populates="products")
    price_snapshots : Mapped[List["PriceSnapshot"]]         = relationship("PriceSnapshot", back_populates="product")
    price_alerts    : Mapped[List["PriceAlert"]]            = relationship("PriceAlert", back_populates="product")

class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    __table_args__ = (
        CheckConstraint(
            "stock_status IN ('in_stock', 'out_of_stock', 'limited', 'unknown')",
            name="ck_price_snapshot_stock_status"
        ),
    )

    id              : Mapped[int]               = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id      : Mapped[int]               = mapped_column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    current_price   : Mapped[Decimal]           = mapped_column(Numeric(10, 2), nullable=False)
    original_price  : Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    discount_pct    : Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    currency        : Mapped[str]               = mapped_column(String(10), server_default=text("'AED'"), nullable=False)
    stock_status    : Mapped[str]               = mapped_column(String(50), server_default=text("'unknown'"), nullable=False)
    rating          : Mapped[Optional[float]]   = mapped_column(Float, nullable=True)
    review_count    : Mapped[int]               = mapped_column(Integer, server_default=text("0"), nullable=False)
    is_sponsored    : Mapped[bool]              = mapped_column(Boolean, server_default=text("false"), nullable=False)
    search_position : Mapped[Optional[int]]     = mapped_column(Integer, nullable=True)
    scraped_at      : Mapped[datetime]          = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    product         : Mapped["Product"] = relationship("Product", back_populates="price_snapshots")


# ─── Price Alerts ────────────────────────────────────────────
class PriceAlert(Base):
    __tablename__ = "price_alerts"

    __table_args__ = (
        CheckConstraint(
            "alert_type IN ('price_drop', 'back_in_stock', 'out_of_stock', 'new_competitor')",
            name="ck_price_alert_type"
        ),
    )

    id              : Mapped[int]               = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id      : Mapped[int]               = mapped_column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    alert_type      : Mapped[str]               = mapped_column(String(50), nullable=False)
    previous_value  : Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    current_value   : Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    change_pct      : Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    threshold_used  : Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    is_seen         : Mapped[bool]              = mapped_column(Boolean, server_default=text("false"), nullable=False)
    triggered_at    : Mapped[datetime]          = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    product         : Mapped["Product"] = relationship("Product", back_populates="price_alerts")


# ─── Scrape Logs ─────────────────────────────────────────────
class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'partial', 'failed')",
            name="ck_scrape_log_status"
        ),
    )

    id                  : Mapped[int]               = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword             : Mapped[Optional[str]]     = mapped_column(String(200), nullable=True)
    pages_scraped       : Mapped[int]               = mapped_column(Integer, server_default=text("0"), nullable=False)
    products_found      : Mapped[int]               = mapped_column(Integer, server_default=text("0"), nullable=False)
    products_new        : Mapped[int]               = mapped_column(Integer, server_default=text("0"), nullable=False)
    products_updated    : Mapped[int]               = mapped_column(Integer, server_default=text("0"), nullable=False)
    alerts_triggered    : Mapped[int]               = mapped_column(Integer, server_default=text("0"), nullable=False)
    errors              : Mapped[int]               = mapped_column(Integer, server_default=text("0"), nullable=False)
    error_details       : Mapped[Optional[str]]     = mapped_column(Text, nullable=True)
    duration_secs       : Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    status              : Mapped[str]               = mapped_column(String(20), nullable=False)
    run_at              : Mapped[datetime]          = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

# let's now create the engine and sesssion 
engine = create_engine(DATABASE_URL,echo=False)
SessionLocal = sessionmaker(bind=engine)

# init
def init_db():
    Base.metadata.create_all(bind=engine)
    print("All tables created successfully")

if __name__=="__main__":
    init_db()
