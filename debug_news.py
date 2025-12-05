import yfinance as yf
import json

try:
    ticker = "TSLA"
    stock = yf.Ticker(ticker)
    news = stock.news
    if news:
        item = news[0]
        if 'content' in item:
            print("Content Keys:", item['content'].keys())
            print("Title:", item['content'].get('title'))
            print("Link:", item['content'].get('canonicalUrl', {}).get('url'))
        else:
            print("Keys:", item.keys())
    else:
        print("No news found")
except Exception as e:
    print(f"Error: {e}")
