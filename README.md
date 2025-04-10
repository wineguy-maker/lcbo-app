# WineFind Project

## Overview
WineFind is a Streamlit application designed to help users discover and manage their favorite wines. The application allows users to filter wines based on various criteria, view detailed product information, and manage a personalized list of favorite wines.

## Features
- **User Authentication**: Secure access to the favorites feature using a PIN.
- **Product Filtering**: Filter wines by country, region, varietal, and more.
- **Favorites Management**: Add or remove wines from your favorites list.
- **Product Display**: View detailed information about each wine, including ratings and reviews.

## Project Structure
```
WineFind
├── src
│   ├── app.py                # Main entry point of the application
│   ├── utils
│   │   ├── auth.py           # User authentication functions
│   │   ├── data.py           # Data loading and saving operations
│   │   └── favorites.py       # Favorites management functions
│   └── components
│       ├── filters.py         # Filter component for the application
│       └── product_display.py  # Product information display
├── data
│   ├── favourites.json        # User's favorite products
│   └── products.csv           # Product data
├── requirements.txt           # Project dependencies
├── README.md                  # Project documentation
└── .gitignore                 # Files to ignore in version control
```

## Installation
1. Clone the repository:
   ```
   git clone <repository-url>
   cd WineFind
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage
1. Run the application:
   ```
   streamlit run src/app.py
   ```

2. Enter your PIN to access the favorites feature.

3. Use the filters to find wines that match your preferences.

4. Click on a wine to view its details and add it to your favorites.

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for details.