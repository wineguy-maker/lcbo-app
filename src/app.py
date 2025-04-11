import streamlit as st
import pandas as pd
import time
from datetime import datetime
import requests
import re

# -------------------------------
# Data Handling
# -------------------------------
@st.cache_data
def load_data(file_path):
    df = pd.read_csv(file_path)
    return df
    
def load_food_items():
    try:
        food_items = pd.read_csv('food_items.csv')
        return food_items
    except Exception as e:
        st.error(f"Error loading food items: {e}")
        return pd.DataFrame(columns=['Category', 'FoodItem'])
        
def sort_data(data, column):
    sorted_data = data.sort_values(by=column, ascending=False)
    return sorted_data

# -------------------------------
# Filter functions
# -------------------------------
def search_data(data, search_text):
    if search_text:
        data = data[data['title'].str.contains(search_text, case=False, na=False)]
    return data

def sort_data_filter(data, sort_by):
    if sort_by == '# of reviews':
        data = data.sort_values(by='raw_avg_reviews', ascending=False)
    elif sort_by == 'Rating':
        data = data.sort_values(by='raw_ec_rating', ascending=False)
    elif sort_by == 'Top Viewed - Year':
        data = data.sort_values(by='raw_view_rank_yearly', ascending=True)
    elif sort_by == 'Top Veiwed - Month':
        data = data.sort_values(by='raw_view_rank_monthly', ascending=True)
    elif sort_by == 'Top Seller - Year':
        data = data.sort_values(by='raw_sell_rank_yearly', ascending=True)
    elif sort_by == 'Top Seller - Month':
        data = data.sort_values(by='raw_sell_rank_monthly', ascending=True)
    else:
        data = data.sort_values(by='weighted_rating', ascending=False)
    return data

def filter_data(data, country='All Countries', region='All Regions', varietal='All Varietals', exclude_usa=False, in_stock=False, only_vintages=False, store='Select Store'):
    if country != 'All Countries':
        data = data[data['raw_country_of_manufacture'] == country]
    if region != 'All Regions':
        data = data[data['raw_lcbo_region_name'] == region]
    if varietal != 'All Varietals':
        data = data[data['raw_lcbo_varietal_name'] == varietal]
    if store != 'Select Store':
        data = data[data['store_name'] == store]
    if in_stock:
        data = data[data['stores_inventory'] > 0]
    if only_vintages:
        data = data[data['raw_lcbo_program'].str.contains(r"['\"]Vintages['\"]", regex=True, na=False)]
    if exclude_usa:
        data = data[data['raw_country_of_manufacture'] != 'United States']
    return data

# -------------------------------
# Helper: Transform Image URL
# -------------------------------
def transform_image_url(url, new_size):
    """
    Replace the ending pattern (e.g., '319.319.PNG') in the URL with the new size string.
    new_size should include extension, e.g., '2048.2048.png' or '1280.1280.png'.
    """
    if not isinstance(url, str):
        return url
    # This regex finds a pattern like "digits.digits.ext" at the end of the URL
    return re.sub(r"\d+\.\d+\.(png|PNG)$", new_size, url)

