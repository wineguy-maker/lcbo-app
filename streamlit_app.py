import streamlit as st
import pandas as pd
import time
from datetime import datetime
import requests
import re
import base64 # Needed for GitHub API
import io # Needed to handle CSV string conversion

# -------------------------------
# GitHub Configuration & Secrets
# -------------------------------
# Try fetching the PAT from Streamlit secrets
try:
    GITHUB_PAT = st.secrets["GITHUB_PAT"]
except KeyError:
    st.error("GitHub PAT not found in Streamlit secrets. Please add it.")
    st.stop() # Stop execution if PAT is missing

GITHUB_REPO_OWNER = "wineguy-maker"
GITHUB_REPO_NAME = "lcbo-app"
PRODUCTS_CSV_PATH = "products.csv"
FAVORITES_CSV_PATH = "favorites.csv"
GITHUB_HEADERS = {
    "Authorization": f"token {GITHUB_PAT}",
    "Accept": "application/vnd.github.v3+json"
}

# -------------------------------
# GitHub Interaction Functions
# -------------------------------

def get_github_file_content(owner, repo, path, headers):
    """Gets the content and SHA of a file from GitHub."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        content = base64.b64decode(response.json()['content']).decode('utf-8')
        sha = response.json()['sha']
        return content, sha
    except requests.exceptions.RequestException as e:
        st.warning(f"Error fetching file '{path}' from GitHub: {e}. Assuming empty/default.")
        if response is not None and response.status_code == 404:
             st.info(f"File '{path}' not found on GitHub. Will create it on first save.")
             return None, None # File not found
        return None, None # Other error
    except Exception as e:
        st.error(f"An unexpected error occurred fetching file '{path}': {e}")
        return None, None


def save_to_github(owner, repo, path, file_content_str, commit_message, headers):
    """Saves/updates a file on GitHub."""
    _, current_sha = get_github_file_content(owner, repo, path, headers)

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    encoded_content = base64.b64encode(file_content_str.encode('utf-8')).decode('utf-8')

    payload = {
        "message": commit_message,
        "content": encoded_content,
        "branch": "main" # Or your default branch
    }
    if current_sha:
        payload["sha"] = current_sha # Add SHA if updating existing file

    try:
        response = requests.put(url, headers=headers, json=payload)
        response.raise_for_status()
        st.success(f"Successfully saved '{path}' to GitHub.")
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Error saving file '{path}' to GitHub: {e}")
        if response is not None:
            st.error(f"GitHub API response: {response.text}")
        return False
    except Exception as e:
        st.error(f"An unexpected error occurred saving file '{path}': {e}")
        return False

# -------------------------------
# Data Handling
# -------------------------------
# @st.cache_data # Caching might be complex with GitHub reads/writes, let's disable for now
def load_data(owner, repo, path, headers):
    """Loads product data from GitHub."""
    st.info(f"Loading '{path}' from GitHub...")
    content, _ = get_github_file_content(owner, repo, path, headers)
    if content:
        try:
            # Use io.StringIO to read the string content as a file
            df = pd.read_csv(io.StringIO(content))
            st.info(f"Loaded {len(df)} products from GitHub.")
            return df
        except pd.errors.EmptyDataError:
            st.warning(f"'{path}' on GitHub is empty. Returning empty DataFrame.")
            return pd.DataFrame() # Return empty DataFrame if CSV is empty
        except Exception as e:
            st.error(f"Error parsing '{path}' from GitHub: {e}")
            return pd.DataFrame()
    else:
        # If file doesn't exist or error occurred, return empty DataFrame
        # Define columns expected by the rest of the app to avoid errors downstream
        expected_columns = [
            'title', 'uri', 'raw_ec_thumbnails', 'raw_ec_shortdesc',
            'raw_lcbo_tastingnotes', 'raw_lcbo_region_name', 'raw_country_of_manufacture',
            'raw_lcbo_program', 'raw_created_at', 'raw_is_buyable', 'raw_ec_price',
            'raw_ec_promo_price', # Added
            'raw_ec_final_price', 'raw_lcbo_unit_volume',
            'raw_lcbo_alcohol_percent', 'raw_lcbo_sugar_gm_per_ltr',
            'raw_lcbo_bottles_per_pack', 'raw_sysconcepts', 'raw_ec_category',
            'raw_ec_category_filter', 'raw_lcbo_varietal_name', 'raw_stores_stock',
            'raw_stores_stock_combined', 'raw_stores_low_stock_combined',
            'raw_stores_low_stock', 'raw_out_of_stock', 'stores_inventory',
            'raw_online_inventory', 'raw_avg_reviews', 'raw_ec_rating',
            'weighted_rating', 'raw_view_rank_yearly', 'raw_view_rank_monthly',
            'raw_sell_rank_yearly', 'raw_sell_rank_monthly'
        ]
        return pd.DataFrame(columns=expected_columns)

# @st.cache_data # Disable caching for consistency with GitHub writes
def load_favorites(owner, repo, path, headers):
    """Loads favorite URIs from GitHub."""
    st.info("Loading favorites from GitHub...")
    content, _ = get_github_file_content(owner, repo, path, headers)
    if content:
        try:
            df_fav = pd.read_csv(io.StringIO(content))
            if 'uri' in df_fav.columns:
                 # Use a set for efficient lookup
                favorites_set = set(df_fav['uri'].astype(str).tolist())
                st.info(f"Loaded {len(favorites_set)} favorites.")
                return favorites_set
            else:
                st.warning(f"'{path}' on GitHub does not contain a 'uri' column.")
                return set()
        except pd.errors.EmptyDataError:
             st.info(f"'{path}' on GitHub is empty. No favorites loaded.")
             return set()
        except Exception as e:
            st.error(f"Error parsing favorites file '{path}': {e}")
            return set()
    else:
        # File not found or error
        return set()

def save_favorites_to_github(favorites_set, owner, repo, path, headers):
    """Saves the current set of favorite URIs to GitHub."""
    if not favorites_set:
        df_fav = pd.DataFrame(columns=['uri'])
    else:
        df_fav = pd.DataFrame(list(favorites_set), columns=['uri'])

    csv_string = df_fav.to_csv(index=False, encoding='utf-8-sig')
    commit_message = f"Update favorites list ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
    save_to_github(owner, repo, path, csv_string, commit_message, headers)


# --- (Keep load_food_items as is, assuming it's a local static file) ---
@st.cache_data
def load_food_items():
    try:
        # Assuming food_items.csv is bundled with your app or in the repo locally
        food_items = pd.read_csv('food_items.csv')
        return food_items
    except Exception as e:
        st.error(f"Error loading local food items: {e}")
        return pd.DataFrame(columns=['Category', 'FoodItem'])

# --- (Keep sort_data as is) ---
def sort_data(data, column):
    # Ensure the sort column exists before sorting
    if column in data.columns:
        # Attempt numeric conversion for sorting if possible, handle errors
        numeric_col = pd.to_numeric(data[column], errors='coerce')
        if not numeric_col.isna().all(): # Check if conversion was successful for at least one value
            # Create temporary sort key to handle NaNs (place them last)
            sort_key = numeric_col.fillna(float('-inf')) # Put NaNs at the bottom for descending
            sorted_data = data.loc[sort_key.sort_values(ascending=False).index]
        else: # If not numeric or all NaNs, sort as object type
             # Sort non-na values first, then na values (often placed at end by default)
             sorted_data = data.sort_values(by=column, ascending=False, na_position='last')
    else:
        st.warning(f"Sort column '{column}' not found in data. Skipping sort.")
        sorted_data = data
    return sorted_data


# -------------------------------
# Filter functions
# -------------------------------
def search_data(data, search_text):
    if search_text:
        # Ensure 'title' column exists and handle potential NaN values
        if 'title' in data.columns:
            data = data[data['title'].str.contains(search_text, case=False, na=False)]
        else:
            st.warning("Column 'title' not found for searching.")
    return data

def sort_data_filter(data, sort_by):
    sort_column_map = {
        '# of reviews': 'raw_avg_reviews',
        'Rating': 'raw_ec_rating',
        'Top Viewed - Year': 'raw_view_rank_yearly',
        'Top Veiwed - Month': 'raw_view_rank_monthly', # Typo corrected 'Veiwed' -> 'Viewed'
        'Top Seller - Year': 'raw_sell_rank_yearly',
        'Top Seller - Month': 'raw_sell_rank_monthly'
    }
    ascending_map = {
        '# of reviews': False,
        'Rating': False,
        'Top Viewed - Year': True,
        'Top Veiwed - Month': True, # Typo corrected 'Veiwed' -> 'Viewed'
        'Top Seller - Year': True,
        'Top Seller - Month': True
    }

    if sort_by in sort_column_map:
        column = sort_column_map[sort_by]
        ascending = ascending_map[sort_by]
        if column in data.columns:
             # Convert to numeric for proper sorting, coercing errors
            data[column] = pd.to_numeric(data[column], errors='coerce')
            # Handle NaNs depending on ascending/descending
            na_position = 'first' if ascending else 'last'
            data = data.sort_values(by=column, ascending=ascending, na_position=na_position)
        else:
            st.warning(f"Sort column '{column}' for '{sort_by}' not found.")
    else: # Default to weighted rating
        data = sort_data(data, 'weighted_rating') # Use the existing sort_data function
    return data


def filter_data(data, country='All Countries', region='All Regions', varietal='All Varietals',
                exclude_usa=False, in_stock=False, only_vintages=False, on_sale=False, # Added on_sale
                favourites_only=False, current_favorites=None, store='Select Store'): # Added favourites
    """Applies filters to the DataFrame."""
    df_filtered = data.copy() # Start with a copy

    if country != 'All Countries' and 'raw_country_of_manufacture' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['raw_country_of_manufacture'] == country]
    if region != 'All Regions' and 'raw_lcbo_region_name' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['raw_lcbo_region_name'] == region]
    if varietal != 'All Varietals' and 'raw_lcbo_varietal_name' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['raw_lcbo_varietal_name'] == varietal]
    # Store filter is handled during data refresh/load now, but keeping structure if needed later
    # if store != 'Select Store' and 'store_name' in df_filtered.columns:
    #     df_filtered = df_filtered[df_filtered['store_name'] == store]
    if in_stock and 'stores_inventory' in df_filtered.columns:
         # Ensure numeric conversion and handle potential errors/NaNs
         inventory_numeric = pd.to_numeric(df_filtered['stores_inventory'], errors='coerce').fillna(0)
         df_filtered = df_filtered[inventory_numeric > 0]
    if only_vintages and 'raw_lcbo_program' in df_filtered.columns:
        # Ensure the column is string type before using .str accessor
        df_filtered = df_filtered[df_filtered['raw_lcbo_program'].astype(str).str.contains("Vintages", regex=False, na=False)] # Simplified regex
    if exclude_usa and 'raw_country_of_manufacture' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['raw_country_of_manufacture'] != 'United States']

    # --- New Filters ---
    if on_sale and 'raw_ec_promo_price' in df_filtered.columns:
        # Check for non-null, non-'N/A', non-empty promo price
        # Convert to numeric, treat errors (like 'N/A') as NaN, fill NaN with 0, check if > 0
        promo_price_numeric = pd.to_numeric(df_filtered['raw_ec_promo_price'], errors='coerce').fillna(0)
        df_filtered = df_filtered[promo_price_numeric > 0]

    if favourites_only and 'uri' in df_filtered.columns and current_favorites is not None:
        df_filtered = df_filtered[df_filtered['uri'].isin(current_favorites)]

    return df_filtered

# --- (Keep transform_image_url as is) ---
def transform_image_url(url, new_size):
    if not isinstance(url, str):
        return url
    return re.sub(r"\d+\.\d+\.(png|PNG)$", new_size, url)

# -------------------------------
# Refresh function
# -------------------------------
def refresh_data(store_id=None, owner=GITHUB_REPO_OWNER, repo=GITHUB_REPO_NAME, path=PRODUCTS_CSV_PATH, headers=GITHUB_HEADERS):
    """Fetches data from LCBO API, processes it, saves locally and to GitHub."""
    current_time = datetime.now()
    st.info(f"Refreshing data from LCBO API ({'Store ID: ' + store_id if store_id else 'All Stores'})...")
    with st.spinner("Fetching data from LCBO API..."): # Add spinner

        # --- (Keep API URL, Headers, Initial Payload structure) ---
        # **SECURITY NOTE:** The Bearer token below is still hardcoded.
        # Replace this with st.secrets["LCBO_API_KEY"] or similar if you store it there.
        # For now, using the placeholder from the original code.
        lcbo_api_key = "xx883b5583-07fb-416b-874b-77cce565d927" # Replace with your actual LCBO API key if different/needed
        lcbo_headers = {
            "User-Agent": "StreamlitWineApp/1.0", # Example User Agent
            "Accept": "application/json",
            "Authorization": f"Bearer {lcbo_api_key}",
            "Content-Type": "application/json",
            "Referer": "https://www.lcbo.com/" # Keep Referer
        }
        url = "https://platform.cloud.coveo.com/rest/search/v2?organizationId=lcboproduction2kwygmc"

        initial_payload = {
            "q": "",
            "tab": "clp-products-wine-red_wine",
            "sort": "ec_rating descending", # Or keep another default sort?
            "facets": [
                {
                    "field": "ec_rating",
                    "currentValues": [
                        {
                            "value": "4..5inc", # Keep 4-5 star filter
                            "state": "selected"
                        }
                    ]
                }
            ],
            "numberOfResults": 500, # Max results per page
            "firstResult": 0,
            "aq": "@ec_visibility==(2,4) @cp_Browse_category_deny<>0 @ec_category==\"Products|Wine|Red Wine\" (@ec_rating==5..5 OR @ec_rating==4..4.9)"
        }

        dictionaryFieldContext = {} # Initialize empty context
        if store_id:
            dictionaryFieldContext = {
                "stores_stock": "",
                "stores_inventory": store_id,
                "stores_stock_combined": store_id,
                "stores_low_stock_combined": store_id
            }
            # Update payload ONLY if store_id is provided
            initial_payload["context"] = {"dictionaryFieldContext": dictionaryFieldContext}


        all_items = []
        total_count = 0

        # --- API Fetching Loop ---
        try:
            # Initial Request
            response = requests.post(url, headers=lcbo_headers, json=initial_payload)
            response.raise_for_status()
            data = response.json()

            if 'results' in data:
                all_items.extend(data['results'])
                total_count = data.get('totalCount', 0)
                st.info(f"Initial fetch: {len(all_items)} items. Total expected: {total_count}")

                # Pagination if needed
                num_fetched = len(all_items)
                while num_fetched < total_count:
                    st.info(f"Fetching next batch (starting from {num_fetched})...")
                    next_payload = initial_payload.copy()
                    next_payload["firstResult"] = num_fetched
                    # Ensure context is included in subsequent requests if needed
                    if store_id:
                         next_payload["context"] = {"dictionaryFieldContext": dictionaryFieldContext}

                    response = requests.post(url, headers=lcbo_headers, json=next_payload)
                    response.raise_for_status()
                    data = response.json()

                    if 'results' in data and data['results']:
                        all_items.extend(data['results'])
                        num_fetched = len(all_items)
                        st.info(f"Fetched batch. Total items now: {num_fetched}")
                    else:
                        st.warning("No more results found or error in subsequent fetch.")
                        break # Exit loop if no results or error
                    time.sleep(0.5) # Shorter sleep, adjust if needed

            else:
                st.error(f"Key 'results' not found in the initial API response. Response: {data}")
                return None # Indicate failure

        except requests.exceptions.RequestException as e:
            st.error(f"API request failed: {e}")
            if response is not None:
                st.error(f"API Response Status: {response.status_code}")
                st.error(f"API Response Text: {response.text[:500]}...") # Show partial text
            return None # Indicate failure
        except Exception as e:
             st.error(f"An unexpected error occurred during API fetch: {e}")
             return None

    # --- Data Processing ---
    with st.spinner("Processing fetched data..."):
        products = []
        for product in all_items:
            raw_data = product.get('raw', {}) # Use .get for safety
            if not raw_data: continue # Skip if no raw data

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
                'raw_ec_promo_price': raw_data.get('ec_promo_price', 'N/A'), # *** ADDED ***
                'raw_ec_final_price': raw_data.get('ec_final_price', 'N/A'),
                'raw_lcbo_unit_volume': raw_data.get('lcbo_unit_volume', 'N/A'),
                'raw_lcbo_alcohol_percent': raw_data.get('lcbo_alcohol_percent', 'N/A'),
                'raw_lcbo_sugar_gm_per_ltr': raw_data.get('lcbo_sugar_gm_per_ltr', 'N/A'),
                'raw_lcbo_bottles_per_pack': raw_data.get('lcbo_bottles_per_pack', 'N/A'),
                'raw_sysconcepts': raw_data.get('sysconcepts', 'N/A'), # Needed for food pairing
                'raw_ec_category': raw_data.get('ec_category', 'N/A'),
                'raw_ec_category_filter': raw_data.get('ec_category_filter', 'N/A'),
                'raw_lcbo_varietal_name': raw_data.get('lcbo_varietal_name', 'N/A'),
                # Inventory fields might be nested differently or named based on store context
                'stores_inventory': raw_data.get('stores_inventory', raw_data.get(f'stores_inventory_{store_id}', 0)) if store_id else raw_data.get('stores_inventory', 0), # Handle store-specific vs general
                'raw_online_inventory': raw_data.get('online_inventory', 0),
                'raw_avg_reviews': raw_data.get('avg_reviews', 0),
                'raw_ec_rating': raw_data.get('ec_rating', 0),
                'weighted_rating': 0.0, # Placeholder
                # Rank fields - check names in API response if needed
                'raw_view_rank_yearly': raw_data.get('view_rank_yearly', 'N/A'),
                'raw_view_rank_monthly': raw_data.get('view_rank_monthly', 'N/A'),
                'raw_sell_rank_yearly': raw_data.get('sell_rank_yearly', 'N/A'),
                'raw_sell_rank_monthly': raw_data.get('sell_rank_monthly', 'N/A')
                 # Add other potentially useful fields if available in `raw_data`
                #'raw_out_of_stock': raw_data.get('out_of_stock', 'N/A'),
            }
            products.append(product_info)

        if not products:
             st.warning("No product information could be processed.")
             return pd.DataFrame() # Return empty df

        df_products = pd.DataFrame(products)

        # --- Weighted Rating Calculation (ensure numeric conversion) ---
        R = pd.to_numeric(df_products['raw_ec_rating'], errors='coerce')
        v = pd.to_numeric(df_products['raw_avg_reviews'], errors='coerce')

        # Calculate mean rating (C) only from items that have reviews (v > 0)
        # and valid ratings (R is not NaN)
        valid_ratings_for_mean = R[v > 0].dropna()
        mean_rating = valid_ratings_for_mean.mean() if not valid_ratings_for_mean.empty else 3.0 # Default C if no reviews

        minimum_votes = 10 # m

        # Fill NaN values in R and v with 0 for calculation purposes
        R_filled = R.fillna(0)
        v_filled = v.fillna(0)

        # Calculate weighted rating
        df_products['weighted_rating'] = (v_filled / (v_filled + minimum_votes)) * R_filled + \
                                         (minimum_votes / (v_filled + minimum_votes)) * mean_rating

        # Ensure 'uri' column exists and is suitable as key
        if 'uri' not in df_products.columns:
            st.error("Critical Error: 'uri' column missing from processed data. Favorites will not work.")
            # As fallback, try creating a key from title, but this is less reliable
            if 'title' in df_products.columns:
                df_products['uri'] = df_products['title'].str.replace(' ', '-').str.lower()
                st.warning("Using generated URI from title as fallback.")
            else:
                 return None # Cannot proceed without a unique key


    # --- Save to GitHub ---
    with st.spinner(f"Saving {len(df_products)} products to GitHub..."):
        csv_string = df_products.to_csv(index=False, encoding='utf-8-sig')
        commit_message = f"Update product data ({'Store: ' + store_id if store_id else 'All Stores'}) - {current_time.strftime('%Y-%m-%d %H:%M:%S')}"
        save_to_github(owner, repo, path, csv_string, commit_message, headers)

    st.success(f"Data refreshed and saved successfully! ({len(df_products)} products)")
    return df_products # Return the newly fetched DataFrame


# -------------------------------
# Main Streamlit App
# -------------------------------
def main():
    st.set_page_config(layout="wide") # Use wider layout
    st.title("🍷 LCBO Wine Find")

    # --- Load Initial Data & Favorites ---
    # Load favorites first, store in session state
    if 'favorites' not in st.session_state:
        st.session_state.favorites = load_favorites(GITHUB_REPO_OWNER, GITHUB_REPO_NAME, FAVORITES_CSV_PATH, GITHUB_HEADERS)

    # Load product data
    # Determine if a refresh is needed based on store selection change
    trigger_refresh = False
    if 'selected_store' not in st.session_state:
        st.session_state.selected_store = 'Select Store' # Initial state
        st.session_state.loaded_data_store = 'Select Store' # Track what data is loaded
        # Load initial data on first run
        data = load_data(GITHUB_REPO_OWNER, GITHUB_REPO_NAME, PRODUCTS_CSV_PATH, GITHUB_HEADERS)
        st.session_state.current_data = data # Store initial data
    else:
        # Check later if store selection actually changes
        pass


    # --- Sidebar ---
    st.sidebar.header("Store Selection")
    store_options = ['Select Store', 'Bradford', 'E. Gwillimbury', 'Upper Canada', 'Yonge & Eg', 'Dufferin & Steeles']
    store_ids = { # Keep your store IDs
        "Bradford": "145",
        "E. Gwillimbury": "391",
        "Upper Canada": "226",
        "Yonge & Eg": "457",
        "Dufferin & Steeles": "618"
    }
    # Use session state value for selectbox default
    selected_store = st.sidebar.selectbox("Store", options=store_options, key='selected_store_widget')

    # --- Refresh Logic ---
    # Check if store selection changed compared to the data we currently have loaded
    if selected_store != st.session_state.get('loaded_data_store', 'Select Store'):
        st.info(f"Store selection changed to: {selected_store}. Refreshing data...")
        st.session_state.selected_store = selected_store # Update session state tracking selection
        store_id_to_refresh = store_ids.get(selected_store) if selected_store != 'Select Store' else None
        # Call refresh_data - it now saves to GitHub and returns the new data
        refreshed_data = refresh_data(store_id=store_id_to_refresh)
        if refreshed_data is not None and not refreshed_data.empty:
            st.session_state.current_data = refreshed_data
            st.session_state.loaded_data_store = selected_store # Update the store context of loaded data
            st.rerun() # Rerun to apply filters to the *new* data immediately
        else:
            st.error("Data refresh failed. Displaying previously loaded data or empty view.")
            # Keep existing data or load default if refresh fails badly
            st.session_state.current_data = st.session_state.get('current_data', load_data(GITHUB_REPO_OWNER, GITHUB_REPO_NAME, PRODUCTS_CSV_PATH, GITHUB_HEADERS))
            # Optionally reset loaded_data_store if refresh failed?
            # st.session_state.loaded_data_store = 'Select Store' # Or keep the attempted store?
    else:
         # If store didn't change, ensure data exists in session state
         if 'current_data' not in st.session_state:
              st.session_state.current_data = load_data(GITHUB_REPO_OWNER, GITHUB_REPO_NAME, PRODUCTS_CSV_PATH, GITHUB_HEADERS)


    # Use the data stored in session state for filtering
    data = st.session_state.current_data

    # --- Check if data is empty ---
    if data is None or data.empty:
        st.warning("No product data loaded. Please select a store or check GitHub connection.")
        st.stop() # Stop execution if no data


    # --- Sidebar Filters (Applied to st.session_state.current_data) ---
    st.sidebar.header("Filter Options 🔍")
    search_text = st.sidebar.text_input("Search Title", value="")
    sort_by = st.sidebar.selectbox("Sort by",
                                   ['Weighted Rating', '# of reviews', 'Rating', # Default first
                                    'Top Viewed - Year', 'Top Viewed - Month', # Corrected typo
                                    'Top Seller - Year', 'Top Seller - Month'])

    # Create filter options from *current* data
    # Use .astype(str) and .dropna() to handle potential non-string or NaN values gracefully
    country_options = ['All Countries'] + sorted(data['raw_country_of_manufacture'].astype(str).dropna().unique().tolist()) if 'raw_country_of_manufacture' in data.columns else ['All Countries']
    region_options = ['All Regions'] + sorted(data['raw_lcbo_region_name'].astype(str).dropna().unique().tolist()) if 'raw_lcbo_region_name' in data.columns else ['All Regions']
    varietal_options = ['All Varietals'] + sorted(data['raw_lcbo_varietal_name'].astype(str).dropna().unique().tolist()) if 'raw_lcbo_varietal_name' in data.columns else ['All Varietals']

    # Food Pairing Filter
    food_items = load_food_items() # Load food items (cached)
    if not food_items.empty:
        categories = sorted(food_items['Category'].unique())
        food_options = ['All Dishes'] + categories
        food_category = st.sidebar.selectbox("Food Category", options=food_options)
    else:
        food_category = 'All Dishes' # Default if food items failed to load

    country = st.sidebar.selectbox("Country", options=country_options)
    region = st.sidebar.selectbox("Region", options=region_options)
    varietal = st.sidebar.selectbox("Varietal", options=varietal_options)

    st.sidebar.markdown("---") # Separator

    # Checkbox Filters
    exclude_usa = st.sidebar.checkbox("Exclude USA", value=False)
    in_stock = st.sidebar.checkbox("In Stock Only (Selected Store)", value=False) # Clarify based on store selection
    only_vintages = st.sidebar.checkbox("Only Vintages", value=False)
    on_sale = st.sidebar.checkbox("On Sale Only", value=False) # *** ADDED ***
    only_favs = st.sidebar.checkbox("Favourites Only", value=False) # *** ADDED ***


    # --- Apply Filters and Sorting ---
    filtered_data = data.copy() # Start with current data

    # Apply text search first
    filtered_data = search_data(filtered_data, search_text)

    # Apply checkbox/select filters
    filtered_data = filter_data(filtered_data, country=country, region=region, varietal=varietal,
                                exclude_usa=exclude_usa, in_stock=in_stock,
                                only_vintages=only_vintages, on_sale=on_sale,
                                favourites_only=only_favs,
                                current_favorites=st.session_state.favorites, # Pass current favs
                                store=st.session_state.selected_store)

    # Food Category Filtering (apply after other filters)
    if food_category != 'All Dishes' and 'raw_sysconcepts' in filtered_data.columns and not food_items.empty:
        selected_items = food_items[food_items['Category'] == food_category]['FoodItem'].str.lower().tolist()
        # Handle NaN in raw_sysconcepts by filling with empty string
        concepts_lower = filtered_data['raw_sysconcepts'].fillna('').astype(str).str.lower()
        # Keep rows where any of the selected food items are found in the concepts string
        mask = concepts_lower.apply(lambda x: any(item in x for item in selected_items))
        filtered_data = filtered_data[mask]

    # Apply Sorting (apply last)
    sort_option = sort_by if sort_by != 'Sort by' else 'Weighted Rating' # Default sort
    if sort_option == 'Weighted Rating':
         filtered_data = sort_data(filtered_data, 'weighted_rating') # Use default weighted sort
    else:
         filtered_data = sort_data_filter(filtered_data, sort_option) # Use specific sort


    st.write(f"Showing **{len(filtered_data)}** products matching filters.")
    st.write(f"Data loaded for store: **{st.session_state.loaded_data_store}**")
    st.markdown("---")


    # --- Pagination ---
    page_size = 10
    total_products = len(filtered_data)
    total_pages = (total_products // page_size) + (1 if total_products % page_size > 0 else 0)

    if total_pages > 0:
        # Ensure page number stays within bounds
        if 'page' not in st.session_state:
             st.session_state.page = 1
        page = st.number_input("Page", min_value=1, max_value=max(1, total_pages), step=1, key='page')
    else:
        page = 1
        st.write("No products to display based on current filters.")

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_data = filtered_data.iloc[start_idx:end_idx]


    # --- Display Products ---
    for idx, row in page_data.iterrows():
        # Ensure 'uri' exists for keying and favoriting
        product_uri = row.get('uri', f"missing-uri-{idx}")
        if product_uri == 'N/A' or not product_uri:
             product_uri = f"generated-uri-{idx}" # Fallback URI

        # Use columns for layout: Title + Fav Button | Details | Image
        col_title_fav, col_details, col_image = st.columns([3, 4, 2]) # Adjust ratios as needed

        with col_title_fav:
            st.markdown(f"##### {row.get('title', 'N/A')}") # Smaller heading
            is_favorited = product_uri in st.session_state.favorites
            button_label = "❤️ Favourited" if is_favorited else "🤍 Favourite"
            button_help = "Remove from Favourites" if is_favorited else "Add to Favourites"
            # Use a unique key for each button based on URI
            if st.button(button_label, key=f"fav_{product_uri}", help=button_help):
                if is_favorited:
                    st.session_state.favorites.remove(product_uri)
                    st.success(f"Removed '{row.get('title', 'Product')}' from favourites.")
                else:
                    st.session_state.favorites.add(product_uri)
                    st.success(f"Added '{row.get('title', 'Product')}' to favourites.")
                # Save favorites to GitHub
                save_favorites_to_github(st.session_state.favorites, GITHUB_REPO_OWNER, GITHUB_REPO_NAME, FAVORITES_CSV_PATH, GITHUB_HEADERS)
                st.rerun() # Rerun to update button state and filter if active

        with col_details:
             # --- Price Display ---
            price_str = ""
            reg_price = row.get('raw_ec_price')
            promo_price = row.get('raw_ec_promo_price')

            # Convert prices to numeric for comparison/display formatting
            try:
                 reg_price_num = float(reg_price) if reg_price not in ['N/A', None, ''] else None
            except (ValueError, TypeError):
                 reg_price_num = None

            try:
                 promo_price_num = float(promo_price) if promo_price not in ['N/A', None, ''] else None
            except (ValueError, TypeError):
                 promo_price_num = None

            if promo_price_num is not None and promo_price_num > 0:
                 # If promo price exists, show it prominently
                 price_str = f"**SALE: ${promo_price_num:.2f}** "
                 if reg_price_num is not None and reg_price_num != promo_price_num:
                     # Show regular price struck through if different
                     price_str += f" (~~${reg_price_num:.2f}~~)"
                 elif reg_price_num is None:
                      price_str += " (Regular price unavailable)"
            elif reg_price_num is not None:
                 # Otherwise, show regular price
                 price_str = f"**Price:** ${reg_price_num:.2f}"
            else:
                 price_str = "**Price:** N/A"

            st.markdown(price_str)

            # --- Rating and Reviews ---
            rating = pd.to_numeric(row.get('raw_ec_rating'), errors='coerce')
            reviews = pd.to_numeric(row.get('raw_avg_reviews'), errors='coerce')
            rating_str = f"{rating:.1f} ⭐" if pd.notna(rating) else "N/A"
            reviews_str = f"{int(reviews)} Reviews" if pd.notna(reviews) else "0 Reviews"
            st.markdown(f"**Rating:** {rating_str} | **Reviews:** {reviews_str}")

            # --- Other Quick Details ---
            country_man = row.get('raw_country_of_manufacture', 'N/A')
            region_name = row.get('raw_lcbo_region_name', 'N/A')
            varietal_name = row.get('raw_lcbo_varietal_name', 'N/A')
            st.markdown(f"**Origin:** {country_man} / {region_name}")
            st.markdown(f"**Varietal:** {varietal_name}")


        with col_image:
            # Display the thumbnail image and enlarge popover
            thumbnail_url = row.get('raw_ec_thumbnails', None)
            if pd.notna(thumbnail_url) and isinstance(thumbnail_url, str) and thumbnail_url != 'N/A':
                 st.image(thumbnail_url, width=100) # Smaller thumbnail
                 with st.popover("Enlarge"):
                     large_image_url = transform_image_url(thumbnail_url, "1280.1280.png") # Use 1280 for popover
                     st.image(large_image_url, use_container_width=True)
            # else:
            #     st.caption("No image") # Keep it clean if no image

        # --- Expander for Full Details ---
        with st.expander("More Details"):
            st.markdown(f"**Title:** {row.get('title', 'N/A')}")
            st.markdown(f"**LCBO URL:** [{row.get('uri', 'N/A')}]({row.get('uri', '#')})") # Make it clickable
            st.markdown(f"**Description:** {row.get('raw_ec_shortdesc', 'N/A')}")
            st.markdown(f"**Tasting Notes:** {row.get('raw_lcbo_tastingnotes', 'N/A')}")
            st.markdown(f"**Program:** {row.get('raw_lcbo_program', 'N/A')}")
            st.markdown(f"**Size:** {row.get('raw_lcbo_unit_volume', 'N/A')}")
            st.markdown(f"**Alcohol %:** {row.get('raw_lcbo_alcohol_percent', 'N/A')}")
            st.markdown(f"**Sugar (g/L):** {row.get('raw_lcbo_sugar_gm_per_ltr', 'N/A')}")
            st.markdown(f"**Store Inventory (Selected):** {row.get('stores_inventory', 'N/A')}") # Re-check field name if needed
            st.markdown(f"**Weighted Rating Score:** {row.get('weighted_rating', 0.0):.4f}")
            st.markdown(f"**Monthly Sold Rank:** {row.get('raw_sell_rank_monthly', 'N/A')}")
            st.markdown(f"**Monthly View Rank:** {row.get('raw_view_rank_monthly', 'N/A')}")
            st.markdown(f"**Yearly Sold Rank:** {row.get('raw_sell_rank_yearly', 'N/A')}")
            st.markdown(f"**Yearly View Rank:** {row.get('raw_view_rank_yearly', 'N/A')}")
            # st.markdown(f"**Raw SysConcepts (for Food):** {row.get('raw_sysconcepts', 'N/A')}") # Optional: for debugging food pairing

        st.markdown("---") # Separator between products

# --- Run the app ---
if __name__ == "__main__":
    main()
