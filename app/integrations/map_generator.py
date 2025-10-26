import folium
from app.utils.helpers import LATEST_MAP

def create_map(df):
    # Default center: Newton, MA (stub)
    m = folium.Map(location=[42.337, -71.209], zoom_start=12)

    for _, r in df.iterrows():
        lat = r.get("lat", 42.337)
        lon = r.get("lon", -71.209)
        popup = folium.Popup(
            f"{r.get('address', '')}<br>"
            f"Score: {r.get('development_score', '')}<br>"
            f"Label: {r.get('label', '')}",
            max_width=250,
        )
        folium.Marker([lat, lon], popup=popup).add_to(m)

    m.save(str(LATEST_MAP))
    return LATEST_MAP
