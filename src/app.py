import streamlit as st
import pandas as pd
import time
from datetime import datetime
import requests
import re
from supabase import create_client, Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading

# Supabase Configuration
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_SERVICE_ROLE_KEY = st.secrets["supabase"]["key"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

PRODUCTS_TABLE = "Products"
FAVOURITES_TABLE = "Favourites"

def supabase_get_records(table_name):
    """Fetch all records from a Supabase table."""
    try:
        response = supabase.table(table_name).select("*").execute()
        return response.data  # Use the data attribute for successful responses
    except Exception as e:
        st.error(f"Failed to fetch records from {table_name}: {e}")
        return []

def supabase_upsert_record(table_name, record):
    """Insert or update a record in a Supabase table."""
    try:
        response = supabase.table(table_name).upsert(record).execute()
        return response.data  # Use the data attribute for successful responses
    except Exception as e:
        st.error(f"Failed to upsert record in {table_name}: {e}")
        return None

def supabase_delete_record(table_name, URI, user_id):
    """Delete a record from a Supabase table."""
    try:
        query = supabase.table(table_name)
        response = (
        supabase.table(table_name)
        .delete()
        .eq("URI", URI)        # First filter
        .eq("User ID",user_id)  # Second filter
        .execute()
        )
        return response.data  # Use the data attribute for successful responses
    except Exception as e:
        st.error(f"Failed to delete record from {table_name}: {e}")
        return None

def load_products_from_supabase():
    """Load products from Supabase."""
    records = supabase_get_records(PRODUCTS_TABLE)
    return pd.DataFrame(records)

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
    """Sort data based on the selected criteria, with IMDb-style weighted rating as the default."""
    if sort_by == '# of reviews':
        data = data.sort_values(by='raw_avg_reviews', ascending=False)
    elif sort_by == 'Rating':
        data = data.sort_values(by='raw_ec_rating', ascending=False)
    elif sort_by == 'Top Viewed - Year':
        data = data.sort_values(by='raw_view_rank_yearly', ascending=True)
    elif sort_by == 'Top Viewed - Month':
        data = data.sort_values(by='raw_view_rank_monthly', ascending=True)
    elif sort_by == 'Top Seller - Year':
        data = data.sort_values(by='raw_sell_rank_yearly', ascending=True)
    elif sort_by == 'Top Seller - Month':
        data = data.sort_values(by='raw_sell_rank_monthly', ascending=True)
    else:
        # Default to IMDb-style weighted rating
        data = data.sort_values(by='weighted_rating', ascending=False)
    return data

def filter_and_sort_data(data, sort_by, **filters):
    """Apply filters and ensure IMDb-style sorting is always the default."""
    # Extract search_text and store from filters and handle them separately
    search_text = filters.pop('search_text', '')
    filters.pop('store', None)  # Remove 'store' key if it exists

    # Apply filters
    data = filter_data(data, **filters)

    # Apply search filter
    data = search_data(data, search_text)

    # Sort data
    data = sort_data_filter(data, sort_by)
    return data

def filter_data(data, country='All Countries', region='All Regions', varietal='All Varietals', exclude_usa=False, in_stock=False, only_vintages=False):
    if country != 'All Countries':
        data = data[data['raw_country_of_manufacture'] == country]
    if region != 'All Regions':
        data = data[data['raw_lcbo_region_name'] == region]
    if varietal != 'All Varietals':
        data = data[data['raw_lcbo_varietal_name'] == varietal]
    if in_stock:
        # Ensure 'stores_inventory' is numeric
        data['stores_inventory'] = pd.to_numeric(data['stores_inventory'], errors='coerce')
        data = data[data['stores_inventory'] > 0]
    if only_vintages:
        data = data[data['raw_lcbo_program'].str.contains(r"['\"]Vintages['\"]", regex=True, na=False)]
    if exclude_usa:
        data = data[data['raw_country_of_manufacture'] != 'United States']
    return data

# -------------------------------
# Favourites Handling
# -------------------------------
def load_favourites():
    """Load favourites from Supabase."""
    records = supabase_get_records(FAVOURITES_TABLE)
    return [record["URI"] for record in records if record.get("User ID") == "admin"]


def save_favourites(favourites):
    """Save favourites to Supabase."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    for uri in favourites:
        supabase_upsert_record(FAVOURITES_TABLE, {"URI": uri, "Date": today_str, "User ID": "admin"})
    # Reload favourites to ensure button state is updated
    st.session_state.favourites = load_favourites()
    st.success("Favourites saved successfully!")
    st.rerun()

def delete_favourites(favourites):
    """Remove favourites in Supabase."""
    for uri in favourites:
        supabase_delete_record(FAVOURITES_TABLE, uri, "admin")
    # Reload favourites to ensure button state is updated
    st.session_state.favourites = load_favourites()
    st.success("Favourites deleted successfully!")
    st.rerun()

def toggle_favourite(wine_id):
    """Toggle the favourite status of a wine."""
    # Load favourites filtered by the current user
    favourites = load_favourites()
    if wine_id in favourites:
        # Remove from favourites by filtering the table using the URI column
        delete_favourites([wine_id])
        st.success(f"Removed wine with URI '{wine_id}' from favourites.")
        st.rerun()
    else:
        # Add to favourites
        save_favourites([wine_id])
        st.success(f"Added wine with URI '{wine_id}' to favourites.")
        
    


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
def get_favourites_with_lowest_price():
    """Check if favourites are at their lowest price."""
    favourites = supabase_get_records(FAVOURITES_TABLE)
    products = supabase_get_records(PRODUCTS_TABLE)
    price_history = supabase_get_records("Price History") 

    lowest_price_items = []
    for fav in favourites:
        uri = fav["URI"]
        print(f"Checking favourite item with URI: {uri}")  # Debug print

        # Look up the current price in the Products table
        product = next((p for p in products if p["uri"] == uri), None)
        if not product:
            print(f"No product found for URI: {uri}")  # Debug print
            continue
        current_price = product.get("raw_ec_promo_price", "N/A")
        if current_price == "N/A":
            current_price = product.get("raw_ec_price", "N/A")
        if current_price == "N/A":
            print(f"No valid price found for product with URI: {uri}")  # Debug print
            continue

        # Look up the lowest price in the Price History table
        history = [entry for entry in price_history if entry["URI"] == uri]
        if not history:
            print(f"No price history found for URI: {uri}")  # Debug print
            continue
        lowest_price = min(entry["Price"] for entry in history)

        # Compare prices
        if float(current_price) == float(lowest_price):
            print(f"Item at lowest price: {product.get('title', 'Unknown')} (URI: {uri})")  # Debug print
            lowest_price_items.append({
                "Title": product.get("title", "Unknown"),  
                "URI": uri,
                "Current Price": current_price,
                "Lowest Price": lowest_price
            })
    print(f"Lowest price items found: {lowest_price_items}")  # Debug print
    return lowest_price_items

def send_email_with_lowest_prices(items):
    """Send an email with the list of favourite items at their lowest price using Postmark SMTP."""
    if not items:
        print("No items at their lowest price. Skipping email.")  # Debug print
        return

    print(f"Preparing to send email for items: {items}")  # Debug print

    # Postmark SMTP configuration
    smtp_server = "smtp-broadcasts.postmarkapp.com"
    smtp_port = 587
    smtp_username = "PM-B-broadcast-o5E13wA0FjsIeCQNnCbh3"
    smtp_password = "_PShFYnMnyik9CCoMZi7cog6W_oV8PjnxsK7"

    # Email configuration
    sender_email = "winefind@justemail.ca"  # Replace with your sender email
    receiver_email = "winefind@justemail.ca"  # Replace with your recipient email
    subject = "Favourites at Their Lowest Price"

    # Create the email content
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject

    html_content = "<h3>Favourites at Their Lowest Price</h3><table border='1'><tr><th>Title</th><th>URI</th><th>Current Price</th><th>Lowest Price</th></tr>"
    for item in items:
        html_content += f"<tr><td>{item['Title']}</td><td><a href='{item['URI']}'>{item['URI']}</a></td><td>{item['Current Price']}</td><td>{item['Lowest Price']}</td></tr>"
    html_content += "</table>"

    message.attach(MIMEText(html_content, "html"))

    # Send the email via Postmark SMTP
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        print("Email sent successfully!")  # Debug print
        st.success("Email sent successfully via Postmark SMTP!")
    except Exception as e:
        print(f"Failed to send email: {e}")  # Debug print
        st.error(f"Failed to send email via Postmark SMTP: {e}")

def background_update(df_products, today_str):
    """Perform additional background tasks like checking favourites and sending emails."""
    # Check favourites for lowest prices and send an email
    lowest_price_items = get_favourites_with_lowest_price()
    send_email_with_lowest_prices(lowest_price_items)
    st.info("Background update: Price history and email notifications completed.")

def refresh_data(store_id=None):
    """Refresh data and update Supabase."""
    current_time = datetime.now()
    today_str = current_time.strftime("%Y-%m-%d")
    # Check if today's data already exists in Supabase
    records = supabase_get_records(PRODUCTS_TABLE)

    url = "https://platform.cloud.coveo.com/rest/search/v2?organizationId=lcboproduction2kwygmc"
    headers = {
        "User-Agent": "your_user_agent",
        "Accept": "application/json",
        "Authorization": "Bearer xx883b5583-07fb-416b-874b-77cce565d927",
        "Content-Type": "application/json",
        "Referer": "https://www.lcbo.com/",
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
                'raw_ec_promo_price': raw_data.get('ec_promo_price', 'N/A'),
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

        # Create a temporary DataFrame for immediate display
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


        # Start background thread for updates
        def update_supabase():
            """Update the Products and Price History tables in Supabase."""
            for _, product in df_products.iterrows():
                product_data = product.to_dict()
                product_data["Date"] = today_str  # Add today's date

                # Update the Products table
                supabase_upsert_record(PRODUCTS_TABLE, product_data)

                # Determine the price to store in the Price History table
                price = product_data.get("raw_ec_promo_price", "N/A")
                if price == "N/A":
                    price = product_data.get("raw_ec_price", "N/A")

                # Update the Price History table if a valid price exists
                if price != "N/A":
                    price_history_data = {
                        "URI": product_data.get("uri", "N/A"),
                        "Title": product_data.get("title", "Unknown"),
                        "Date": today_str,
                        "Price": price
                    }
                    supabase_upsert_record("Price History", price_history_data)

        threading.Thread(target=update_supabase, daemon=True).start()
        threading.Thread(target=background_update(df_products, today_str), daemon=True).start()

        st.success("Data loaded! Background updates are in progress.")
        return df_products
    else:
        st.error("Failed to retrieve data from the API.")
        return None

# -------------------------------
# Main Streamlit App
# -------------------------------
def main():
    st.title("🍷 LCBO Wine Filter")
    # Add this line to clear the cached data
    st.cache_data.clear()

    # Sidebar Filters with improved header
    st.sidebar.header("Filter Options 🔍")

    # Authorization in the filters pane:
    if "authorized" not in st.session_state:
        st.session_state.authorized = False

    with st.sidebar.expander("Admin Authorization"):
        pin_input = st.text_input("Enter PIN", type="password", key="auth_pin")
        if st.button("Submit", key="auth_submit"):
            if pin_input == st.secrets["correct_pin"]:
                st.session_state.authorized = True
                st.sidebar.success("Authorization successful!")
            else:
                st.sidebar.error("Incorrect PIN. Please try again.")

    # Initialize session state for favourites and UI updates
    if "favourites" not in st.session_state:
        st.session_state.favourites = load_favourites()
    if "ui_updated" not in st.session_state:
        st.session_state.ui_updated = False

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

    # Refresh data if store selection changes:
    if selected_store != st.session_state.selected_store:
        st.session_state.selected_store = selected_store
        if selected_store != 'Select Store':
            store_id = store_ids.get(selected_store)
            data = refresh_data(store_id=store_id)
        else:
            data = load_products_from_supabase()
    else:
        data = load_products_from_supabase()

    search_text = st.sidebar.text_input("Search", value="")
    sort_by = st.sidebar.selectbox("Sort by", ['Sort by', '# of reviews', 'Rating', 'Top Veiwed - Year', 'Top Veiwed - Month', 'Top Seller - Year', 'Top Seller - Month'])

    # Create filter options from data
    food_items = load_food_items()
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
    only_sale_items = st.sidebar.checkbox("Only Sale Items", value=False)
    only_favourites = st.sidebar.checkbox("Only Favourites", value=False)

    # Load favourites from session state
    favourites = st.session_state.favourites
   
    # Apply Filters and Sorting
    filters = {
        'country': country,
        'region': region,
        'varietal': varietal,
        'exclude_usa': exclude_usa,
        'in_stock': in_stock,
        'only_vintages': only_vintages,
        'store': selected_store,
        'search_text': search_text
    }
    filtered_data = filter_and_sort_data(data, sort_by, **filters)

    # Apply "Only Sale Items" filter
    if only_sale_items:
        filtered_data = filtered_data[filtered_data['raw_ec_promo_price'].notna() & (filtered_data['raw_ec_promo_price'] != 'N/A')]

    # Apply "Only Favourites" filter
    if only_favourites:
        filtered_data = filtered_data[filtered_data['uri'].isin(favourites)]

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
        promo_price = row.get('raw_ec_promo_price', None)
        regular_price = row.get('raw_ec_price', 'N/A')

        # Use 'id' if it exists, otherwise fallback to 'title' or generate a unique identifier
        wine_id = row.get('uri', row['title'])  # Fallback to 'title' if 'id' is missing
        if not wine_id:
            wine_id = f"wine-{idx}"  # Generate a unique ID if both are missing

        # Favourite button
        is_favourite = wine_id in st.session_state.favourites  # Check the updated favourites list
        heart_icon = "❤️" if is_favourite else "🤍"
        if st.session_state.authorized:
            if st.button(f"{heart_icon} Favourite", key=f"fav-{wine_id}"):
                toggle_favourite(wine_id)
            if st.button(f"{heart_icon} Favourite", key=f"fav-{wine_id}"):
                toggle_favourite(wine_id)
                # Force a refresh of the app to update the button state
                st.rerun()
        else:
            st.markdown(f"{heart_icon} Favourite", unsafe_allow_html=True)

        # Raw SVG data for the sale icon
        sale_icon_svg = """
        <svg fill="#d00b0b" height="40px" width="40px" version="1.1" id="Layer_1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 455 455" xml:space="preserve" stroke="#d00b0b">
        <g id="SVGRepo_bgCarrier" stroke-width="0"></g>
        <g id="SVGRepo_tracerCarrier" stroke-linecap="round" stroke-linejoin="round"></g>
        <g id="SVGRepo_iconCarrier">
            <g>
                <polygon points="191.455,234.88 206.575,234.88 199.105,212.29"></polygon>
                <path d="M0,113.06V341.94h455V113.06H0z M160.991,249.685c-1.35,2.49-3.136,4.5-5.355,6.03c-2.221,1.53-4.77,2.641-7.65,3.33 c-2.88,0.689-5.85,1.035-8.91,1.035c-2.34,0-4.741-0.18-7.2-0.54c-2.461-0.36-4.86-0.885-7.2-1.575 c-2.34-0.689-4.605-1.515-6.795-2.475c-2.191-0.959-4.216-2.07-6.075-3.33l6.48-12.87c0.239,0.301,1.02,0.87,2.34,1.71 c1.319,0.841,2.955,1.68,4.905,2.52c1.949,0.841,4.125,1.59,6.525,2.25c2.399,0.661,4.829,0.99,7.29,0.99 c5.22,0,7.83-1.589,7.83-4.77c0-1.199-0.391-2.189-1.17-2.97c-0.78-0.779-1.86-1.485-3.24-2.115 c-1.381-0.63-3.015-1.215-4.905-1.755c-1.89-0.54-3.946-1.139-6.165-1.8c-2.94-0.9-5.49-1.875-7.65-2.925 c-2.16-1.049-3.946-2.264-5.355-3.645c-1.41-1.379-2.461-2.97-3.15-4.77c-0.69-1.8-1.035-3.899-1.035-6.3 c0-3.36,0.63-6.33,1.89-8.91c1.26-2.579,2.97-4.754,5.13-6.525c2.16-1.769,4.665-3.105,7.515-4.005 c2.849-0.9,5.864-1.35,9.045-1.35c2.219,0,4.41,0.211,6.57,0.63c2.16,0.42,4.23,0.96,6.21,1.62c1.98,0.661,3.825,1.411,5.535,2.25 c1.71,0.841,3.285,1.68,4.725,2.52l-6.48,12.24c-0.18-0.239-0.81-0.689-1.89-1.35c-1.08-0.66-2.43-1.35-4.05-2.07 c-1.62-0.72-3.391-1.35-5.31-1.89c-1.921-0.54-3.84-0.81-5.76-0.81c-5.281,0-7.92,1.771-7.92,5.31c0,1.08,0.284,1.98,0.855,2.7 c0.57,0.72,1.409,1.366,2.52,1.935c1.11,0.571,2.505,1.095,4.185,1.575c1.679,0.481,3.63,1.021,5.85,1.62 c3.06,0.841,5.819,1.755,8.28,2.745c2.459,0.99,4.545,2.221,6.255,3.69c1.71,1.471,3.029,3.255,3.96,5.355 c0.93,2.101,1.395,4.621,1.395,7.56C163.016,244.15,162.34,247.196,160.991,249.685z M213.955,259.36l-4.95-14.31h-19.89 l-4.86,14.31h-15.12l23.31-63.9h13.32l23.31,63.9H213.955z M285.595,259.36h-45.72v-63.9h14.76v50.94h30.96V259.36z M341.935,259.36h-44.91v-63.9h44.1v12.96h-29.34v12.42h25.2v11.97h-25.2v13.59h30.15V259.36z"></path>
            </g>
        </g>
        </svg>
        """

        if pd.notna(promo_price) and promo_price != 'N/A':
            # Display sale price with embedded SVG and strikethrough for regular price
            st.markdown(
                f"""<div style="font-size: 16px;"><strong>Price:</strong> <svg fill="#d00b0b" height="40px" width="40px" version="1.1" id="Layer_1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 455 455" xml:space="preserve" stroke="#d00b0b">
        <g id="SVGRepo_bgCarrier" stroke-width="0"></g>
        <g id="SVGRepo_tracerCarrier" stroke-linecap="round" stroke-linejoin="round"></g>
        <g id="SVGRepo_iconCarrier">
            <g>
                <polygon points="191.455,234.88 206.575,234.88 199.105,212.29"></polygon>
                <path d="M0,113.06V341.94h455V113.06H0z M160.991,249.685c-1.35,2.49-3.136,4.5-5.355,6.03c-2.221,1.53-4.77,2.641-7.65,3.33 c-2.88,0.689-5.85,1.035-8.91,1.035c-2.34,0-4.741-0.18-7.2-0.54c-2.461-0.36-4.86-0.885-7.2-1.575 c-2.34-0.689-4.605-1.515-6.795-2.475c-2.191-0.959-4.216-2.07-6.075-3.33l6.48-12.87c0.239,0.301,1.02,0.87,2.34,1.71 c1.319,0.841,2.955,1.68,4.905,2.52c1.949,0.841,4.125,1.59,6.525,2.25c2.399,0.661,4.829,0.99,7.29,0.99 c5.22,0,7.83-1.589,7.83-4.77c0-1.199-0.391-2.189-1.17-2.97c-0.78-0.779-1.86-1.485-3.24-2.115 c-1.381-0.63-3.015-1.215-4.905-1.755c-1.89-0.54-3.946-1.139-6.165-1.8c-2.94-0.9-5.49-1.875-7.65-2.925 c-2.16-1.049-3.946-2.264-5.355-3.645c-1.41-1.379-2.461-2.97-3.15-4.77c-0.69-1.8-1.035-3.899-1.035-6.3 c0-3.36,0.63-6.33,1.89-8.91c1.26-2.579,2.97-4.754,5.13-6.525c2.16-1.769,4.665-3.105,7.515-4.005 c2.849-0.9,5.864-1.35,9.045-1.35c2.219,0,4.41,0.211,6.57,0.63c2.16,0.42,4.23,0.96,6.21,1.62c1.98,0.661,3.825,1.411,5.535,2.25 c1.71,0.841,3.285,1.68,4.725,2.52l-6.48,12.24c-0.18-0.239-0.81-0.689-1.89-1.35c-1.08-0.66-2.43-1.35-4.05-2.07 c-1.62-0.72-3.391-1.35-5.31-1.89c-1.921-0.54-3.84-0.81-5.76-0.81c-5.281,0-7.92,1.771-7.92,5.31c0,1.08,0.284,1.98,0.855,2.7 c0.57,0.72,1.409,1.366,2.52,1.935c1.11,0.571,2.505,1.095,4.185,1.575c1.679,0.481,3.63,1.021,5.85,1.62 c3.06,0.841,5.819,1.755,8.28,2.745c2.459,0.99,4.545,2.221,6.255,3.69c1.71,1.471,3.029,3.255,3.96,5.355 c0.93,2.101,1.395,4.621,1.395,7.56C163.016,244.15,162.34,247.196,160.991,249.685z M213.955,259.36l-4.95-14.31h-19.89 l-4.86,14.31h-15.12l23.31-63.9h13.32l23.31,63.9H213.955z M285.595,259.36h-45.72v-63.9h14.76v50.94h30.96V259.36z M341.935,259.36h-44.91v-63.9h44.1v12.96h-29.34v12.42h25.2v11.97h-25.2v13.59h30.15V259.36z"></path>
            </g>
        </g>
        </svg>
                <strong>${promo_price}</strong> <span style="text-decoration: line-through; color: gray;">${regular_price}</span></div>""",
                unsafe_allow_html=True
            )
        else:
            # Display only the regular price
            st.markdown(
                f"""<div style="font-size: 16px;"><strong>Price:</strong> ${regular_price}</div>""",
                unsafe_allow_html=True
            )

        st.markdown(f"**Rating:** {row.get('raw_ec_rating', 'N/A')} | **Reviews:** {row.get('raw_avg_reviews', 'N/A')}")

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

    # Reset the UI update flag
    st.session_state.ui_updated = False

if __name__ == "__main__":
    main()
