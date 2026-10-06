from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from extensions import db, jwt

BLOCKLIST = set()  # revoked JWT ids (logout). Use Redis/DB in real production.


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    db.init_app(app)
    jwt.init_app(app)

    @jwt.token_in_blocklist_loader
    def is_revoked(_header, payload):
        return payload["jti"] in BLOCKLIST

    @jwt.unauthorized_loader
    @jwt.invalid_token_loader
    def unauthorized(reason):
        return jsonify(error="Authentication required", detail=str(reason)), 401

    @jwt.expired_token_loader
    @jwt.revoked_token_loader
    def expired(_h, _p):
        return jsonify(error="Session expired, please log in again"), 401

    from routes import api
    app.register_blueprint(api, url_prefix="/api")

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify(error="Resource not found"), 404

    @app.errorhandler(500)
    def server_error(_e):
        return jsonify(error="Internal server error"), 500

    with app.app_context():
        db.create_all()
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