# -------------------------------
# Refresh function
# -------------------------------
def refresh_data(store_id=None):
    current_time = datetime.now()
    st.info("Refreshing data...")

    url = "https://platform.cloud.coveo.com/rest/search/v2?organizationId=lcboproduction2kwygmc"
    headers = {
        "User-Agent": "your_user_agent",
        "Accept": "application/json",
        "Authorization": "Bearer xx883b5583-07fb-416b-874b-77cce565d927",
        "Content-Type": "application/json",
        "Referer": "https://www.lcbo.com/"
    }

    initial_payload = {
        "q": "",
        "tab": "clp-products-wine-red_wine",
        "sort": "ec_rating descending",
        "facets": [
            {
                "field": "ec_rating",
                "currentValues": [
                    {
                        "value": "4..5inc",
                        "state": "selected"
                    }
                ]
            }
        ],
        "numberOfResults": 500,
        "firstResult": 0,
        "aq": "@ec_visibility==(2,4) @cp_browsing_category_deny<>0 @ec_category==\"Products|Wine|Red Wine\" (@ec_rating==5..5 OR @ec_rating==4..4.9)"
    }

    if store_id:
        dictionaryFieldContext = {
            "stores_stock": "",
            "stores_inventory": store_id,
            "stores_stock_combined": store_id,
            "stores_low_stock_combined": store_id
        }
        initial_payload.update(dictionaryFieldContext)

    def get_items(payload):
        response = requests.post(url, headers=headers, json=payload)
        return response.json()

    data = get_items(initial_payload)
    if 'results' in data:
        all_items = data['results']
        total_count = data['totalCount']
        st.info(f"Total Count: {total_count}")

        num_requests = (total_count // 500) + (1 if total_count % 500 != 0 else 0)

        for i in range(1, num_requests):
            payload = {
                "q": "",
                "tab": "clp-products-wine-red_wine",
                "sort": "ec_rating descending",
                "facets": [
                    {
                        "field": "ec_rating",
                        "currentValues": [
                            {
                                "value": "4..5inc",
                                "state": "selected"
                            }
                        ]
                    }
                ],
                "numberOfResults": 500,
                "firstResult": i * 500,
                "aq": "@ec_visibility==(2,4) @cp_browsing_category_deny<>0 @ec_category==\"Products|Wine|Red Wine\" (@ec_rating==5..5 OR @ec_rating==4..4.9)"
            }
            if store_id:
                payload.update(dictionaryFieldContext)
            data = get_items(payload)
            if 'results' in data:
                all_items.extend(data['results'])
            else:
                st.error(f"Key 'results' not found in the response during pagination. Response: {data}")
            time.sleep(1)  # Avoid hitting the server too frequently

        products = []
        for product in all_items:
            raw_data = product['raw']
            product_info = {
                'title': product.get('title', 'N/A'),
                'uri': product.get('uri', 'N/A'),
                'raw_ec_thumbnails': raw_data.get('ec_thumbnails', 'N/A'),
                'raw_ec_shortdesc': raw_data.get('ec_shortdesc', 'N/A'),
                'raw_lcbo_tastingnotes': raw_data.get('lcbo_tastingnotes', 'N/A'),
                'raw_lcbo_region_name': raw_data.get('lcbo_region_name', 'N/A'),
                'raw_country_of_manufacture': raw_data.get('country_of_manufacture', 'N/A'),
                'raw_lcbo_program': raw_data.get('lcbo_program', 'N/A'),
                'raw_created_at': raw_data.get('created_at', 'N/A'),
                'raw_is_buyable': raw_data.get('is_buyable', 'N/A'),
                'raw_ec_price': raw_data.get('ec_price', 'N/A'),
                'raw_ec_final_price': raw_data.get('ec_final_price', 'N/A'),
                'raw_lcbo_unit_volume': raw_data.get('lcbo_unit_volume', 'N/A'),
                'raw_lcbo_alcohol_percent': raw_data.get('lcbo_alcohol_percent', 'N/A'),
                'raw_lcbo_sugar_gm_per_ltr': raw_data.get('lcbo_sugar_gm_per_ltr', 'N/A'),
                'raw_lcbo_bottles_per_pack': raw_data.get('lcbo_bottles_per_pack', 'N/A'),
                'raw_sysconcepts': raw_data.get('sysconcepts', 'N/A'),
                'raw_ec_category': raw_data.get('ec_category', 'N/A'),
                'raw_ec_category_filter': raw_data.get('ec_category_filter', 'N/A'),
                'raw_lcbo_varietal_name': raw_data.get('lcbo_varietal_name', 'N/A'),
                'raw_stores_stock': raw_data.get('stores_stock', 'N/A'),
                'raw_stores_stock_combined': raw_data.get('stores_stock_combined', 'N/A'),
                'raw_stores_low_stock_combined': raw_data.get('stores_low_stock_combined', 'N/A'),
                'raw_stores_low_stock': raw_data.get('stores_low_stock', 'N/A'),
                'raw_out_of_stock': raw_data.get('out_of_stock', 'N/A'),
                'stores_inventory': raw_data.get('stores_inventory', 0),
                'raw_online_inventory': raw_data.get('online_inventory', 0),
                'raw_avg_reviews': raw_data.get('avg_reviews', 0),
                'raw_ec_rating': raw_data.get('ec_rating', 0),
                'weighted_rating': 0.0,  # Placeholder for weighted rating
                'raw_view_rank_yearly': raw_data.get('view_rank_yearly', 'N/A'),
                'raw_view_rank_monthly': raw_data.get('view_rank_monthly', 'N/A'),
                'raw_sell_rank_yearly': raw_data.get('sell_rank_yearly', 'N/A'),
                'raw_sell_rank_monthly': raw_data.get('sell_rank_monthly', 'N/A')
            }
            products.append(product_info)

        
        df_products = pd.DataFrame(products)

        # Calculate mean rating for products with reviews
        valid_reviews = pd.to_numeric(df_products['raw_avg_reviews'], errors='coerce')
        valid_ratings = pd.to_numeric(df_products['raw_ec_rating'], errors='coerce')
        mean_rating = valid_ratings[valid_reviews > 0].mean()
        minimum_votes = 10  # Minimum number of votes required

        def weighted_rating(R, v, m, C):
            # Calculate IMDb-style weighted rating
            return (v / (v + m)) * R + (m / (v + m)) * C

        # Compute weighted rating using numeric conversion
        df_products['weighted_rating'] = df_products.apply(
            lambda x: weighted_rating(
                float(x['raw_ec_rating']) if pd.notna(x['raw_ec_rating']) and x['raw_ec_rating'] != 'N/A' else 0,
                float(x['raw_avg_reviews']) if pd.notna(x['raw_avg_reviews']) and x['raw_avg_reviews'] != 'N/A' else 0,
                minimum_votes,
                mean_rating if not pd.isna(mean_rating) else 0
            ),
            axis=1
        )

        df_products.to_csv('products.csv', index=False, encoding='utf-8-sig')
        st.success("Data refreshed successfully!")
        return load_data("products.csv")
    else:
        st.error("Failed to retrieve data from the API.")
        return None

# -------------------------------
# Main Streamlit App
# -------------------------------
def main():
    st.title("LCBO Wine Filter")
    # Add this line to clear the cached data
    st.cache_data.clear()
    # Initialize session state for store and image modal trigger
    if 'selected_store' not in st.session_state:
        st.session_state.selected_store = 'Select Store'

    # Store Selector
    store_options = ['Select Store', 'Bradford', 'E. Gwillimbury', 'Upper Canada', 'Yonge & Eg', 'Dufferin & Steeles']
    store_ids = {
        "Bradford": "145",
        "E. Gwillimbury": "391",
        "Upper Canada": "226",
        "Yonge & Eg": "457",
        "Dufferin & Steeles": "618"
    }
    selected_store = st.sidebar.selectbox("Store", options=store_options)

    # Refresh data if store selection changes
    if selected_store != st.session_state.selected_store:
        st.session_state.selected_store = selected_store
        if selected_store != 'Select Store':
            store_id = store_ids.get(selected_store)
            data = refresh_data(store_id=store_id)
        else:
            data = load_data("products.csv")
    else:
        data = load_data("products.csv")

    # Sidebar Filters with improved header
    st.sidebar.header("Filter Options 🔍")
    search_text = st.sidebar.text_input("Search", value="")
    sort_by = st.sidebar.selectbox("Sort by",
                                   ['Sort by', '# of reviews', 'Rating', 'Top Veiwed - Year', 'Top Veiwed - Month', 'Top Seller - Year',
                                    'Top Seller - Month'])
    
    # Create filter options from data
    
    # Load food items
    food_items = load_food_items()
    
    # Get unique categories
    categories = food_items['Category'].unique()
    
    country_options = ['All Countries'] + sorted(data['raw_country_of_manufacture'].dropna().unique().tolist())
    region_options = ['All Regions'] + sorted(data['raw_lcbo_region_name'].dropna().unique().tolist())
    varietal_options = ['All Varietals'] + sorted(data['raw_lcbo_varietal_name'].dropna().unique().tolist())
    food_options = ['All Dishes'] + sorted(categories.tolist())
    
    country = st.sidebar.selectbox("Country", options=country_options)
    region = st.sidebar.selectbox("Region", options=region_options)
    varietal = st.sidebar.selectbox("Varietal", options=varietal_options)
    food_category = st.sidebar.selectbox("Food Category", options=food_options)
    exclude_usa = st.sidebar.checkbox("Exclude USA", value=False)
    in_stock = st.sidebar.checkbox("In Stock Only", value=False)
    only_vintages = st.sidebar.checkbox("Only Vintages", value=False)

   
    # Apply Filters and Sorting
    filtered_data = data.copy()
    filtered_data = filter_data(filtered_data, country=country, region=region, varietal=varietal, exclude_usa=exclude_usa,
                                in_stock=in_stock, only_vintages=only_vintages)
    filtered_data = search_data(filtered_data, search_text)

     # Food Category Filtering
    if food_category != 'All Dishes':
        selected_items = food_items[food_items['Category'] == food_category]['FoodItem'].str.lower().tolist()
        filtered_data = filtered_data[filtered_data['raw_sysconcepts'].fillna('').apply(
            lambda x: any(item in str(x).lower() for item in selected_items)
        )]

    sort_option = sort_by if sort_by != 'Sort by' else 'weighted_rating'
    if sort_option != 'weighted_rating':
        filtered_data = sort_data_filter(filtered_data, sort_option)
    else:
        filtered_data = sort_data(filtered_data, sort_option)

    st.write(f"Showing **{len(filtered_data)}** products")
             
    # Pagination
    page_size = 10
    total_products = len(filtered_data)
    total_pages = (total_products // page_size) + (1 if total_products % page_size else 0)
    if total_pages > 0:
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
    else:
        page = 1
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_data = filtered_data.iloc[start_idx:end_idx]

    # Display Products
    for idx, row in page_data.iterrows():
        st.markdown(f"### {row['title']}")
        st.markdown(f"**Price:** ${row.get('raw_ec_price', 'N/A')} | **Rating:** {row.get('raw_ec_rating', 'N/A')} | **Reviews:** {row.get('raw_avg_reviews', 'N/A')}")
        
        # Display the thumbnail image
        thumbnail_url = row.get('raw_ec_thumbnails', None)
        if pd.notna(thumbnail_url) and thumbnail_url != 'N/A':
            st.image(thumbnail_url, width=150)
            # Add an "Enlarge Image" button below the thumbnail.
            with st.popover("Enlarge Image"):
                large_image_url = transform_image_url(thumbnail_url, "2048.2048.png")
                st.image(large_image_url, use_container_width=True)
        else:
            st.write("No image available.")

        # -- Instead of a "View Details" button, use an expander --
        with st.expander("Product Details", expanded=False):
            # Here, just inline the same content you used to show in show_detailed_product_popup()
            st.write("### Detailed Product View")
            if pd.notna(thumbnail_url) and thumbnail_url != 'N/A':
                detail_image_url = transform_image_url(thumbnail_url, "1280.1280.png")
                st.image(detail_image_url, width=300)
            if pd.notna(row['raw_lcbo_program']) and row['raw_lcbo_program'] != 'N/A': 
                st.markdown(f"**Vintage**")
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
            st.markdown(f"**Store Inventory:** {row['stores_inventory']}")
            st.markdown(f"**Monthly Sold Rank:** {row['raw_sell_rank_monthly']}")
            st.markdown(f"**Monthly View Rank:** {row['raw_view_rank_monthly']}")
            st.markdown(f"**Yearly Sold Rank:** {row['raw_sell_rank_yearly']}")
            st.markdown(f"**Yearly View Rank:** {row['raw_view_rank_yearly']}")
            st.markdown(f"**Alcohol %:** {row['raw_lcbo_alcohol_percent']}")
            st.markdown(f"**Sugar (p/ltr):** {row['raw_lcbo_sugar_gm_per_ltr']}")
    
        st.markdown("---")

if __name__ == "__main__":
    main()
