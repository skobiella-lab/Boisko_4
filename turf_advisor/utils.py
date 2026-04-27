import requests

def geocode_address(address):
    """Geokoduje adres na współrzędne używając Nominatim API."""
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1"
        headers = {'User-Agent': 'TurfAdvisor/1.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                return {
                    'lat': float(data[0]['lat']),
                    'lon': float(data[0]['lon']),
                    'display_name': data[0]['display_name']
                }
        return None
    except Exception as e:
        print(f"Błąd geokodowania: {e}")
        return None