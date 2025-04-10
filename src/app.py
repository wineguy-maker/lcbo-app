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
from pprint import pprint # Added for potential pretty-printing if needed

# --- Supabase Configuration ---
# Ensure these secrets are set in your Streamlit Cloud deployment
# Example structure in secrets.toml:
# [supabase]
# url = "YOUR_SUPABASE_URL"
# key = "YOUR_SUPABASE_SERVICE_ROLE_KEY"
#
# [api]
# token = "Bearer xxYOUR_API_KEY"
#
# correct_pin = "YOUR_ADMIN_PIN"

try:
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_SERVICE_ROLE_KEY = st.secrets["supabase"]["key"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
except KeyError as e:
    st.error(f"Missing Supabase secret: {e}. Please check Streamlit Cloud secrets.")
    st.stop() # Stop execution if Supabase cannot be configured
except Exception as e:
    st.error(f"Error initializing Supabase client: {e}")
    st.stop()

# Define Table Names
PRODUCTS_TABLE = "Products"
FAVOURITES_TABLE = "Favourites"
PRICE_HISTORY_TABLE = "Price History"

# -------------------------------
# Supabase Helper Functions
# -------------------------------
def supabase_get_records(table_name):
    """Fetch all records from a Supabase table."""
    try:
        response = supabase.table(table_name).select("*").execute()
        if hasattr(response, 'error') and response.error:
             st.error(f"Supabase error fetching from {table_name}: {response.error}")
             return []
        return response.data
    except Exception as e:
        st.error(f"Failed to fetch records from {table_name}: {e}")
        return []

def supabase_upsert_record(table_name, record):
    """Insert or update a record(s) in a Supabase table."""
    try:
        response = supabase.table(table_name).upsert(record).execute()
        if hasattr(response, 'error') and response.error:
             st.error(f"Supabase error upserting to {table_name}: {response.error}")
             return None
        return response.data
    except Exception as e:
        st.error(f"Failed to upsert record in {table_name}: {e}")
        return None

def supabase_delete_record(table_name, URI, user_id):
    """Delete a record from a Supabase table based on URI and User ID."""
    try:
        response = (
            supabase.table(table_name)
            .delete()
            .eq("URI", URI)        # Filter by URI
            .eq("User ID", user_id)  # Filter by User ID
            .execute()
        )
        if hasattr(response, 'error') and response.error:
             st.error(f"Supabase error deleting from {table_name}: {response.error}")
             return None
        return response.data
    except Exception as e:
        st.error(f"Failed to delete record from {table_name}: {e}")
        return None

def load_products_from_supabase():
    """Load products from the Supabase Products table."""
    records = supabase_get_records(PRODUCTS_TABLE)
    if records:
        return pd.DataFrame(records)
    else:
        st.warning("No products found in Supabase table. Please refresh data.")
        # Return an empty DataFrame with expected columns if fetch fails or returns empty
        return pd.DataFrame(columns=['title', 'uri', 'raw_ec_rating', 'raw_avg_reviews', 'weighted_rating', 'raw_ec_price', 'raw_ec_promo_price', 'raw_country_of_manufacture', 'raw_lcbo_region_name', 'raw_lcbo_varietal_name', 'store_name', 'stores_inventory', 'raw_lcbo_program'])


# -------------------------------
# Data Handling (Local CSV - Keep if needed)
# -------------------------------
@st.cache_data # Caching might be less relevant if always loading from DB/API
def load_data(file_path):
    try:
        df = pd.read_csv(file_path)
        return df
    except FileNotFoundError:
        st.error(f"Error: File not found at {file_path}.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading data from {file_path}: {e}")
        return pd.DataFrame()

def load_food_items():
    try:
        food_items = pd.read_csv('food_items.csv') # Ensure this file is deployed with your app
        return food_items
    except Exception as e:
        st.error(f"Error loading food items: {e}")
        return pd.DataFrame(columns=['Category', 'FoodItem'])

# -------------------------------
# Filter functions
# -------------------------------
def search_data(data, search_text):
    """Filter data based on search text in the 'title' column."""
    if search_text and 'title' in data.columns:
        try:
            # Ensure title column is string before using .str accessor
            return data[data['title'].astype(str).str.contains(search_text, case=False, na=False)]
        except Exception as e:
             st.warning(f"Error during search: {e}")
             return data # Return original data on search error
    return data

def sort_data_filter(data, sort_by):
    """Sort data based on the selected criteria, with weighted rating as the default."""
    df_sorted = data.copy() # Work on a copy
    ascending = True # Default ascending for ranks
    sort_column = None

    if sort_by == '# of reviews':
        sort_column = 'raw_avg_reviews'
        ascending = False
    elif sort_by == 'Rating':
        sort_column = 'raw_ec_rating'
        ascending = False
    elif sort_by == 'Top Viewed - Year':
        sort_column = 'raw_view_rank_yearly'
    elif sort_by == 'Top Viewed - Month':
        sort_column = 'raw_view_rank_monthly'
    elif sort_by == 'Top Seller - Year':
        sort_column = 'raw_sell_rank_yearly'
    elif sort_by == 'Top Seller - Month':
        sort_column = 'raw_sell_rank_monthly'
    else: # Default to weighted rating if 'Sort by' or invalid option selected
        sort_column = 'weighted_rating'
        ascending = False

    if sort_column and sort_column in df_sorted.columns:
        # Ensure numeric type for sorting where applicable
        if sort_column in ['raw_avg_reviews', 'raw_ec_rating', 'weighted_rating',
                           'raw_view_rank_yearly', 'raw_view_rank_monthly',
                           'raw_sell_rank_yearly', 'raw_sell_rank_monthly']:
             # Coerce to numeric, making non-numeric NaN
             df_sorted[sort_column] = pd.to_numeric(df_sorted[sort_column], errors='coerce')

        try:
             return df_sorted.sort_values(by=sort_column, ascending=ascending, na_position='last')
        except Exception as e:
             st.warning(f"Could not sort by {sort_column}: {e}. Returning unsorted.")
             return data # Return original data on sort error
    elif sort_by != 'Sort by':
         st.warning(f"Could not sort by selected option '{sort_by}'.")
         return data # Return original data if specified sort column doesn't exist
    else:
         # Default sort by weighted_rating if 'Sort by' is chosen and column exists
         if 'weighted_rating' in df_sorted.columns:
             df_sorted['weighted_rating'] = pd.to_numeric(df_sorted['weighted_rating'], errors='coerce')
             return df_sorted.sort_values(by='weighted_rating', ascending=False, na_position='last')
         else:
             return data # Return original if default sort column missing


def filter_data(data, country='All Countries', region='All Regions', varietal='All Varietals', exclude_usa=False, in_stock=False, only_vintages=False, store='Select Store'):
    """Apply various filters to the data. Expects specific keyword arguments."""
    df = data.copy()
    try:
        if country != 'All Countries' and 'raw_country_of_manufacture' in df.columns:
            df = df[df['raw_country_of_manufacture'] == country]
        if region != 'All Regions' and 'raw_lcbo_region_name' in df.columns:
            df = df[df['raw_lcbo_region_name'] == region]
        if varietal != 'All Varietals' and 'raw_lcbo_varietal_name' in df.columns:
            df = df[df['raw_lcbo_varietal_name'] == varietal]
        # Store filtering might depend on how 'store_name' is populated (usually after API call)
        if store != 'Select Store' and 'store_name' in df.columns:
             df = df[df['store_name'] == store]

        if in_stock and 'stores_inventory' in df.columns:
             df['stores_inventory'] = pd.to_numeric(df['stores_inventory'], errors='coerce').fillna(0)
             df = df[df['stores_inventory'] > 0]

        if only_vintages and 'raw_lcbo_program' in df.columns:
             df = df[df['raw_lcbo_program'].astype(str).str.contains(r"['\"]Vintages['\"]", regex=True, na=False)]

        if exclude_usa and 'raw_country_of_manufacture' in df.columns:
            df = df[df['raw_country_of_manufacture'] != 'United States']
    except Exception as e:
        st.error(f"Error during filtering step: {e}")
        return data # Return original data on error
    return df


# --- THIS IS THE CORRECTED VERSION OF filter_and_sort_data ---
def filter_and_sort_data(data, sort_by, **filters):
    """Combine filtering and sorting."""
    if data is None or data.empty:
        return pd.DataFrame() # Return empty if no input data

    # 1. Create a dictionary containing only the arguments meant for filter_data
    filter_data_args = {
        'country': filters.get('country', 'All Countries'),
        'region': filters.get('region', 'All Regions'),
        'varietal': filters.get('varietal', 'All Varietals'),
        'exclude_usa': filters.get('exclude_usa', False),
        'in_stock': filters.get('in_stock', False),
        'only_vintages': filters.get('only_vintages', False),
        'store': filters.get('store', 'Select Store')
        # Note: 'search_text' is deliberately excluded here
    }

    # 2. Apply primary filters using only the specific arguments filter_data expects
    data = filter_data(data, **filter_data_args)

    # 3. Apply search filter separately using the dedicated search_data function
    search_text = filters.get('search_text', '') # Get search_text from the original filters dict
    data = search_data(data, search_text)

    # 4. Apply sorting
    data = sort_data_filter(data, sort_by)
    return data
# --- END OF CORRECTED FUNCTION ---


# -------------------------------
# Favourites Handling
# -------------------------------
def load_favourites():
    """Load favourites URIs for the hardcoded 'admin' user from Supabase."""
    user_id_to_load = "admin" # Hardcoded user ID
    try:
        response = supabase.table(FAVOURITES_TABLE).select("URI").eq("User ID", user_id_to_load).execute()
        if hasattr(response, 'error') and response.error:
             st.error(f"Supabase error loading favourites: {response.error}")
             return []
        return [record["URI"] for record in response.data]
    except Exception as e:
        st.error(f"Error loading favourites: {e}")
        return []


def save_favourites(favourites_to_add):
    """Save a list of favourite URIs to Supabase for the 'admin' user."""
    user_id_to_save = "admin" # Hardcoded user ID
    today_str = datetime.now().strftime("%Y-%m-%d")
    records_to_upsert = []
    for uri in favourites_to_add:
        records_to_upsert.append({"URI": uri, "Date": today_str, "User ID": user_id_to_save})

    if records_to_upsert:
        try:
            # Upsert the records
            response = supabase.table(FAVOURITES_TABLE).upsert(records_to_upsert).execute()
            if hasattr(response, 'error') and response.error:
                 st.error(f"Supabase error saving favourites: {response.error}")
            else:
                 st.success("Favourites saved successfully!")
                 # Reload favourites into session state after saving
                 st.session_state.favourites = load_favourites()
                 st.rerun() # Rerun to update UI immediately
        except Exception as e:
             st.error(f"Error saving favourites: {e}")


def delete_favourites(favourites_to_delete):
    """Remove a list of favourite URIs from Supabase for the 'admin' user."""
    user_id_to_delete = "admin" # Hardcoded user ID
    success = True
    for uri in favourites_to_delete:
        deleted_data = supabase_delete_record(FAVOURITES_TABLE, uri, user_id_to_delete)
        if deleted_data is None:
             success = False # supabase_delete_record already showed an error

    if success and favourites_to_delete: # Only show success if deletion was attempted and successful
        st.success("Favourites deleted successfully!")
        # Reload favourites into session state after deleting
        st.session_state.favourites = load_favourites()
        st.rerun()


def toggle_favourite(wine_uri):
    """Toggle the favourite status of a wine for the 'admin' user."""
    current_favourites = load_favourites()

    if wine_uri in current_favourites:
        delete_favourites([wine_uri]) # Pass as a list
    else:
        save_favourites([wine_uri]) # Pass as a list
    # Rerun is handled by save/delete functions now


# -------------------------------
# Helper: Transform Image URL
# -------------------------------
def transform_image_url(url, new_size):
    """Replace image size pattern in URL. Handles png, jpg, jpeg (case-insensitive)."""
    if not isinstance(url, str):
        return url
    try:
        # Regex finds digits.digits.extension at the end, case-insensitive
        return re.sub(r"\d+\.\d+\.(png|jpg|jpeg)$", new_size, url, flags=re.IGNORECASE)
    except Exception:
         return url # Return original URL if regex fails


# -------------------------------
# Background Tasks / Email Logic
# -------------------------------
def get_favourites_with_lowest_price():
    """Check if favourites are at their lowest recorded price."""
    st.info("Checking favourites for lowest prices...")
    favourite_uris = load_favourites()
    if not favourite_uris:
        st.info("No favourites found for user 'admin'.")
        return []

    all_products = supabase_get_records(PRODUCTS_TABLE)
    if not all_products:
        st.warning("Could not load product data to check prices.")
        return []
    products_df = pd.DataFrame(all_products)
    products_df = products_df[products_df['uri'].isin(favourite_uris)]
    if products_df.empty:
         st.info("No product data found for the favourited items.")
         return []

    price_history = supabase_get_records(PRICE_HISTORY_TABLE)
    if not price_history:
        st.warning("Could not load price history data.")
        return []
    price_history_df = pd.DataFrame(price_history)
    price_history_df = price_history_df[price_history_df['URI'].isin(favourite_uris)]

    lowest_price_items = []

    if not price_history_df.empty:
         price_history_df['Price'] = pd.to_numeric(price_history_df['Price'], errors='coerce')
         # Find the index of the minimum price for each URI, then select those rows
         lowest_prices = price_history_df.loc[price_history_df.groupby('URI')['Price'].idxmin()]
    else:
         lowest_prices = pd.DataFrame(columns=['URI', 'Price'])

    for _, product in products_df.iterrows():
        uri = product.get("uri")
        if not uri: continue

        current_price_str = product.get("raw_ec_promo_price")
        if pd.isna(current_price_str) or str(current_price_str).strip() == '' or str(current_price_str).strip().upper() == 'N/A':
             current_price_str = product.get("raw_ec_price")

        current_price_numeric = pd.to_numeric(current_price_str, errors='coerce')
        if pd.isna(current_price_numeric):
            # st.warning(f"Skipping {product.get('title', uri)}: Invalid current price ('{current_price_str}')") # Reduce noise
            continue

        lowest_entry = lowest_prices[lowest_prices['URI'] == uri]

        if not lowest_entry.empty:
            lowest_price_numeric = lowest_entry['Price'].iloc[0]
            if pd.isna(lowest_price_numeric): continue # Skip if lowest historical is invalid

            # Compare prices (using <= to include matching lowest price)
            if current_price_numeric <= lowest_price_numeric:
                lowest_price_items.append({
                    "Title": product.get("title", "Unknown Title"),
                    "URI": uri,
                    "Current Price": f"${current_price_numeric:.2f}",
                    "Lowest Price": f"${lowest_price_numeric:.2f}"
                })

    st.info(f"Found {len(lowest_price_items)} favourites at their lowest price.")
    return lowest_price_items


# --- THIS IS THE REVERTED VERSION using hardcoded SMTP details ---
def send_email_with_lowest_prices(items):
    """Send an email with the list of favourite items at their lowest price using hardcoded SMTP details."""
    if not items:
        st.info("No items at lowest price to report. Email not sent.")
        return

    # --- Using Hardcoded Credentials ---
    # WARNING: Hardcoding credentials is a security risk. Consider using st.secrets.
    smtp_server = "smtp-broadcasts.postmarkapp.com"
    smtp_port = 587
    smtp_username = "PM-B-broadcast-o5E13wA0FjsIeCQNnCbh3" # Hardcoded username
    smtp_password = "_PShFYnMnyik9CCoMZi7cog6W_oV8PjnxsK7" # Hardcoded password
    sender_email = "winefind@justemail.ca"  # Hardcoded sender
    receiver_email = "winefind@justemail.ca"  # Hardcoded recipient
    # --- End Hardcoded Credentials ---

    subject = "Favourites at Their Lowest Price Alert!"
    message = MIMEMultipart("alternative")
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject

    text_content = "Favourites at Their Lowest Price:\n\n"
    for item in items: text_content += f"- Title: {item['Title']}\n  URI: {item['URI']}\n  Current Price: {item['Current Price']}\n  Lowest Recorded Price: {item['Lowest Price']}\n\n"

    html_content = "<html><head></head><body><h3>Favourites at Their Lowest Price</h3><table border='1' style='border-collapse: collapse; width: 100%;'><thead><tr style='background-color: #f2f2f2;'><th style='padding: 8px; text-align: left;'>Title</th><th style='padding: 8px; text-align: left;'>URI</th><th style='padding: 8px; text-align: right;'>Current Price</th><th style='padding: 8px; text-align: right;'>Lowest Recorded</th></tr></thead><tbody>"
    for item in items:
        title_safe = item['Title'].replace('<', '&lt;').replace('>', '&gt;')
        uri_safe = item['URI'].replace('<', '&lt;').replace('>', '&gt;')
        current_price_safe = item['Current Price'].replace('<', '&lt;').replace('>', '&gt;')
        lowest_price_safe = item['Lowest Price'].replace('<', '&lt;').replace('>', '&gt;')
        html_content += f"<tr><td style='padding: 8px;'>{title_safe}</td><td style='padding: 8px;'><a href='{uri_safe}'>{uri_safe}</a></td><td style='padding: 8px; text-align: right;'>{current_price_safe}</td><td style='padding: 8px; text-align: right;'>{lowest_price_safe}</td></tr>"
    html_content += "</tbody></table></body></html>"

    message.attach(MIMEText(text_content, "plain"))
    message.attach(MIMEText(html_content, "html"))

    try:
        st.info(f"Attempting to send email via {smtp_server}:{smtp_port}...")
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_username, smtp_password) # Uses hardcoded vars
            server.sendmail(sender_email, receiver_email, message.as_string())
        st.success("Email sent successfully!")
    except smtplib.SMTPAuthenticationError:
         st.error("SMTP Authentication Error: Incorrect username or password (using hardcoded values).")
    except smtplib.SMTPConnectError:
         st.error(f"SMTP Connection Error: Failed to connect to {smtp_server}:{smtp_port}.")
    except Exception as e:
        st.error(f"Failed to send email: {e}")
