import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# Connect to database
try:
    conn = sqlite3.connect("stocks.db")
    cursor = conn.cursor()
except sqlite3.Error as e:
    print(f"Error connecting to database: {e}")
    exit()

# Verify table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
if not tables:
    print("No tables found in stocks.db")
    conn.close()
    exit()
print(f"Tables in database: {tables}")

# Query all data
query = "SELECT * FROM recommendations"
try:
    df = pd.read_sql_query(query, conn)
    print("\nAll Stocks in recommendations Table:")
    if df.empty:
        print("No data found in recommendations table")
    else:
        print(df.to_string(index=False))
except sqlite3.Error as e:
    print(f"Query error: {e}")

# Query Buy recommendations for today
today = datetime.now().strftime("%Y-%m-%d")
query_buy = "SELECT ticker, rating, sector, signal, date FROM recommendations WHERE rating = 'Buy' AND date = ?"
try:
    df_buy = pd.read_sql_query(query_buy, conn, params=(today,))
    print(f"\nBuy Recommendations for {today}:")
    if df_buy.empty:
        print("No Buy recommendations found for today")
    else:
        print(df_buy.to_string(index=False))
except sqlite3.Error as e:
    print(f"Query error: {e}")

# Visualize Buy recommendations by sector
try:
    df_sector = pd.read_sql_query("""
        SELECT sector, COUNT(*) as total_buys
        FROM recommendations
        WHERE rating = 'Buy' AND date = ?
        GROUP BY sector
    """, conn, params=(today,))
    if not df_sector.empty:
        plt.figure(figsize=(10, 6))
        plt.bar(df_sector['sector'], df_sector['total_buys'], color='skyblue')
        plt.xlabel('Sector')
        plt.ylabel('Number of Buy Recommendations')
        plt.title(f'Buy Recommendations by Sector ({today})')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.show()
    else:
        print("No data to visualize")
except sqlite3.Error as e:
    print(f"Visualization query error: {e}")

conn.close()