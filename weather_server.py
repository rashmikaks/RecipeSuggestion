from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
OPENWEATHER_API_KEY = "YOUR_API_KEY"

@app.route("/weather", methods=["POST"])
def weather():
    data = request.get_json()
    lat = data.get("lat")
    lon = data.get("lon")

    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
    resp = requests.get(url).json()

    return jsonify({
        "city": resp.get("name", "Unknown"),
        "temperature": resp["main"]["temp"],
        "condition": resp["weather"][0]["main"],
        "humidity": resp["main"]["humidity"],
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