# --- End of reverted function ---


def background_update(products_list, today_str):
    """Perform table updates and price history processing in the background."""
    st.info("Background update started...")
    # 1. Upsert Product Data
    records_to_upsert = []
    for product in products_list:
        product_record = product.copy()
        product_record["Date"] = today_str # Add update date
        # Ensure primary key ('uri'?) is present and matches table schema
        if 'uri' not in product_record or pd.isna(product_record['uri']): continue # Skip if no URI
        records_to_upsert.append(product_record)

    if records_to_upsert:
         st.info(f"Upserting {len(records_to_upsert)} products to Supabase...")
         batch_size = 400 # Slightly smaller batch size might be safer
         for i in range(0, len(records_to_upsert), batch_size):
             batch = records_to_upsert[i:i + batch_size]
             upsert_result = supabase_upsert_record(PRODUCTS_TABLE, batch)
             if upsert_result is None: st.warning(f"Failed to upsert product batch starting at index {i}.")
         st.info("Background update: Products table upsert completed.")

    # 2. Update Price History
    price_history_records = []
    for product in products_list:
         uri = product.get('uri')
         price_str = product.get("raw_ec_promo_price")
         if pd.isna(price_str) or str(price_str).strip() == '' or str(price_str).strip().upper() == 'N/A':
              price_str = product.get("raw_ec_price")
         price_numeric = pd.to_numeric(price_str, errors='coerce')

         if uri and not pd.isna(price_numeric):
              price_history_records.append({"URI": uri, "Price": price_numeric, "Date": today_str})

    if price_history_records:
         st.info(f"Adding {len(price_history_records)} price history records...")
         # Using upsert with ('URI', 'Date') primary key assumed
         response = supabase.table(PRICE_HISTORY_TABLE).upsert(price_history_records).execute()
         if hasattr(response, 'error') and response.error: st.error(f"Supabase error saving price history: {response.error}")
         else: st.info("Background update: Price history saved.")

    # 3. Check favourites for lowest prices and send email
    lowest_price_items = get_favourites_with_lowest_price()
    send_email_with_lowest_prices(lowest_price_items)

    st.info("Background update finished.")


