from flask import Flask
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    surname = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    patronymic = db.Column(db.String(100), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    position = db.Column(db.String(150), nullable=False)

    login = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

