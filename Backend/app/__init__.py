from flask import Flask,jsonify
from sqlalchemy import text
from .config import Config
from flask_migrate import Migrate
from .extension import db,jwt,mail
from flask_cors import CORS
from app.database.redis_client import token_in_blocklist
from .registerRouter import register_all_routes




def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    mail.init_app(app)
    jwt.init_app(app)
    migrate = Migrate(app, db)

    CORS(app, resources={r"/api/*": {"origins": Config.FRONTEND_URL}}, supports_credentials=True)
    # CORS(app, origins=["http://192.168.1.49:5173"], supports_credentials=True)

    with app.app_context():
        try:
            db.create_all()
            db.session.execute(text('SELECT 1'))
            print("Database connected successfully!")
        except Exception as e:
            print(f"Database connection failed: {e}")



    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        try:
            return token_in_blocklist(jwt_payload["jti"])
        except Exception as e:
            print(f"Redis check failed: {e}")
            return True
    
        
    # Register all routes
    register_all_routes(app)
    @app.route('/')
    def home():
        return jsonify({"message": "Welcome to Flask API!"})

    

    return app
