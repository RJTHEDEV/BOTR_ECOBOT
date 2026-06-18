from flask import Flask, render_template, request, jsonify
import sqlite3
import os

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "bot.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    # Get top 20 richest users
    try:
        richest_users = conn.execute('SELECT user_id, balance, bank, (balance + bank) as net_worth FROM users ORDER BY net_worth DESC LIMIT 20').fetchall()
    except Exception as e:
        print(e)
        richest_users = []
    conn.close()
    return render_template('index.html', title="Global Leaderboard", users=richest_users)

@app.route('/clans')
def clans():
    conn = get_db_connection()
    # Get top 20 clans by level and bank
    try:
        top_clans = conn.execute('SELECT name, owner_id, bank, level FROM clans ORDER BY level DESC, bank DESC LIMIT 20').fetchall()
    except Exception as e:
        print(e)
        top_clans = []
    conn.close()
    return render_template('clans.html', title="Top Clans", clans=top_clans)

@app.route('/api/stats')
def stats():
    conn = get_db_connection()
    try:
        total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        total_clans = conn.execute('SELECT COUNT(*) FROM clans').fetchone()[0]
        total_economy = conn.execute('SELECT SUM(balance + bank) FROM users').fetchone()[0]
    except Exception as e:
        total_users = 0
        total_clans = 0
        total_economy = 0
    conn.close()
    return jsonify({
        "users": total_users,
        "clans": total_clans,
        "total_wealth": total_economy
    })

if __name__ == '__main__':
    # Run on port 5000, accessible externally
    app.run(host='0.0.0.0', port=5000, debug=True)
