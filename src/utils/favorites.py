def load_favourites():
    """Load favourites from the JSON file."""
    try:
        with open("data/favourites.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_favourites(favourites):
    """Save favourites to the JSON file."""
    with open("data/favourites.json", "w") as f:
        json.dump(favourites, f)

def add_favourite(wine_id, pin, correct_pin):
    """Add a wine to favourites if the correct PIN is provided."""
    if pin == correct_pin:
        favourites = load_favourites()
        if wine_id not in favourites:
            favourites.append(wine_id)
            save_favourites(favourites)
            return True
    return False

def remove_favourite(wine_id, pin, correct_pin):
    """Remove a wine from favourites if the correct PIN is provided."""
    if pin == correct_pin:
        favourites = load_favourites()
        if wine_id in favourites:
            favourites.remove(wine_id)
            save_favourites(favourites)
            return True
    return False

def get_favourites():
    """Retrieve the list of favourite wines."""
    return load_favourites()