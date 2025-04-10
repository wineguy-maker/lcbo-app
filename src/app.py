# Corrected version of filter_and_sort_data

def filter_and_sort_data(data, sort_by, **filters):
    """Combine filtering and sorting."""
    if data is None or data.empty:
        return pd.DataFrame() # Return empty if no input data

    # --- CORRECTED SECTION START ---
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
    #    THIS IS LIKELY THE LINE CAUSING THE ERROR IF NOT CORRECTED (around line 229 in your file context)
    data = filter_data(data, **filter_data_args)
    # --- CORRECTED SECTION END ---

    # 3. Apply search filter separately using the dedicated search_data function
    search_text = filters.get('search_text', '') # Get search_text from the original filters dict
    data = search_data(data, search_text)

    # 4. Apply sorting
    data = sort_data_filter(data, sort_by)
    return data

