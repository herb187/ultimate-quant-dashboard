"""
=============================================================================
MODULE 1: DATA INGESTION PIPELINE (Crypto)
=============================================================================
DISCLAIMER: Educational purposes only. Not financial advice.
=============================================================================
"""

import ccxt
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import time
import datetime

# --- DATABASE CONFIGURATION ---
DB_CONFIG = {
    'dbname': 'market_data',
    'user': 'quant_user',
    'password': 'quant_password',
    'host': 'localhost',
    'port': '5432'
}

def setup_database_tables(conn):
    """Creates the hypertable for time-series OHLCV data."""
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS crypto_ohlcv (
                time TIMESTAMPTZ NOT NULL,
                symbol TEXT NOT NULL,
                open DOUBLE PRECISION,
                high DOUBLE PRECISION,
                low DOUBLE PRECISION,
                close DOUBLE PRECISION,
                volume DOUBLE PRECISION
            );
        """)
        try:
            cur.execute("""
                SELECT create_hypertable('crypto_ohlcv', 'time', if_not_exists => TRUE);
            """)
            conn.commit()
            print("[DB] Hypertable initialized successfully.")
        except Exception as e:
            print(f"[DB] Hypertable note: {e}")

def fetch_and_store_historical(exchange, symbol, timeframe='1h', limit=500):
    """Fetches historical candles and bulk inserts them into the DB."""
    print(f"[Pipeline] Fetching {limit} historical {timeframe} candles for {symbol}...")
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df['symbol'] = symbol
    
    records = [tuple(x) for x in df[['time', 'symbol', 'open', 'high', 'low', 'close', 'volume']].to_records(index=False)]
    
    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO crypto_ohlcv (time, symbol, open, high, low, close, volume)
            VALUES %s
            ON CONFLICT DO NOTHING
        """, records)
        conn.commit()
    conn.close()
    print(f"[Pipeline] Successfully stored {len(records)} records in TimescaleDB.")

def stream_realtime_updates(exchange, symbol, interval_seconds=60):
    """Polls the exchange and upserts the latest candle."""
    print(f"[Stream] Starting real-time polling for {symbol} every {interval_seconds}s...")
    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, '1m', limit=1)
            if not ohlcv:
                continue
            candle = ohlcv[0]
            time_ts = datetime.datetime.fromtimestamp(candle[0] / 1000, tz=datetime.timezone.utc)
            
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO crypto_ohlcv (time, symbol, open, high, low, close, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (time, symbol) 
                    DO UPDATE SET 
                        open = EXCLUDED.open, high = EXCLUDED.high, 
                        low = EXCLUDED.low, close = EXCLUDED.close, 
                        volume = EXCLUDED.volume;
                """, (time_ts, symbol, candle[1], candle[2], candle[3], candle[4], candle[5]))
                conn.commit()
            conn.close()
            print(f"[Stream] {symbol} | Close: {candle[4]} | Vol: {candle[5]} | Saved to DB.")
            time.sleep(interval_seconds)
        except Exception as e:
            print(f"[Stream Error] {e}. Retrying in 10s...")
            time.sleep(10)

if __name__ == "__main__":
    binance = ccxt.binance({'enableRateLimit': True})
    TARGET_SYMBOL = 'BTC/USDT'
    
    conn = psycopg2.connect(**DB_CONFIG)
    setup_database_tables(conn)
    conn.close()
    
    fetch_and_store_historical(binance, TARGET_SYMBOL, '1h', 100)
    stream_realtime_updates(binance, TARGET_SYMBOL, interval_seconds=30)