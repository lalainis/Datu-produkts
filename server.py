from flask import Flask, jsonify, request, send_from_directory

from backend_service import BASE_DIR, get_bootstrap_data, get_dashboard_data, load_dataset


app = Flask(__name__)


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/styles.css")
def styles():
    return send_from_directory(BASE_DIR, "styles.css")


@app.get("/app.js")
def script():
    return send_from_directory(BASE_DIR, "app.js")


@app.get("/logo.png")
def logo():
    return send_from_directory(BASE_DIR, "Elektrum_Business_Logo_RGB_White.png")


@app.get("/api/health")
def health():
    dataset = load_dataset()
    return jsonify(
        {
            "status": "ok",
            "generatedAt": dataset["generatedAt"],
            "objects": len(dataset["objects"]),
        }
    )


@app.get("/api/bootstrap")
def bootstrap():
    return jsonify(get_bootstrap_data())


@app.get("/api/dashboard")
def dashboard():
    object_id = request.args.get("objectId")
    if not object_id:
        return jsonify({"error": "Missing required query parameter 'objectId'"}), 400

    try:
        payload = get_dashboard_data(object_id, request.args)
    except KeyError as error:
        return jsonify({"error": error.args[0]}), 404

    return jsonify(payload)


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Resource not found"}), 404
    return send_from_directory(BASE_DIR, "index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8010, debug=False)
