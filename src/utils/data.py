import csv
import requests
import streamlit as st

KVSTORE_URL = "https://kvstore.io/collections/favorites"
API_KEY = st.secrets["kv_api_key"]

def load_products():
    """Load product details from products.csv."""
    with open("data/products.csv", "r") as f:
        reader = csv.DictReader(f)
        return {row["wine_id"]: row for row in reader}

def display_favorites(favorites):
    """Display favorite products by linking to products.csv."""
    products = load_products()
    return [products[wine_id] for wine_id in favorites if wine_id in products]

def load_favorites():
    """Load favorites from KVStore."""
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(KVSTORE_URL, headers=headers)
    if response.status_code == 200:
        return response.json()
    return []

def save_favorites(favorites):
    """Save favorites to KVStore."""
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.put(KVSTORE_URL, json=favorites, headers=headers)
    response.raise_for_status()

def add_favorite(wine_id, favorites):
    """Add a wine to the favorites list."""
    if wine_id not in favorites:
        favorites.append(wine_id)
        save_favorites(favorites)

def remove_favorite(wine_id, favorites):
    """Remove a wine from the favorites list."""
    if wine_id in favorites:
        favorites.remove(wine_id)
        save_favorites(favorites)

def is_favorite(wine_id, favorites):
    """Check if a wine is in the favorites list."""
    return wine_id in favorites

def load_data():
    """Placeholder for load_data function."""
    pass