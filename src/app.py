import streamlit as st
import json

# Authentication logic
def verify_pin(input_pin, correct_pin="your_secure_pin"):
    return input_pin == correct_pin

# Data management logic
def load_favorites():
    """Load favorites from the JSON file."""
    try:
        with open("data/favourites.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_favorites(favorites):
    """Save favorites to the JSON file."""
    with open("data/favourites.json", "w") as f:
        json.dump(favorites, f)

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

# Filtering logic
def filter_products(products, criteria):
    """Filter products based on the given criteria."""
    return [product for product in products if criteria(product)]

# Main app logic
st.title("WineFind - Your Personal Wine Collection")

# User authentication
pin = st.text_input("Enter your PIN to manage favorites:", type="password")
if st.button("Submit"):
    if verify_pin(pin):
        st.session_state.authenticated = True
        st.success("Authenticated! You can now manage your favorites.")
    else:
        st.session_state.authenticated = False
        st.error("Invalid PIN. Please try again.")

# Load product data and favorites
products = [{"id": "1", "title": "Wine A"}, {"id": "2", "title": "Wine B"}]  # Example product data
favorites = load_favorites()

# Filter products
criteria = lambda product: True  # Example criteria (show all products)
filtered_products = filter_products(products, criteria)

# Display products
st.write("Available Products:")
for product in filtered_products:
    st.write(f"{product['title']} {'(Favorite)' if is_favorite(product['id'], favorites) else ''}")

# Manage favorites
if st.session_state.get("authenticated", False):
    selected_product = st.selectbox("Select a product to add/remove from favorites:", options=[p["title"] for p in filtered_products])
    selected_product_id = next(p["id"] for p in filtered_products if p["title"] == selected_product)

    if st.button("Add to Favorites"):
        add_favorite(selected_product_id, favorites)
        st.success(f"{selected_product} has been added to your favorites.")

    if st.button("Remove from Favorites"):
        remove_favorite(selected_product_id, favorites)
        st.success(f"{selected_product} has been removed from your favorites.")

st.markdown("---")
st.write("Explore our collection and find your favorite wines!")
