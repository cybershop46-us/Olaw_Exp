import os

from flask import current_app, jsonify

from olaw.utils import list_available_models, get_limiter

#API_MODELS_RATE_LIMIT = os.environ["API_MODELS_RATE_LIMIT"]
API_MODELS_RATE_LIMIT = os.getenv("API_MODELS_RATE_LIMIT", "10 per minute")


@current_app.route("/api/models")
@get_limiter().limit(API_MODELS_RATE_LIMIT)
def get_models():
    """
    [GET] /api/models

    Returns a JSON list of available / suitable text completion models.
    """
    return jsonify(list_available_models()), 200
