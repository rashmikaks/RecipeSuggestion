from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

API_KEY = "86913ffe1b323a7bf0611b6e56ca77f6"

latest_weather = None  # store last received weather globally

@app.route("/")
def home():
    return open("get_location.html").read()

@app.route("/location", methods=["POST"])
def receive_location():
    global latest_weather

    data = request.json
    lat = data.get("lat")
    lon = data.get("lon")
    print("Received coordinates:", data)

    geo_url = f"https://api.openweathermap.org/geo/1.0/reverse?lat={lat}&lon={lon}&limit=1&appid={API_KEY}"
    geo_response = requests.get(geo_url).json()
    print("Geo response:", geo_response)

    if geo_response and len(geo_response) > 0:
        city = geo_response[0].get("name", "Unknown")
        state = geo_response[0].get("state", "Unknown")
        country = geo_response[0].get("country", "Unknown")
    else:
        city = "Unknown"
        state = "Unknown"
        country = "Unknown"

    weather_url = (
        f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}"
        f"&appid={API_KEY}&units=metric"
    )
    weather_response = requests.get(weather_url).json()

    print("\nWeather Response:", weather_response)

    latest_weather = {
        "city": city,
        "state": state,
        "country": country,
        "weather": weather_response
    }

    return jsonify(latest_weather)

@app.route("/latest", methods=["GET"])
def latest():
    if latest_weather is None:
        return jsonify({"error": "No location received yet"}), 404
    return jsonify(latest_weather)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
