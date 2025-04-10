# filepath: WineFind/WineFind/src/components/product_display.py

import streamlit as st
import pandas as pd
from utils.data import load_data
from utils.favorites import load_favourites, toggle_favourite

def display_products(data):
    st.write(f"Showing **{len(data)}** products")
    
    for idx, row in data.iterrows():
        st.markdown(f"### {row['title']}")
        promo_price = row.get('raw_ec_promo_price', None)
        regular_price = row.get('raw_ec_price', 'N/A')

        wine_id = row.get('uri', row['title'])  # Fallback to 'title' if 'id' is missing
        if not wine_id:
            wine_id = f"wine-{idx}"  # Generate a unique ID if both are missing

        # Load favorites from the JSON file
        favourites = load_favourites()
        is_favourite = wine_id in favourites  # Check the updated favourites list
        heart_icon = "❤️" if is_favourite else "🤍"
        
        if st.button(f"{heart_icon} Favourite", key=f"fav-{wine_id}"):
            toggle_favourite(wine_id)
            st.experimental_rerun()

        if pd.notna(promo_price) and promo_price != 'N/A':
            st.markdown(
                f"""<div style="font-size: 16px;"><strong>Price:</strong> <span style="color: red;">${promo_price}</span> 
                <span style="text-decoration: line-through; color: gray;">${regular_price}</span></div>""",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"""<div style="font-size: 16px;"><strong>Price:</strong> ${regular_price}</div>""",
                unsafe_allow_html=True
            )
        
        st.markdown(f"**Rating:** {row.get('raw_ec_rating', 'N/A')} | **Reviews:** {row.get('raw_avg_reviews', 'N/A')}")

        thumbnail_url = row.get('raw_ec_thumbnails', None)
        if pd.notna(thumbnail_url) and thumbnail_url != 'N/A':
            st.image(thumbnail_url, width=150)
        else:
            st.write("No image available.")

        with st.expander("Product Details", expanded=False):
            st.write("### Detailed Product View")
            if pd.notna(thumbnail_url) and thumbnail_url != 'N/A':
                st.image(thumbnail_url, width=300)
            st.markdown(f"**Title:** {row['title']}")
            st.markdown(f"**URL:** {row['uri']}")
            st.markdown(f"**Country:** {row['raw_country_of_manufacture']}")
            st.markdown(f"**Region:** {row['raw_lcbo_region_name']}")
            st.markdown(f"**Type:** {row['raw_lcbo_varietal_name']}")
            st.markdown(f"**Size:** {row['raw_lcbo_unit_volume']}")
            st.markdown(f"**Description:** {row['raw_ec_shortdesc']}")
            st.markdown(f"**Price:** {row['raw_ec_price']}")
            st.markdown(f"**Rating:** {row['raw_ec_rating']}")
            st.markdown(f"**Reviews:** {row['raw_avg_reviews']}")
    
        st.markdown("---")