import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
import requests

# -------------------------------
# Data Handling (data_handler.py)
# -------------------------------
@st.cache_data
def load_data(file_path):
    df = pd.read_csv(file_path)
    return df

def sort_data(data, column):
    sorted_data = data.sort_values(by=column, ascending=False)
    return sorted_data

# -------------------------------
# Filter functions (filter.py)
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
    elif sort_by == 'Yearly Views':
        data = data.sort_values(by='raw_yearly_views', ascending=False)
    elif sort_by == 'Monthly Views':
        data = data.sort_values(by='raw_monthly_views', ascending=False)
    elif sort_by == 'Yearly Sold':
        data = data.sort_values(by='raw_yearly_sold', ascending=False)
    elif sort_by == 'Monthly Sold':
        data = data.sort_values(by='raw_monthly_sold', ascending=False)
    else:
        data = data.sort_values(by='weighted_rating', ascending=False)
    return data

def filter_data(data, country='Select Country', region='Select Region', varietal='Select Varietal', in_stock=False, only_vintages=False):
    if country != 'Select Country':
        data = data[data['raw_country_of_manufacture'] == country]
    if region != 'Select Region':
        data = data[data['raw_lcbo_region_name'] == region]
    if varietal != 'Select Varietal':
        data = data[data['raw_lcbo_varietal_name'] == varietal]
    if in_stock:
        data = data[data['stores_inventory'] > 0]
    if only_vintages:
        data = data[data['raw_lcbo_program'].str.contains(r"['\"]Vintages['\"]", regex=True, na=False)]
    return data

# -------------------------------
# Refresh function (refresh_data.py)
# -------------------------------
def refresh_data(store_id=None):
    st.info("Refreshing data from API...")
    time.sleep(2)  # Simulate a delay; replace with your API logic if needed.
    st.success("Data refreshed!")
    return load_data("products.csv")

# -------------------------------
# Main Streamlit App
# -------------------------------
def main():
    st.title("LCBO Wine Filter")

    # Load data from CSV
    data = load_data("products.csv")

    # Sidebar Filters
    st.sidebar.header("Filters")
    search_text = st.sidebar.text_input("Search", value="")
    sort_by = st.sidebar.selectbox("Sort by", ['Sort by', '# of reviews', 'Rating', 'Yearly Views', 'Monthly Views', 'Yearly Sold', 'Monthly Sold'])

    # Create filter options from the data
    country_options = ['Select Country'] + sorted(data['raw_country_of_manufacture'].dropna().unique().tolist())
    region_options = ['Select Region'] + sorted(data['raw_lcbo_region_name'].dropna().unique().tolist())
    varietal_options = ['Select Varietal'] + sorted(data['raw_lcbo_varietal_name'].dropna().unique().tolist())

    country = st.sidebar.selectbox("Country", options=country_options)
    region = st.sidebar.selectbox("Region", options=region_options)
    varietal = st.sidebar.selectbox("Varietal", options=varietal_options)
    in_stock = st.sidebar.checkbox("In Stock Only", value=False)
    only_vintages = st.sidebar.checkbox("Only Vintages", value=False)

    # Refresh Data Button
    if st.sidebar.button("Refresh Data"):
        data = refresh_data()  # Refresh and reload the data

    # -----------------------------------------------------------
    # Apply Filters and Sorting
    # -----------------------------------------------------------
    filtered_data = data.copy()
    filtered_data = filter_data(filtered_data, country=country, region=region, varietal=varietal,
                                  in_stock=in_stock, only_vintages=only_vintages)
    filtered_data = search_data(filtered_data, search_text)
    sort_option = sort_by if sort_by != 'Sort by' else 'weighted_rating'
    if sort_option != 'weighted_rating':
        filtered_data = sort_data_filter(filtered_data, sort_option)
    else:
        filtered_data = sort_data(filtered_data, sort_option)

    st.write(f"Showing **{len(filtered_data)}** products")

    # -----------------------------------------------------------
    # Pagination (adjust page size as needed)
    # -----------------------------------------------------------
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

    # -----------------------------------------------------------
    # Displaying Products
    # -----------------------------------------------------------
    for idx, row in page_data.iterrows():
        st.markdown(f"### {row['title']}")
        st.markdown(f"**Price:** ${row.get('raw_ec_price', 'N/A')} | **Rating:** {row.get('raw_ec_rating', 'N/A')} | **Reviews:** {row.get('raw_avg_reviews', 'N/A')}")
        if pd.notna(row.get('raw_ec_thumbnails', None)) and row.get('raw_ec_thumbnails', 'N/A') != 'N/A':
            st.image(row['raw_ec_thumbnails'], width=150)
        st.markdown("---")

if __name__ == "__main__":
    main()