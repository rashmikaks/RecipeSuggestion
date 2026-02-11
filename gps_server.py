from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/location", methods=["POST"])
def location():
    data = request.get_json()
    print("Received:", data)
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
