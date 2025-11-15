"""API routes for Rowlytics."""

import os
import sqlite3

from flask import Blueprint, jsonify

api_bp = Blueprint("api", __name__, url_prefix="/api")

# Database file stored next to this python file
DB_PATH = os.path.join(os.path.dirname(__file__), "visits.db")


def increment_page(slug: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Make sure the table exists
    c.execute("""
        CREATE TABLE IF NOT EXISTS page_visits (
            slug TEXT PRIMARY KEY,
            count INTEGER NOT NULL
        )
    """)

    # Increment or insert row
    c.execute("""
        INSERT INTO page_visits (slug, count)
        VALUES (?, 1)
        ON CONFLICT(slug) DO UPDATE SET count = count + 1
    """, (slug,))

    conn.commit()
    conn.close()


@api_bp.route("/increment/<slug>", methods=["POST"])
def increment(slug):
    increment_page(slug)
    return jsonify({"status": "ok"})


@api_bp.route("/count/<slug>")
def get_count(slug):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT count FROM page_visits WHERE slug = ?", (slug,))
    row = c.fetchone()
    conn.close()
    return jsonify({"count": row[0] if row else 0})
