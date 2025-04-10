# File: /WineFind/WineFind/src/app.py

import streamlit as st
from utils.auth import verify_pin
from utils.data import load_products, load_favorites, save_favorites, add_favorite, remove_favorite
from components.filters import filter_products
from components.product_display import display_products

# Initialize the Streamlit app
st.title("WineFind - Your Personal Wine Collection")

# User authentication
pin = st.text_input("Enter your PIN to manage favorites:", type="password")
if verify_pin(pin):
    st.session_state.authenticated = True
    st.success("Authenticated! You can now manage your favorites.")
else:
    st.session_state.authenticated = False

# Load product data
products = load_products()
favorites = load_favorites()

# Filter products based on user input
filtered_products = filter_products(products)

# Display products
display_products(filtered_products, favorites)

# Manage favorites
if st.session_state.authenticated:
    selected_product = st.selectbox("Select a product to add/remove from favorites:", options=filtered_products['title'])
    if st.button("Add to Favorites"):
        add_favorite(selected_product, favorites)
        save_favorites(favorites)
        st.success(f"{selected_product} has been added to your favorites.")
    if st.button("Remove from Favorites"):
        remove_favorite(selected_product, favorites)
        save_favorites(favorites)
        st.success(f"{selected_product} has been removed from your favorites.")

st.markdown("---")
st.write("Explore our collection and find your favorite wines!")