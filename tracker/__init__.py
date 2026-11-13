from flask import Flask
from .db import init_db
from .routes import bp


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(SECRET_KEY="local-demo-secret", DATABASE="instance/breakdowns.db")
    if test_config:
        app.config.update(test_config)
    init_db(app)
    app.register_blueprint(bp)
    return app
