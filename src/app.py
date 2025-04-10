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

# Supabase Configuration
# Ensure these secrets are set in your Streamlit Cloud deployment
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_SERVICE_ROLE_KEY = st.secrets["supabase"]["key"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Define Table Names
PRODUCTS_TABLE = "Products"
FAVOURITES_TABLE = "Favourites"
PRICE_HISTORY_TABLE = "Price History" # Added for clarity

# -------------------------------
# Supabase Helper Functions
# -------------------------------
def supabase_get_records(table_name):
    """Fetch all records from a Supabase table."""
    try:
        response = supabase.table(table_name).select("*").execute()
        # Check for potential errors returned by Supabase API itself
        if hasattr(response, 'error') and response.error:
             st.error(f"Supabase error fetching from {table_name}: {response.error}")
             return []
        return response.data
    except Exception as e:
        st.error(f"Failed to fetch records from {table_name}: {e}")
        # Optionally, log the full traceback for debugging
        # import traceback
        # st.error(traceback.format_exc())
        return []

def supabase_upsert_record(table_name, record):
    """Insert or update a record in a Supabase table."""
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
        # Chain eq() filters before delete()
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
    if records: # Check if records is not empty or None
        return pd.DataFrame(records)
    else:
        # Return an empty DataFrame with expected columns if fetch fails or returns empty
        # Adjust columns based on your actual PRODUCTS_TABLE structure if needed
        return pd.DataFrame(columns=['title', 'uri', 'raw_ec_rating', 'raw_avg_reviews', 'weighted_rating', 'raw_ec_price', 'raw_ec_promo_price', 'raw_country_of_manufacture', 'raw_lcbo_region_name', 'raw_lcbo_varietal_name', 'store_name', 'stores_inventory', 'raw_lcbo_program'])


# -------------------------------
# Data Handling (Local CSV - Keep if needed, but focus is now Supabase)
# -------------------------------
# You might not need load_data if exclusively using Supabase after initial refresh
@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_csv(file_path)
        return df
    except FileNotFoundError:
        st.error(f"Error: File not found at {file_path}. Please ensure 'products.csv' exists or data is fetched.")
        return pd.DataFrame() # Return empty DataFrame on error
    except Exception as e:
        st.error(f"Error loading data from {file_path}: {e}")
        return pd.DataFrame()

def load_food_items():
    try:
        # Ensure this CSV file is available in your deployment environment
        food_items = pd.read_csv('food_items.csv')
        return food_items
    except Exception as e:
        st.error(f"Error loading food items: {e}")
        return pd.DataFrame(columns=['Category', 'FoodItem'])

def sort_data(data, column):
    """Generic sort function."""
    if column in data.columns:
        # Handle potential non-numeric data if sorting numerically expected columns
        try:
            # Attempt numeric sort for specific columns if needed
            if column in ['raw_avg_reviews', 'raw_ec_rating', 'weighted_rating']:
                 data[column] = pd.to_numeric(data[column], errors='coerce')
            return data.sort_values(by=column, ascending=False, na_position='last')
        except Exception as e:
            st.warning(f"Could not sort by {column}: {e}")
            return data # Return unsorted on error
    else:
        st.warning(f"Sort column '{column}' not found in data.")
        return data

# -------------------------------
# Filter functions
# -------------------------------
def search_data(data, search_text):
    """Filter data based on search text in the 'title' column."""
    if search_text and 'title' in data.columns:
        try:
            data = data[data['title'].str.contains(search_text, case=False, na=False)]
        except Exception as e:
             st.warning(f"Error during search: {e}")
    return data

def sort_data_filter(data, sort_by):
    """Sort data based on the selected criteria, with weighted rating as the default."""
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
    else: # Default to weighted rating
        sort_column = 'weighted_rating'
        ascending = False

    if sort_column and sort_column in data.columns:
        # Ensure numeric type for sorting where applicable
        if sort_column in ['raw_avg_reviews', 'raw_ec_rating', 'weighted_rating',
                           'raw_view_rank_yearly', 'raw_view_rank_monthly',
                           'raw_sell_rank_yearly', 'raw_sell_rank_monthly']:
             data[sort_column] = pd.to_numeric(data[sort_column], errors='coerce')

        return data.sort_values(by=sort_column, ascending=ascending, na_position='last')
    elif sort_by != 'Sort by': # Don't warn if default 'Sort by' is selected
         st.warning(f"Could not sort by selected option '{sort_by}' (Column: {sort_column}). Defaulting to weighted rating.")
         # Fallback to default weighted rating sort
         if 'weighted_rating' in data.columns:
              data['weighted_rating'] = pd.to_numeric(data['weighted_rating'], errors='coerce')
              return data.sort_values(by='weighted_rating', ascending=False, na_position='last')
         else:
              return data # Return unsorted if fallback fails
    else:
         # If 'Sort by' is selected, default to weighted rating if available
         if 'weighted_rating' in data.columns:
              data['weighted_rating'] = pd.to_numeric(data['weighted_rating'], errors='coerce')
              return data.sort_values(by='weighted_rating', ascending=False, na_position='last')
         else:
              return data # Return original if no sort specified and weighted_rating missing


def filter_data(data, country='All Countries', region='All Regions', varietal='All Varietals', exclude_usa=False, in_stock=False, only_vintages=False, store='Select Store'):
    """Apply various filters to the data."""
    df = data.copy() # Work on a copy to avoid modifying original
    try:
        if country != 'All Countries' and 'raw_country_of_manufacture' in df.columns:
            df = df[df['raw_country_of_manufacture'] == country]
        if region != 'All Regions' and 'raw_lcbo_region_name' in df.columns:
            df = df[df['raw_lcbo_region_name'] == region]
        if varietal != 'All Varietals' and 'raw_lcbo_varietal_name' in df.columns:
            df = df[df['raw_lcbo_varietal_name'] == varietal]
        # Note: Store filtering logic might need adjustment if 'store_name' isn't directly in Products table
        # This assumes store info is added during/after refresh_data or loaded differently
        if store != 'Select Store' and 'store_name' in df.columns: # Check if 'store_name' exists
             df = df[df['store_name'] == store]
        elif store != 'Select Store':
             st.warning(f"Store filtering ignored: 'store_name' column not found. Data might not be store-specific yet.")

        if in_stock and 'stores_inventory' in df.columns:
             df['stores_inventory'] = pd.to_numeric(df['stores_inventory'], errors='coerce').fillna(0)
             df = df[df['stores_inventory'] > 0]
        elif in_stock:
             st.warning("In Stock filtering ignored: 'stores_inventory' column not found.")

        if only_vintages and 'raw_lcbo_program' in df.columns:
             # Ensure the column is string type before using .str accessor
             df = df[df['raw_lcbo_program'].astype(str).str.contains(r"['\"]Vintages['\"]", regex=True, na=False)]
        elif only_vintages:
             st.warning("Only Vintages filtering ignored: 'raw_lcbo_program' column not found.")

        if exclude_usa and 'raw_country_of_manufacture' in df.columns:
            df = df[df['raw_country_of_manufacture'] != 'United States']
    except Exception as e:
        st.error(f"Error during filtering: {e}")
        return data # Return original data on error
    return df

def filter_and_sort_data(data, sort_by, **filters):
    """Combine filtering and sorting."""
    if data is None or data.empty:
        return pd.DataFrame() # Return empty if no input data

    # Apply primary filters
    data = filter_data(data, **filters)

    # Apply search filter
    search_text = filters.get('search_text', '')
    data = search_data(data, search_text)

    # Apply sorting
    data = sort_data_filter(data, sort_by)
    return data

# -------------------------------
# Favourites Handling
# -------------------------------
def load_favourites():
    """Load favourites URIs for the hardcoded 'admin' user from Supabase."""
    # Consider making 'admin' dynamic if you support multiple users
    user_id_to_load = "admin"
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
    # Consider making 'admin' dynamic
    user_id_to_save = "admin"
    today_str = datetime.now().strftime("%Y-%m-%d")
    records_to_upsert = []
    for uri in favourites_to_add:
        records_to_upsert.append({"URI": uri, "Date": today_str, "User ID": user_id_to_save})

    if records_to_upsert:
        try:
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
    else:
        st.info("No new favourites to save.")


def delete_favourites(favourites_to_delete):
    """Remove a list of favourite URIs from Supabase for the 'admin' user."""
    # Consider making 'admin' dynamic
    user_id_to_delete = "admin"
    success = True
    for uri in favourites_to_delete:
        # Call the specific delete function that handles both URI and User ID
        deleted_data = supabase_delete_record(FAVOURITES_TABLE, uri, user_id_to_delete)
        if deleted_data is None: # Check if the delete function indicated an error
             success = False
             # Error message is already shown by supabase_delete_record

    if success:
        st.success("Favourites deleted successfully!")
        # Reload favourites into session state after deleting
        st.session_state.favourites = load_favourites()
        st.rerun() # Rerun to update UI immediately

def toggle_favourite(wine_id):
    """Toggle the favourite status of a wine for the 'admin' user."""
    # Load current favourites to ensure we have the latest state
    current_favourites = load_favourites() # Use load_favourites which already filters for 'admin'

    if wine_id in current_favourites:
        # Remove it by calling delete_favourites with a list containing the single ID
        delete_favourites([wine_id])
        # Success message is handled within delete_favourites now
        # st.success(f"Removed wine with URI '{wine_id}' from favourites.") # Can be removed
    else:
        # Add it by calling save_favourites with a list containing the single ID
        save_favourites([wine_id])
        # Success message is handled within save_favourites now
        # st.success(f"Added wine with URI '{wine_id}' to favourites.") # Can be removed
    # No explicit rerun needed here as save/delete functions handle it


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
    try:
        return re.sub(r"\d+\.\d+\.(png|PNG|jpg|JPG|jpeg|JPEG)$", new_size, url, flags=re.IGNORECASE)
    except Exception:
         return url # Return original URL if regex fails


# -------------------------------
# Background Tasks / Email Logic
# -------------------------------
def get_favourites_with_lowest_price():
    """Check if favourites are at their lowest recorded price."""
    st.info("Checking favourites for lowest prices...")
    # Load current favourites for the 'admin' user
    favourite_uris = load_favourites()
    if not favourite_uris:
        st.info("No favourites found for user 'admin'.")
        return []

    # Load product data (consider filtering only needed products)
    # This could be optimized if PRODUCTS_TABLE is very large
    all_products = supabase_get_records(PRODUCTS_TABLE)
    if not all_products:
        st.warning("Could not load product data to check prices.")
        return []
    products_df = pd.DataFrame(all_products)
    # Filter products_df to only include favourited items for efficiency
    products_df = products_df[products_df['uri'].isin(favourite_uris)]
    if products_df.empty:
         st.info("No product data found for the favourited items.")
         return []


    # Load price history (consider filtering only needed history)
    # This could be optimized if PRICE_HISTORY_TABLE is very large
    price_history = supabase_get_records(PRICE_HISTORY_TABLE)
    if not price_history:
        st.warning("Could not load price history data.")
        return [] # Cannot determine lowest price without history
    price_history_df = pd.DataFrame(price_history)
    # Filter history to only include favourited items
    price_history_df = price_history_df[price_history_df['URI'].isin(favourite_uris)]


    lowest_price_items = []

    # Calculate lowest price per URI from history efficiently
    if not price_history_df.empty:
         price_history_df['Price'] = pd.to_numeric(price_history_df['Price'], errors='coerce')
         lowest_prices = price_history_df.loc[price_history_df.groupby('URI')['Price'].idxmin()]
    else:
         lowest_prices = pd.DataFrame(columns=['URI', 'Price']) # Empty if no history


    # Iterate through favourites DataFrame (which contains current product info)
    for _, product in products_df.iterrows():
        uri = product.get("uri")
        if not uri:
            continue

        # Get current price (handle promo price)
        current_price = product.get("raw_ec_promo_price")
        # Check if promo price is valid (not None, not NaN, not 'N/A' string)
        if pd.isna(current_price) or str(current_price).strip() == '' or str(current_price).strip().upper() == 'N/A':
             current_price = product.get("raw_ec_price") # Fallback to regular price

        # Ensure current price is numeric
        current_price_numeric = pd.to_numeric(current_price, errors='coerce')
        if pd.isna(current_price_numeric):
            st.warning(f"Skipping {product.get('title', uri)}: Invalid current price ('{current_price}')")
            continue

        # Look up the lowest price from our pre-calculated history
        lowest_entry = lowest_prices[lowest_prices['URI'] == uri]

        if not lowest_entry.empty:
            lowest_price_numeric = lowest_entry['Price'].iloc[0] # Already numeric
            if pd.isna(lowest_price_numeric):
                 st.warning(f"Skipping {product.get('title', uri)}: Lowest historical price is invalid.")
                 continue

            # Compare prices (use a small tolerance for float comparison if needed)
            # Example: if abs(current_price_numeric - lowest_price_numeric) < 0.001:
            if current_price_numeric <= lowest_price_numeric:
                lowest_price_items.append({
                    "Title": product.get("title", "Unknown Title"),
                    "URI": uri,
                    "Current Price": f"${current_price_numeric:.2f}", # Format for display
                    "Lowest Price": f"${lowest_price_numeric:.2f}" # Format for display
                })
        else:
            # Optional: Handle items with no price history if needed
            # st.info(f"No price history found for favourite item: {uri}")
            pass

    st.info(f"Found {len(lowest_price_items)} favourites at their lowest price.")
    return lowest_price_items


def send_email_with_lowest_prices(items):
    """Send an email with the list of favourite items at their lowest price using SMTP."""
    if not items:
        st.info("No items at lowest price to report. Email not sent.")
        return

    # --- IMPORTANT: Use Streamlit Secrets for Credentials ---
    try:
        # Using generic names, replace with your actual secret keys
        smtp_server = st.secrets["smtp"]["server"]
        smtp_port = st.secrets["smtp"]["port"]
        smtp_username = st.secrets["smtp"]["username"]
        smtp_password = st.secrets["smtp"]["password"]
        sender_email = st.secrets["smtp"]["sender_email"]
        receiver_email = st.secrets["smtp"]["receiver_email"] # Can be same as sender or different
    except KeyError as e:
        st.error(f"Missing SMTP secret: {e}. Please configure secrets for smtp.server, smtp.port, etc.")
        return
    except Exception as e:
         st.error(f"Error accessing SMTP secrets: {e}")
         return

    subject = "Favourites at Their Lowest Price Alert!"

    # Create the email content
    message = MIMEMultipart("alternative") # Use alternative for HTML and plain text
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject

    # Build Plain Text Body
    text_content = "Favourites at Their Lowest Price:\n\n"
    for item in items:
        text_content += f"- Title: {item['Title']}\n"
        text_content += f"  URI: {item['URI']}\n"
        text_content += f"  Current Price: {item['Current Price']}\n"
        text_content += f"  Lowest Recorded Price: {item['Lowest Price']}\n\n"

    # Build HTML Body
    html_content = """
    <html>
      <head></head>
      <body>
        <h3>Favourites at Their Lowest Price</h3>
        <table border='1' style='border-collapse: collapse; width: 100%;'>
          <thead>
            <tr style='background-color: #f2f2f2;'>
              <th style='padding: 8px; text-align: left;'>Title</th>
              <th style='padding: 8px; text-align: left;'>URI</th>
              <th style='padding: 8px; text-align: right;'>Current Price</th>
              <th style='padding: 8px; text-align: right;'>Lowest Recorded</th>
            </tr>
          </thead>
          <tbody>
    """
    for item in items:
        # Basic escaping for HTML safety, consider more robust library if needed
        title_safe = item['Title'].replace('<', '&lt;').replace('>', '&gt;')
        uri_safe = item['URI'].replace('<', '&lt;').replace('>', '&gt;')
        current_price_safe = item['Current Price'].replace('<', '&lt;').replace('>', '&gt;')
        lowest_price_safe = item['Lowest Price'].replace('<', '&lt;').replace('>', '&gt;')
        html_content += f"""
            <tr>
              <td style='padding: 8px;'>{title_safe}</td>
              <td style='padding: 8px;'><a href='{uri_safe}'>{uri_safe}</a></td>
              <td style='padding: 8px; text-align: right;'>{current_price_safe}</td>
              <td style='padding: 8px; text-align: right;'>{lowest_price_safe}</td>
            </tr>
        """
    html_content += """
          </tbody>
        </table>
      </body>
    </html>
    """

    # Attach both parts
    message.attach(MIMEText(text_content, "plain"))
    message.attach(MIMEText(html_content, "html"))

    # Send the email
    try:
        st.info(f"Attempting to send email via {smtp_server}:{smtp_port}...")
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo() # Say hello to server
            server.starttls() # Secure the connection
            server.ehlo() # Say hello again after TLS
            server.login(smtp_username, smtp_password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        st.success("Email sent successfully!")
    except smtplib.SMTPAuthenticationError:
         st.error("SMTP Authentication Error: Incorrect username or password. Check your secrets.")
    except smtplib.SMTPConnectError:
         st.error(f"SMTP Connection Error: Failed to connect to {smtp_server}:{smtp_port}.")
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        # import traceback
        # st.error(traceback.format_exc()) # For detailed debug if needed


def background_update(products_list, today_str):
    """Perform table updates and price history processing in the background."""
    st.info("Background update started...")
    # 1. Upsert Product Data
    records_to_upsert = []
    for product in products_list:
        # Ensure 'Date' is added if needed by your schema, or handle primary keys correctly
        product_record = product.copy() # Work on a copy
        product_record["Date"] = today_str # Add update date if relevant
        # Make sure the record structure matches your PRODUCTS_TABLE exactly
        # Especially primary key(s) like 'uri'
        records_to_upsert.append(product_record)

    if records_to_upsert:
         st.info(f"Upserting {len(records_to_upsert)} products to Supabase...")
         # Consider upserting in smaller batches if you have thousands of products
         batch_size = 500
         for i in range(0, len(records_to_upsert), batch_size):
             batch = records_to_upsert[i:i + batch_size]
             upsert_result = supabase_upsert_record(PRODUCTS_TABLE, batch)
             if upsert_result is None:
                  st.warning(f"Failed to upsert product batch starting at index {i}.")
             # else:
                  # st.info(f"Upserted product batch {i // batch_size + 1}") # Optional progress
         st.info("Background update: Products table upsert completed.")
    else:
         st.info("Background update: No products to upsert.")

    # 2. Update Price History (Assuming product_list contains current price)
    price_history_records = []
    for product in products_list:
         uri = product.get('uri')
         # Determine the price to log (handle promo vs regular)
         price = product.get("raw_ec_promo_price")
         if pd.isna(price) or str(price).strip() == '' or str(price).strip().upper() == 'N/A':
              price = product.get("raw_ec_price")

         price_numeric = pd.to_numeric(price, errors='coerce')

         if uri and not pd.isna(price_numeric):
              price_history_records.append({
                   "URI": uri,
                   "Price": price_numeric,
                   "Date": today_str # Log the date the price was recorded
              })

    if price_history_records:
         st.info(f"Adding {len(price_history_records)} price history records...")
         # Price history should likely be an INSERT, not upsert, unless you only want one entry per day per URI
         # Using upsert assumes ('URI', 'Date') is your primary key or you want to overwrite
         response = supabase.table(PRICE_HISTORY_TABLE).upsert(price_history_records).execute()
         if hasattr(response, 'error') and response.error:
              st.error(f"Supabase error saving price history: {response.error}")
         else:
              st.info("Background update: Price history saved.")
    else:
         st.info("Background update: No valid price history records generated.")


    # 3. Check favourites for lowest prices and send an email
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

    # --- Optional: Check if data for today already exists ---
    # This requires querying Supabase first, might slow down initial load slightly
    # try:
    #     # Query *only* for the date column, limit 1 for efficiency
    #     response = supabase.table(PRODUCTS_TABLE).select("Date", count="exact").eq("Date", today_str).limit(1).execute()
    #     if response.count > 0:
    #          st.info(f"Data for {today_str} already exists in Supabase. Loading from DB.")
    #          return load_products_from_supabase() # Load existing data
    # except Exception as e:
    #      st.warning(f"Could not check for existing data for {today_str}: {e}. Proceeding with API refresh.")
    # --- End Optional Check ---

    st.info("Refreshing data from LCBO API...")
    url = "https://platform.cloud.coveo.com/rest/search/v2?organizationId=lcboproduction2kwygmc"
    # --- Use Secrets for Authorization Token ---
    try:
         api_token = st.secrets["api"]["token"] # Assumes secret structure [api] token = "Bearer ..."
    except KeyError:
         st.error("API Authorization Token not found in secrets. Please set secrets['api']['token']")
         return None # Cannot proceed without auth

    headers = {
        "User-Agent": "Mozilla/5.0 StreamlitApp/1.0", # Example User-Agent
        "Accept": "application/json",
        "Authorization": api_token, # Use the token from secrets
        "Content-Type": "application/json",
        "Referer": "https://www.lcbo.com/", # Keep referer
    }

    # Base payload structure
    base_payload = {
        "q": "",
        "tab": "clp-products-wine-red_wine",
        "sort": "ec_rating descending", # Initial sort doesn't matter much if we recalculate rating
        "facets": [
            {
                "field": "ec_rating",
                "currentValues": [
                    {   # Fetching 4+ star ratings initially
                        "value": "4..5inc",
                        "state": "selected"
                    }
                ]
            }
        ],
        "numberOfResults": 500, # Max per page
        "firstResult": 0,
         # Simplified AQ to get Red Wines visible online/in store
        "aq": '@ec_visibility==(2,4) @ec_category=="Products|Wine|Red Wine"'
        # Removed rating filter from AQ to ensure mean calculation is broad
        # "@ec_visibility==(2,4) @cp_Browse_category_deny<>0 @ec_category==\"Products|Wine|Red Wine\" (@ec_rating==5..5 OR @ec_rating==4..4.9)"
    }

    # Add store context if a specific store is selected
    dictionaryFieldContext = {} # Initialize empty context
    if store_id:
        dictionaryFieldContext = {
            # Adjust context keys based on testing if needed
            "stores_stock": "", # Seems necessary based on your old code
            "stores_inventory": store_id,
            "stores_stock_combined": store_id,
            "stores_low_stock_combined": store_id
        }
        # Add the context to the base payload if store_id exists
        base_payload["dictionaryFieldContext"] = dictionaryFieldContext


    # Function to fetch a batch of items
    def get_items(payload):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30) # Added timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
             st.error(f"API request failed: {e}")
             return None # Return None on request failure
        except Exception as e:
             st.error(f"Error processing API response: {e}")
             return None


    st.info("Fetching initial batch from API...")
    initial_data = get_items(base_payload)

    if initial_data and 'results' in initial_data:
        all_items = initial_data['results']
        total_count = initial_data.get('totalCount', 0)
        st.info(f"API reported total count: {total_count}")

        # Calculate number of pages needed
        num_requests = (total_count // 500) + (1 if total_count % 500 != 0 else 0)
        st.info(f"Fetching {num_requests} batches...")

        progress_bar = st.progress(0) # Initialize progress bar

        # Fetch subsequent pages
        for i in range(1, num_requests):
            current_payload = base_payload.copy() # Start with base payload
            current_payload["firstResult"] = i * 500 # Update page offset

            # Re-apply store context if it was set
            if dictionaryFieldContext:
                 current_payload["dictionaryFieldContext"] = dictionaryFieldContext

            # st.info(f"Fetching batch {i+1}/{num_requests}...") # Verbose logging
            paged_data = get_items(current_payload)

            if paged_data and 'results' in paged_data:
                all_items.extend(paged_data['results'])
            else:
                st.warning(f"No 'results' in response for batch {i+1}, stopping pagination.")
                # Log the response if helpful for debugging
                # st.warning(f"Response for failed batch: {paged_data}")
                break # Stop if a page fails

            # Update progress bar
            progress = int(((i + 1) / num_requests) * 100)
            progress_bar.progress(progress)

            time.sleep(0.5) # Be slightly nicer to the API

        progress_bar.empty() # Remove progress bar after completion
        st.info(f"Total items fetched: {len(all_items)}")

        # --- START: Weighted Rating Calculation (Adopted from Old Code Logic) ---

        # Create a temporary DataFrame *first* to calculate stats
        temp_df = pd.DataFrame([{
            'raw_ec_rating': item['raw'].get('ec_rating'),
            'raw_avg_reviews': item['raw'].get('avg_reviews')
        } for item in all_items])

        # Convert to numeric, coercing errors (like 'N/A' or missing) to NaN
        temp_df['numeric_rating'] = pd.to_numeric(temp_df['raw_ec_rating'], errors='coerce')
        temp_df['numeric_reviews'] = pd.to_numeric(temp_df['raw_avg_reviews'], errors='coerce')

        # Calculate mean rating ONLY from items with actual reviews > 0
        valid_reviewed_items = temp_df.dropna(subset=['numeric_reviews', 'numeric_rating'])
        valid_reviewed_items = valid_reviewed_items[valid_reviewed_items['numeric_reviews'] > 0]
        mean_rating = valid_reviewed_items['numeric_rating'].mean()

        # Handle case where NO items have reviews > 0
        if pd.isna(mean_rating):
            mean_rating = temp_df['numeric_rating'].mean()
            if pd.isna(mean_rating):
                mean_rating = 0.0 # Absolute fallback if no ratings exist at all

        # *** Use a fixed minimum votes threshold ***
        minimum_votes = 10 # This matches your old working code

        st.info(f"Calculated mean_rating (C) for weighted score: {mean_rating:.4f}") # For debugging
        st.info(f"Using fixed minimum_votes (m) for weighted score: {minimum_votes}") # For debugging

        # Define the weighted rating function (ensure inputs are handled as floats)
        def weighted_rating(rating, votes, min_votes, avg_rating):
            try:
                rating = float(rating) if pd.notna(rating) else 0.0
                votes = float(votes) if pd.notna(votes) else 0.0
                min_votes = float(min_votes)
                avg_rating = float(avg_rating)
            except (ValueError, TypeError):
                return 0.0 # Return 0 if any conversion fails

            denominator = votes + min_votes
            if denominator == 0:
                return 0.0 # Avoid division by zero

            # IMDb formula: (v/(v+m))*R + (m/(v+m))*C
            return (votes / denominator * rating) + (min_votes / denominator * avg_rating)

        # Now process the original all_items list to create the final products list
        products_list_for_update = [] # Use a different name to avoid confusion
        for product_api_item in all_items:
            raw_data = product_api_item['raw']
            rating_val = raw_data.get('ec_rating')
            votes_val = raw_data.get('avg_reviews')

            # Create the dictionary for this product
            product_info = {
                'title': product_api_item.get('title', 'N/A'),
                'uri': product_api_item.get('uri', 'N/A'),
                # --- Add ALL other fields you need from raw_data here ---
                'raw_ec_thumbnails': raw_data.get('ec_thumbnails', 'N/A'),
                'raw_ec_shortdesc': raw_data.get('ec_shortdesc', 'N/A'),
                'raw_lcbo_tastingnotes': raw_data.get('lcbo_tastingnotes', 'N/A'),
                'raw_lcbo_region_name': raw_data.get('lcbo_region_name', 'N/A'),
                'raw_country_of_manufacture': raw_data.get('country_of_manufacture', 'N/A'),
                'raw_lcbo_program': raw_data.get('lcbo_program', 'N/A'),
                'raw_created_at': raw_data.get('created_at', 'N/A'), # Might not be needed?
                'raw_is_buyable': raw_data.get('is_buyable', 'N/A'),
                'raw_ec_price': raw_data.get('ec_price', 'N/A'),
                'raw_ec_final_price': raw_data.get('ec_final_price', 'N/A'), # Check if needed
                'raw_ec_promo_price': raw_data.get('ec_promo_price', 'N/A'), # Important for price check
                'raw_lcbo_unit_volume': raw_data.get('lcbo_unit_volume', 'N/A'),
                'raw_lcbo_alcohol_percent': raw_data.get('lcbo_alcohol_percent', 'N/A'),
                'raw_lcbo_sugar_gm_per_ltr': raw_data.get('lcbo_sugar_gm_per_ltr', 'N/A'),
                'raw_lcbo_bottles_per_pack': raw_data.get('lcbo_bottles_per_pack', 'N/A'),
                'raw_sysconcepts': raw_data.get('sysconcepts', 'N/A'), # Used for food pairing
                'raw_ec_category': raw_data.get('ec_category', 'N/A'),
                'raw_ec_category_filter': raw_data.get('ec_category_filter', 'N/A'),
                'raw_lcbo_varietal_name': raw_data.get('lcbo_varietal_name', 'N/A'),
                'raw_stores_stock': raw_data.get('stores_stock', 'N/A'), # If store specific
                'raw_stores_stock_combined': raw_data.get('stores_stock_combined', 'N/A'), # If store specific
                'raw_stores_low_stock_combined': raw_data.get('stores_low_stock_combined', 'N/A'), # If store specific
                'raw_stores_low_stock': raw_data.get('stores_low_stock', 'N/A'), # If store specific
                'raw_out_of_stock': raw_data.get('out_of_stock', 'N/A'), # If store specific
                'stores_inventory': raw_data.get('stores_inventory', 0), # Important for filter
                'raw_online_inventory': raw_data.get('online_inventory', 0),
                'raw_avg_reviews': votes_val,   # Store original value from API
                'raw_ec_rating': rating_val,     # Store original value from API
                'weighted_rating': weighted_rating(rating_val, votes_val, minimum_votes, mean_rating), # Use calculated WR
                'raw_view_rank_yearly': raw_data.get('view_rank_yearly', 'N/A'),
                'raw_view_rank_monthly': raw_data.get('view_rank_monthly', 'N/A'),
                'raw_sell_rank_yearly': raw_data.get('sell_rank_yearly', 'N/A'),
                'raw_sell_rank_monthly': raw_data.get('sell_rank_monthly', 'N/A')
                 # Add 'Date' field just before upserting in background thread if needed
                 # 'Date': today_str
            }
            # Add store name if store was selected (assuming API doesn't return it)
            if store_id and st.session_state.selected_store != 'Select Store':
                 product_info['store_name'] = st.session_state.selected_store
            else:
                 product_info['store_name'] = None # Or handle as needed

            products_list_for_update.append(product_info)

        # --- END: Weighted Rating Calculation ---

        # Create DataFrame from the processed list for immediate display
        df_products_display = pd.DataFrame(products_list_for_update)

        # Start background thread for Supabase updates and email check
        st.info("Starting background thread for database updates and price checks...")
        thread = threading.Thread(target=background_update, args=(products_list_for_update, today_str), daemon=True)
        thread.start()

        st.success("API data fetched! Displaying current data while background updates run.")
        return df_products_display # Return the processed data immediately

    else:
        st.error("Failed to retrieve initial data from the API.")
        # Log the response if helpful
        st.error(f"API Response: {initial_data}")
        return load_products_from_supabase() # Fallback to loading existing data if API fails


# -------------------------------
# Main Streamlit App
# -------------------------------
def main():
    st.set_page_config(layout="wide") # Use wider layout
    st.title("🍷 LCBO Wine Filter & Favourite Tracker")

    # --- Authorization ---
    if "authorized" not in st.session_state:
        st.session_state.authorized = False # Default to not authorized

    with st.sidebar.expander("Admin Authorization", expanded=not st.session_state.authorized):
        pin_input = st.text_input("Enter PIN", type="password", key="auth_pin")
        if st.button("Login", key="auth_submit"):
            correct_pin = st.secrets.get("correct_pin", "DEFAULT_PIN_IF_MISSING") # Get PIN from secrets
            if pin_input == correct_pin:
                st.session_state.authorized = True
                st.rerun() # Rerun to update UI after successful login
            else:
                st.sidebar.error("Incorrect PIN.")

    # --- Session State Initialization ---
    if "favourites" not in st.session_state:
        # Load favourites only if authorized to prevent unnecessary loads for non-admins
        # Assuming only admin uses favourites based on hardcoded "admin" user ID
        if st.session_state.authorized:
             st.session_state.favourites = load_favourites()
        else:
             st.session_state.favourites = [] # Empty list if not authorized
    if "ui_updated" not in st.session_state:
        st.session_state.ui_updated = False # Flag for UI updates might not be needed with rerun()
    if 'selected_store' not in st.session_state:
        st.session_state.selected_store = 'Select Store'
    if 'data' not in st.session_state:
        st.session_state.data = pd.DataFrame() # Initialize data state


    # --- Sidebar Filters ---
    st.sidebar.header("Filter Options 🔍")

    # Store Selector
    store_options = ['Select Store', 'Bradford', 'E. Gwillimbury', 'Upper Canada', 'Yonge & Eg', 'Dufferin & Steeles']
    store_ids = {
        "Bradford": "145",
        "E. Gwillimbury": "391",
        "Upper Canada": "226",
        "Yonge & Eg": "457",
        "Dufferin & Steeles": "618"
    }
    selected_store = st.sidebar.selectbox("Select Store", options=store_options, key="store_selector")

    # --- Data Loading / Refresh Logic ---
    # Trigger refresh manually or based on store change
    needs_refresh = False
    if selected_store != st.session_state.selected_store:
        st.info(f"Store changed to {selected_store}. Triggering data refresh.")
        st.session_state.selected_store = selected_store
        needs_refresh = True

    # Manual Refresh Button
    if st.sidebar.button("Refresh Data from API", key="manual_refresh"):
         needs_refresh = True
         st.info("Manual refresh requested.")

    # Perform refresh if needed
    if needs_refresh:
        store_id_to_pass = store_ids.get(selected_store) if selected_store != 'Select Store' else None
        with st.spinner("Fetching fresh data from API... Please wait."):
             refreshed_data = refresh_data(store_id=store_id_to_pass)
        if refreshed_data is not None:
             st.session_state.data = refreshed_data
             st.success("Data refresh complete.")
        else:
             st.error("Data refresh failed. Loading potentially stale data from database.")
             st.session_state.data = load_products_from_supabase()
    else:
        # Load data from session state if available, otherwise from Supabase
        if st.session_state.data.empty:
             st.info("Loading initial data from database...")
             st.session_state.data = load_products_from_supabase()
             if st.session_state.data.empty:
                  st.warning("No data loaded from database. Please try refreshing.")


    # Use the data stored in session state for filtering
    data_to_display = st.session_state.data

    # Continue with other sidebar filters
    search_text = st.sidebar.text_input("Search Title", value="")
    sort_by = st.sidebar.selectbox("Sort by", ['Sort by', '# of reviews', 'Rating', 'Top Viewed - Year', 'Top Viewed - Month', 'Top Seller - Year', 'Top Seller - Month'])

    # Create filter options from the currently loaded data
    if not data_to_display.empty:
         country_options = ['All Countries'] + sorted(data_to_display['raw_country_of_manufacture'].dropna().unique().tolist())
         region_options = ['All Regions'] + sorted(data_to_display['raw_lcbo_region_name'].dropna().unique().tolist())
         varietal_options = ['All Varietals'] + sorted(data_to_display['raw_lcbo_varietal_name'].dropna().unique().tolist())
    else:
         country_options = ['All Countries']
         region_options = ['All Regions']
         varietal_options = ['All Varietals']

    # Food pairing (assuming food_items.csv is loaded)
    food_items = load_food_items()
    categories = food_items['Category'].unique() if not food_items.empty else []
    food_options = ['All Dishes'] + sorted(categories.tolist())

    country = st.sidebar.selectbox("Country", options=country_options)
    region = st.sidebar.selectbox("Region", options=region_options)
    varietal = st.sidebar.selectbox("Varietal", options=varietal_options)
    food_category = st.sidebar.selectbox("Food Category", options=food_options)
    exclude_usa = st.sidebar.checkbox("Exclude USA", value=False)
    in_stock = st.sidebar.checkbox("In Stock Only (Selected Store)", value=False) # Clarify scope
    only_vintages = st.sidebar.checkbox("Only Vintages", value=False)
    only_sale_items = st.sidebar.checkbox("Only Sale Items", value=False)
    # Only show "Only Favourites" if authorized
    only_favourites = st.sidebar.checkbox("Only My Favourites", value=False) if st.session_state.authorized else False


    # --- Apply Filters and Sorting ---
    if not data_to_display.empty:
        filters = {
            'country': country,
            'region': region,
            'varietal': varietal,
            'exclude_usa': exclude_usa,
            'in_stock': in_stock,
            'only_vintages': only_vintages,
            'store': selected_store, # Pass selected store name for potential use
            'search_text': search_text
        }
        filtered_data = filter_and_sort_data(data_to_display, sort_by, **filters)

        # Apply "Only Sale Items" filter
        if only_sale_items and 'raw_ec_promo_price' in filtered_data.columns:
            # Ensure promo price column is treated correctly (handle None/NaN/empty strings)
            filtered_data['promo_price_numeric'] = pd.to_numeric(filtered_data['raw_ec_promo_price'], errors='coerce')
            filtered_data = filtered_data[filtered_data['promo_price_numeric'].notna() & (filtered_data['promo_price_numeric'] > 0)] # Check for valid numeric promo price
            filtered_data = filtered_data.drop(columns=['promo_price_numeric']) # Drop temporary column
        elif only_sale_items:
            st.warning("Sale item filter ignored: 'raw_ec_promo_price' column not found or invalid.")


        # Apply "Only Favourites" filter (only if checkbox checked and authorized)
        if only_favourites and st.session_state.authorized and 'uri' in filtered_data.columns:
             current_favs = st.session_state.favourites # Use favourites from session state
             filtered_data = filtered_data[filtered_data['uri'].isin(current_favs)]
        elif only_favourites and not st.session_state.authorized:
             st.warning("Please log in to view only favourites.")
        elif only_favourites:
             st.warning("Favourites filter ignored: 'uri' column not found.")

         # Food Category Filtering (apply after other filters)
        if food_category != 'All Dishes' and not food_items.empty and 'raw_sysconcepts' in filtered_data.columns:
            selected_food_items = food_items[food_items['Category'] == food_category]['FoodItem'].str.lower().tolist()
            # Function to check if any selected food item is in the sysconcepts string
            def check_food_match(sysconcepts_str):
                 if pd.isna(sysconcepts_str):
                      return False
                 text_to_check = str(sysconcepts_str).lower()
                 return any(item in text_to_check for item in selected_food_items)

            filtered_data = filtered_data[filtered_data['raw_sysconcepts'].apply(check_food_match)]

        st.write(f"Showing **{len(filtered_data)}** products")

    else:
        filtered_data = pd.DataFrame() # Empty DataFrame if no data loaded
        st.write("No product data loaded.")


    # --- Display Products with Pagination ---
    if not filtered_data.empty:
        page_size = 10
        total_products = len(filtered_data)
        total_pages = (total_products // page_size) + (1 if total_products % page_size > 0 else 0) # Correct calculation for remainder

        if total_pages > 0:
            page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1, key="pagination")
        else:
            page = 1 # Default to page 1 even if no data (prevents error)

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_data = filtered_data.iloc[start_idx:end_idx]

        # Display Products on the current page
        for idx, row in page_data.iterrows():
            col1, col2 = st.columns([1, 3]) # Column for image+fav, Column for details

            with col1:
                # Display the thumbnail image
                thumbnail_url = row.get('raw_ec_thumbnails', None)
                if pd.notna(thumbnail_url) and thumbnail_url != 'N/A':
                    st.image(thumbnail_url, width=150)
                    # Add an "Enlarge Image" popover
                    with st.popover("Enlarge"):
                        large_image_url = transform_image_url(thumbnail_url, "2048.2048.png")
                        if large_image_url != thumbnail_url: # Check if transform worked
                             st.image(large_image_url, use_container_width=True)
                        else:
                             st.image(thumbnail_url, use_container_width=True) # Show original if transform failed
                else:
                    st.caption("No image") # Placeholder if no image

                # Favourite button / indicator
                wine_uri = row.get('uri') # Use URI as the unique identifier
                if wine_uri:
                    is_favourite = wine_uri in st.session_state.favourites
                    heart_icon = "❤️" if is_favourite else "🤍"
                    button_label = f"{heart_icon} Favourite"
                    button_key = f"fav-{wine_uri}" # Use URI in key for uniqueness

                    if st.session_state.authorized:
                        if st.button(button_label, key=button_key):
                            toggle_favourite(wine_uri)
                            # toggle_favourite now handles the rerun
                    else:
                        # Display non-clickable indicator if not authorized
                        st.markdown(f"<div style='margin-top: 10px;'>{heart_icon} Favourite</div>", unsafe_allow_html=True)


            with col2:
                st.markdown(f"#### {row.get('title', 'N/A')}")

                # Price display logic
                promo_price = row.get('raw_ec_promo_price')
                regular_price = row.get('raw_ec_price')
                display_price = ""

                # Try converting prices to numeric, handle errors/None/'N/A'
                try:
                    num_promo = float(promo_price) if pd.notna(promo_price) and str(promo_price).strip() != '' and str(promo_price).strip().upper() != 'N/A' else None
                except (ValueError, TypeError):
                    num_promo = None
                try:
                    num_regular = float(regular_price) if pd.notna(regular_price) and str(regular_price).strip() != '' and str(regular_price).strip().upper() != 'N/A' else None
                except (ValueError, TypeError):
                    num_regular = None

                if num_promo is not None and num_promo > 0:
                     # Sale Icon SVG (consider making this smaller or placing differently)
                     # sale_icon_svg = """<svg fill="#d00b0b"... </svg>""" # Your SVG here (shortened for brevity)
                     display_price += f"<strong><span style='color: red;'>${num_promo:.2f}</span></strong> "
                     if num_regular is not None:
                          display_price += f"<span style='text-decoration: line-through; color: gray;'>${num_regular:.2f}</span>"
                elif num_regular is not None:
                     display_price += f"<strong>${num_regular:.2f}</strong>"
                else:
                     display_price = "N/A" # Fallback if no valid price

                st.markdown(f"**Price:** {display_price}", unsafe_allow_html=True)

                # Rating and Reviews display
                rating_disp = row.get('raw_ec_rating', 'N/A')
                reviews_disp = row.get('raw_avg_reviews', 'N/A')
                try: # Attempt to format reviews as integer if possible
                     reviews_disp = int(float(reviews_disp)) if pd.notna(reviews_disp) else 'N/A'
                except (ValueError, TypeError): pass # Keep as is if not convertible
                st.markdown(f"**Rating:** {rating_disp} | **Reviews:** {reviews_disp}")
                st.markdown(f"**Weighted Score:** {row.get('weighted_rating', 0.0):.4f}") # Display calculated weighted rating

                # Expander for more details
                with st.expander("More Details"):
                    # Safely get values using .get() with default 'N/A'
                    st.markdown(f"**Title:** {row.get('title', 'N/A')}")
                    st.markdown(f"**URI:** {row.get('uri', 'N/A')}")
                    st.markdown(f"**Country:** {row.get('raw_country_of_manufacture', 'N/A')}")
                    st.markdown(f"**Region:** {row.get('raw_lcbo_region_name', 'N/A')}")
                    st.markdown(f"**Varietal:** {row.get('raw_lcbo_varietal_name', 'N/A')}")
                    st.markdown(f"**Volume:** {row.get('raw_lcbo_unit_volume', 'N/A')}")
                    st.markdown(f"**Alcohol %:** {row.get('raw_lcbo_alcohol_percent', 'N/A')}")
                    st.markdown(f"**Sugar (g/L):** {row.get('raw_lcbo_sugar_gm_per_ltr', 'N/A')}")
                    st.markdown(f"**Description:** {row.get('raw_ec_shortdesc', 'N/A')}")
                    st.markdown(f"**Tasting Notes:** {row.get('raw_lcbo_tastingnotes', 'N/A')}")
                    st.markdown(f"**Inventory (Selected Store):** {row.get('stores_inventory', 'N/A')}") # This relies on store context being correctly applied
                    st.markdown(f"**Monthly Sales Rank:** {row.get('raw_sell_rank_monthly', 'N/A')}")
                    st.markdown(f"**Monthly View Rank:** {row.get('raw_view_rank_monthly', 'N/A')}")
                    st.markdown(f"**Yearly Sales Rank:** {row.get('raw_sell_rank_yearly', 'N/A')}")
                    st.markdown(f"**Yearly View Rank:** {row.get('raw_view_rank_yearly', 'N/A')}")
                    if pd.notna(row.get('raw_lcbo_program')) and 'Vintages' in str(row.get('raw_lcbo_program')):
                         st.markdown(f"**Program:** Vintages")

            st.markdown("---") # Separator between products

    elif data_to_display.empty and not needs_refresh:
        st.info("No products match the current filters, or no data has been loaded yet.")
    elif needs_refresh:
         st.info("Data is refreshing, please wait...")


# -------------------------------
# Entry Point
# -------------------------------
if __name__ == "__main__":
    main()
