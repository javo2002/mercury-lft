import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Boolean, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.sql import func
from config import settings

Base = declarative_base()

class Trade(Base):
    __tablename__ = 'trades'
    id = Column(Integer, primary_key=True)
    # Add a client-side order ID for linking open/close trades
    client_order_id = Column(String, unique=True, nullable=False, index=True)
    timestamp = Column(String)
    ticker = Column(String, nullable=False, index=True)
    asset_class = Column(String, default='stock')
    action = Column(String, nullable=False)
    quantity = Column(Float)
    price = Column(Float)
    reason = Column(String)
    trade_type = Column(String)
    stop_price = Column(Float)
    # Link to post-trade analysis
    analysis = relationship("PostTradeAnalysis", back_populates="trade", uselist=False)

# --- NEW TABLE FOR PHASE 3 ---
class PostTradeAnalysis(Base):
    __tablename__ = 'post_trade_analysis'
    id = Column(Integer, primary_key=True)
    trade_id = Column(Integer, ForeignKey('trades.id'), nullable=False)
    pnl = Column(Float)
    market_comparison_pnl = Column(Float)
    ai_summary = Column(Text)
    trade = relationship("Trade", back_populates="analysis")

# --- NEW TABLE FOR PHASE 3 ---
class Feedback(Base):
    __tablename__ = 'feedback'
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, nullable=False) # e.g., Mailbox message ID
    source_type = Column(String, nullable=False) # e.g., 'daily_plan'
    rating = Column(Integer, nullable=False) # 1 for positive, -1 for negative
    timestamp = Column(String)

# --- NEW TABLE FOR PHASE 4 ---
class BacktestResult(Base):
    __tablename__ = 'backtest_results'
    id = Column(Integer, primary_key=True)
    strategy_name = Column(String, nullable=False)
    parameters = Column(String) # Stored as a string dictionary
    start_date = Column(String)
    end_date = Column(String)
    sharpe_ratio = Column(Float)
    cagr = Column(Float)
    max_drawdown = Column(Float)
    win_rate = Column(Float)
    timestamp = Column(String)
    report_url = Column(String) # Link to the generated pyfolio report

# ... other existing tables (Signal, Sentiment, Mailbox, etc.) remain the same ...
class Signal(Base):
    __tablename__ = 'signals'
    id = Column(Integer, primary_key=True)
    ticker = Column(String, nullable=False, index=True)
    asset_class = Column(String, default='stock')
    date = Column(String, nullable=False, index=True)
    sma_signal = Column(String)
    rsi_signal = Column(String)
    volatility_signal = Column(String)
    pattern_signal = Column(String)
    live_signal = Column(String, index=True)
    last_close = Column(Float)

class Sentiment(Base):
    __tablename__ = 'sentiment'
    id = Column(Integer, primary_key=True)
    ticker = Column(String, nullable=False, index=True)
    date = Column(String, nullable=False, index=True)
    sentiment_score = Column(Float)
    sentiment_label = Column(String)
    keywords = Column(String)
    top_headline = Column(String)

class Mailbox(Base):
    __tablename__ = 'mailbox'
    id = Column(Integer, primary_key=True)
    timestamp = Column(String)
    subject = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String, default='unread', index=True)

class InstrumentRisk(Base):
    __tablename__ = "instrument_risk"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True, nullable=False)
    max_position_size_usd = Column(Float, default=10000.0)
    atr_stop_multiplier = Column(Float, default=2.5)

class SystemStatus(Base):
    __tablename__ = "system_status"
    id = Column(Integer, primary_key=True)
    trading_enabled = Column(Boolean, default=True, nullable=False)


engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    if session.query(SystemStatus).count() == 0:
        session.add(SystemStatus(id=1, trading_enabled=True))
        session.commit()
    session.close()
    print("Database initialized and all tables created.")