# -------------------------------
# Refresh function (API Fetching and Processing)
# -------------------------------
def refresh_data(store_id=None):
    """Fetch fresh data from API, calculate weighted ratings, and initiate background update."""
    current_time = datetime.now()
    today_str = current_time.strftime("%Y-%m-%d")

    st.info("Refreshing data from LCBO API...")
    url = "https://platform.cloud.coveo.com/rest/search/v2?organizationId=lcboproduction2kwygmc"
    try:
         api_token = st.secrets["api"]["token"]
    except KeyError:
         st.error("API Authorization Token not found in secrets. Please set secrets['api']['token']")
         return None
    except Exception as e:
         st.error(f"Error accessing API token secret: {e}")
         return None

    headers = { "User-Agent": "Mozilla/5.0 StreamlitApp/1.1", "Accept": "application/json", "Authorization": api_token, "Content-Type": "application/json", "Referer": "https://www.lcbo.com/" }
    base_payload = { "q": "", "tab": "clp-products-wine-red_wine", "sort": "ec_rating descending", "facets": [{"field": "ec_rating","currentValues": [{"value": "4..5inc", "state": "selected"}]}],"numberOfResults": 500, "firstResult": 0, "aq": '@ec_visibility==(2,4) @ec_category=="Products|Wine|Red Wine"'}
    dictionaryFieldContext = {}
    if store_id:
        dictionaryFieldContext = { "stores_inventory": store_id, "stores_stock_combined": store_id, "stores_low_stock_combined": store_id }
        base_payload["dictionaryFieldContext"] = dictionaryFieldContext

    def get_items(payload):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
             st.error(f"API request failed: {e}")
             return None
        except Exception as e:
             st.error(f"Error processing API response: {e}")
             return None

    st.info("Fetching initial batch from API...")
    initial_data = get_items(base_payload)
    if not (initial_data and 'results' in initial_data):
         st.error("Failed to retrieve initial data from the API.")
         st.error(f"API Response: {initial_data}")
         return None # Return None if initial fetch fails

    all_items = initial_data['results']
    total_count = initial_data.get('totalCount', 0)
    st.info(f"API reported total count: {total_count}")
    num_requests = (total_count // 500) + (1 if total_count % 500 != 0 else 0)
    st.info(f"Fetching {num_requests} batches...")
    progress_bar = st.progress(0)

    for i in range(1, num_requests):
        current_payload = base_payload.copy()
        current_payload["firstResult"] = i * 500
        if dictionaryFieldContext: current_payload["dictionaryFieldContext"] = dictionaryFieldContext
        paged_data = get_items(current_payload)
        if paged_data and 'results' in paged_data: all_items.extend(paged_data['results'])
        else: st.warning(f"No 'results' in response for batch {i+1}, stopping pagination."); break
        progress = int(((i + 1) / num_requests) * 100); progress_bar.progress(progress)
        time.sleep(0.5)
    progress_bar.empty()
    st.info(f"Total items fetched: {len(all_items)}")

    # --- START: Weighted Rating Calculation (Adopted from Old Code Logic) ---
    temp_df = pd.DataFrame([{'raw_ec_rating': item['raw'].get('ec_rating'), 'raw_avg_reviews': item['raw'].get('avg_reviews')} for item in all_items])
    temp_df['numeric_rating'] = pd.to_numeric(temp_df['raw_ec_rating'], errors='coerce')
    temp_df['numeric_reviews'] = pd.to_numeric(temp_df['raw_avg_reviews'], errors='coerce')
    valid_reviewed_items = temp_df.dropna(subset=['numeric_reviews', 'numeric_rating'])
    valid_reviewed_items = valid_reviewed_items[valid_reviewed_items['numeric_reviews'] > 0]
    mean_rating = valid_reviewed_items['numeric_rating'].mean()
    if pd.isna(mean_rating): mean_rating = temp_df['numeric_rating'].mean(); mean_rating = 0.0 if pd.isna(mean_rating) else mean_rating
    minimum_votes = 10 # Fixed value
    st.info(f"Calculated mean_rating (C) for weighted score: {mean_rating:.4f}")
    st.info(f"Using fixed minimum_votes (m) for weighted score: {minimum_votes}")

    def weighted_rating(rating, votes, min_votes, avg_rating):
        try:
            rating = float(rating) if pd.notna(rating) else 0.0
            votes = float(votes) if pd.notna(votes) else 0.0
            min_votes = float(min_votes); avg_rating = float(avg_rating)
        except (ValueError, TypeError): return 0.0
        denominator = votes + min_votes
        if denominator == 0: return 0.0
        return (votes / denominator * rating) + (min_votes / denominator * avg_rating)

    products_list_for_update = []
    for product_api_item in all_items:
        raw_data = product_api_item['raw']
        rating_val = raw_data.get('ec_rating'); votes_val = raw_data.get('avg_reviews')
        product_info = {
            'title': product_api_item.get('title', 'N/A'), 'uri': product_api_item.get('uri', 'N/A'),
            'raw_ec_thumbnails': raw_data.get('ec_thumbnails', 'N/A'), 'raw_ec_shortdesc': raw_data.get('ec_shortdesc', 'N/A'),
            'raw_lcbo_tastingnotes': raw_data.get('lcbo_tastingnotes', 'N/A'), 'raw_lcbo_region_name': raw_data.get('lcbo_region_name', 'N/A'),
            'raw_country_of_manufacture': raw_data.get('country_of_manufacture', 'N/A'), 'raw_lcbo_program': raw_data.get('lcbo_program', 'N/A'),
            'raw_created_at': raw_data.get('created_at', 'N/A'), 'raw_is_buyable': raw_data.get('is_buyable', 'N/A'),
            'raw_ec_price': raw_data.get('ec_price', 'N/A'), 'raw_ec_final_price': raw_data.get('ec_final_price', 'N/A'),
            'raw_ec_promo_price': raw_data.get('ec_promo_price', 'N/A'), 'raw_lcbo_unit_volume': raw_data.get('lcbo_unit_volume', 'N/A'),
            'raw_lcbo_alcohol_percent': raw_data.get('lcbo_alcohol_percent', 'N/A'), 'raw_lcbo_sugar_gm_per_ltr': raw_data.get('lcbo_sugar_gm_per_ltr', 'N/A'),
            'raw_lcbo_bottles_per_pack': raw_data.get('lcbo_bottles_per_pack', 'N/A'), 'raw_sysconcepts': raw_data.get('sysconcepts', 'N/A'),
            'raw_ec_category': raw_data.get('ec_category', 'N/A'), 'raw_ec_category_filter': raw_data.get('ec_category_filter', 'N/A'),
            'raw_lcbo_varietal_name': raw_data.get('lcbo_varietal_name', 'N/A'), 'raw_stores_stock': raw_data.get('stores_stock', 'N/A'),
            'raw_stores_stock_combined': raw_data.get('stores_stock_combined', 'N/A'), 'raw_stores_low_stock_combined': raw_data.get('stores_low_stock_combined', 'N/A'),
            'raw_stores_low_stock': raw_data.get('stores_low_stock', 'N/A'), 'raw_out_of_stock': raw_data.get('out_of_stock', 'N/A'),
            'stores_inventory': raw_data.get('stores_inventory', 0), 'raw_online_inventory': raw_data.get('online_inventory', 0),
            'raw_avg_reviews': votes_val, 'raw_ec_rating': rating_val,
            'weighted_rating': weighted_rating(rating_val, votes_val, minimum_votes, mean_rating), # Apply calculation
            'raw_view_rank_yearly': raw_data.get('view_rank_yearly', 'N/A'), 'raw_view_rank_monthly': raw_data.get('view_rank_monthly', 'N/A'),
            'raw_sell_rank_yearly': raw_data.get('sell_rank_yearly', 'N/A'), 'raw_sell_rank_monthly': raw_data.get('sell_rank_monthly', 'N/A')
        }
        if store_id and st.session_state.selected_store != 'Select Store': product_info['store_name'] = st.session_state.selected_store
        else: product_info['store_name'] = None
        products_list_for_update.append(product_info)
    # --- END: Weighted Rating Calculation ---

    df_products_display = pd.DataFrame(products_list_for_update)
    st.info("Starting background thread for database updates and price checks...")
    thread = threading.Thread(target=background_update, args=(products_list_for_update, today_str), daemon=True)
    thread.start()
    st.success("API data fetched! Displaying current data while background updates run.")
    return df_products_display


# -------------------------------
# Main Streamlit App
# -------------------------------
def main():
    st.set_page_config(layout="wide")
    st.title("🍷 LCBO Wine Filter & Favourite Tracker")

    # Authorization
    if "authorized" not in st.session_state: st.session_state.authorized = False
    with st.sidebar.expander("Admin Authorization", expanded=not st.session_state.authorized):
        pin_input = st.text_input("Enter PIN", type="password", key="auth_pin")
        if st.button("Login", key="auth_submit"):
            correct_pin = st.secrets.get("correct_pin", None)
            if correct_pin and pin_input == correct_pin: st.session_state.authorized = True; st.rerun()
            else: st.sidebar.error("Incorrect PIN.")

    # Session State Init
    if "favourites" not in st.session_state:
        st.session_state.favourites = load_favourites() if st.session_state.authorized else []
    if 'selected_store' not in st.session_state: st.session_state.selected_store = 'Select Store'
    if 'data' not in st.session_state: st.session_state.data = pd.DataFrame()

    # Sidebar Filters
    st.sidebar.header("Filter Options 🔍")
    store_options = ['Select Store', 'Bradford', 'E. Gwillimbury', 'Upper Canada', 'Yonge & Eg', 'Dufferin & Steeles']
    store_ids = { "Bradford": "145", "E. Gwillimbury": "391", "Upper Canada": "226", "Yonge & Eg": "457", "Dufferin & Steeles": "618" }
    selected_store = st.sidebar.selectbox("Select Store", options=store_options, key="store_selector", index=store_options.index(st.session_state.selected_store)) # Persist selection

    # Data Loading / Refresh Logic
    needs_refresh = False
    if selected_store != st.session_state.selected_store:
        st.info(f"Store changed to {selected_store}. Triggering data refresh.")
        st.session_state.selected_store = selected_store
        needs_refresh = True
    if st.sidebar.button("Refresh Data from API", key="manual_refresh"):
         needs_refresh = True; st.info("Manual refresh requested.")

    if needs_refresh:
        store_id_to_pass = store_ids.get(selected_store) if selected_store != 'Select Store' else None
        with st.spinner("Fetching fresh data from API... Please wait."): refreshed_data = refresh_data(store_id=store_id_to_pass)
        if refreshed_data is not None and not refreshed_data.empty: st.session_state.data = refreshed_data; st.success("Data refresh complete.")
        elif refreshed_data is not None and refreshed_data.empty: st.session_state.data = refreshed_data; st.warning("API returned no data for selection.") # Handle empty results
        else: st.error("Data refresh failed. Loading potentially stale data from database."); st.session_state.data = load_products_from_supabase()
    else:
        if st.session_state.data.empty: st.info("Loading initial data from database..."); st.session_state.data = load_products_from_supabase()
        if st.session_state.data.empty: st.warning("No data loaded. Please select a store or refresh.")

    data_to_display = st.session_state.data

    # Continue with sidebar filters
    search_text = st.sidebar.text_input("Search Title", value="")
    sort_by = st.sidebar.selectbox("Sort by", ['Sort by', '# of reviews', 'Rating', 'Top Viewed - Year', 'Top Viewed - Month', 'Top Seller - Year', 'Top Seller - Month'])
    if not data_to_display.empty:
         country_options = ['All Countries'] + sorted(data_to_display['raw_country_of_manufacture'].dropna().unique().tolist())
         region_options = ['All Regions'] + sorted(data_to_display['raw_lcbo_region_name'].dropna().unique().tolist())
         varietal_options = ['All Varietals'] + sorted(data_to_display['raw_lcbo_varietal_name'].dropna().unique().tolist())
    else: country_options, region_options, varietal_options = ['All Countries'], ['All Regions'], ['All Varietals']
    food_items = load_food_items()
    categories = food_items['Category'].unique() if not food_items.empty else []
    food_options = ['All Dishes'] + sorted(categories.tolist())
    country = st.sidebar.selectbox("Country", options=country_options)
    region = st.sidebar.selectbox("Region", options=region_options)
    varietal = st.sidebar.selectbox("Varietal", options=varietal_options)
    food_category = st.sidebar.selectbox("Food Category", options=food_options)
    exclude_usa = st.sidebar.checkbox("Exclude USA", value=False)
    in_stock = st.sidebar.checkbox("In Stock Only (Selected Store)", value=False)
    only_vintages = st.sidebar.checkbox("Only Vintages", value=False)
    only_sale_items = st.sidebar.checkbox("Only Sale Items", value=False)
    only_favourites = st.sidebar.checkbox("Only My Favourites", value=False) if st.session_state.authorized else False

    # Apply Filters and Sorting
    if not data_to_display.empty:
        filters = {'country': country, 'region': region, 'varietal': varietal, 'exclude_usa': exclude_usa, 'in_stock': in_stock, 'only_vintages': only_vintages, 'store': selected_store, 'search_text': search_text}
        filtered_data = filter_and_sort_data(data_to_display, sort_by, **filters) # This now calls the corrected version

        # Post-filtering steps
        if only_sale_items and 'raw_ec_promo_price' in filtered_data.columns:
            filtered_data['promo_price_numeric'] = pd.to_numeric(filtered_data['raw_ec_promo_price'], errors='coerce')
            filtered_data = filtered_data[filtered_data['promo_price_numeric'].notna() & (filtered_data['promo_price_numeric'] > 0)]
            filtered_data = filtered_data.drop(columns=['promo_price_numeric'])
        if only_favourites and st.session_state.authorized and 'uri' in filtered_data.columns:
             current_favs = st.session_state.favourites
             filtered_data = filtered_data[filtered_data['uri'].isin(current_favs)]
        if food_category != 'All Dishes' and not food_items.empty and 'raw_sysconcepts' in filtered_data.columns:
            selected_food_items = food_items[food_items['Category'] == food_category]['FoodItem'].str.lower().tolist()
            def check_food_match(sysconcepts_str):
                 if pd.isna(sysconcepts_str): return False
                 text_to_check = str(sysconcepts_str).lower()
                 return any(item in text_to_check for item in selected_food_items)
            filtered_data = filtered_data[filtered_data['raw_sysconcepts'].apply(check_food_match)]
        st.write(f"Showing **{len(filtered_data)}** products")
    else: filtered_data = pd.DataFrame(); st.write("No product data loaded.")

    # Display Products with Pagination
    if not filtered_data.empty:
        page_size = 10
        total_products = len(filtered_data)
        total_pages = (total_products // page_size) + (1 if total_products % page_size > 0 else 0)
        if total_pages > 0: page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1, key="pagination")
        else: page = 1
        start_idx = (page - 1) * page_size; end_idx = start_idx + page_size
        page_data = filtered_data.iloc[start_idx:end_idx]

        for idx, row in page_data.iterrows():
            col1, col2 = st.columns([1, 3])
            with col1:
                thumbnail_url = row.get('raw_ec_thumbnails');
                if pd.notna(thumbnail_url): st.image(thumbnail_url, width=150)
                else: st.caption("No image")
                with st.popover("Enlarge"): large_image_url = transform_image_url(thumbnail_url, "2048.2048.png"); st.image(large_image_url or thumbnail_url, use_container_width=True)
                wine_uri = row.get('uri')
                if wine_uri:
                    is_favourite = wine_uri in st.session_state.favourites; heart_icon = "❤️" if is_favourite else "🤍"
                    if st.session_state.authorized:
                        if st.button(f"{heart_icon} Favourite", key=f"fav-{wine_uri}"): toggle_favourite(wine_uri)
                    else: st.markdown(f"<div style='margin-top: 10px;'>{heart_icon} Favourite</div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"#### {row.get('title', 'N/A')}")
                promo_price, regular_price = row.get('raw_ec_promo_price'), row.get('raw_ec_price'); display_price = ""; num_promo, num_regular = None, None
                try: num_promo = float(promo_price) if pd.notna(promo_price) and str(promo_price).strip() != '' and str(promo_price).strip().upper() != 'N/A' else None
                except (ValueError, TypeError): pass
                try: num_regular = float(regular_price) if pd.notna(regular_price) and str(regular_price).strip() != '' and str(regular_price).strip().upper() != 'N/A' else None
                except (ValueError, TypeError): pass
                if num_promo: display_price += f"<strong><span style='color: red;'>${num_promo:.2f}</span></strong> "; display_price += f"<span style='text-decoration: line-through; color: gray;'>${num_regular:.2f}</span>" if num_regular else ""
                elif num_regular: display_price += f"<strong>${num_regular:.2f}</strong>"
                else: display_price = "N/A"
                st.markdown(f"**Price:** {display_price}", unsafe_allow_html=True)
                rating_disp, reviews_disp = row.get('raw_ec_rating', 'N/A'), row.get('raw_avg_reviews', 'N/A')
                try: reviews_disp = int(float(reviews_disp)) if pd.notna(reviews_disp) else 'N/A'
                except (ValueError, TypeError): pass
                st.markdown(f"**Rating:** {rating_disp} | **Reviews:** {reviews_disp}"); st.markdown(f"**Weighted Score:** {row.get('weighted_rating', 0.0):.4f}")
                with st.expander("More Details"):
                    st.markdown(f"**Title:** {row.get('title', 'N/A')}"); st.markdown(f"**URI:** {row.get('uri', 'N/A')}") # ... add other fields ...
                    st.markdown(f"**Country:** {row.get('raw_country_of_manufacture', 'N/A')}"); st.markdown(f"**Region:** {row.get('raw_lcbo_region_name', 'N/A')}"); st.markdown(f"**Varietal:** {row.get('raw_lcbo_varietal_name', 'N/A')}")
                    st.markdown(f"**Volume:** {row.get('raw_lcbo_unit_volume', 'N/A')}"); st.markdown(f"**Alcohol %:** {row.get('raw_lcbo_alcohol_percent', 'N/A')}"); st.markdown(f"**Sugar (g/L):** {row.get('raw_lcbo_sugar_gm_per_ltr', 'N/A')}")
                    st.markdown(f"**Description:** {row.get('raw_ec_shortdesc', 'N/A')}"); st.markdown(f"**Tasting Notes:** {row.get('raw_lcbo_tastingnotes', 'N/A')}")
                    st.markdown(f"**Inventory (Selected Store):** {row.get('stores_inventory', 'N/A')}")
                    st.markdown(f"**Monthly Sales Rank:** {row.get('raw_sell_rank_monthly', 'N/A')}"); st.markdown(f"**Monthly View Rank:** {row.get('raw_view_rank_monthly', 'N/A')}")
                    st.markdown(f"**Yearly Sales Rank:** {row.get('raw_sell_rank_yearly', 'N/A')}"); st.markdown(f"**Yearly View Rank:** {row.get('raw_view_rank_yearly', 'N/A')}")
                    if pd.notna(row.get('raw_lcbo_program')) and 'Vintages' in str(row.get('raw_lcbo_program')): st.markdown(f"**Program:** Vintages")
            st.markdown("---")
    elif data_to_display.empty and not needs_refresh: st.info("No products match the current filters, or no data has been loaded yet.")
    elif needs_refresh: st.info("Data is refreshing, please wait...")

# Entry Point
if __name__ == "__main__":
    main()

