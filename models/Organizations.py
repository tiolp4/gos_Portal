from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

db = SQLAlchemy(app)

class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    inn = db.Column(db.String(12), unique=True, nullable=False)

    users = db.relationship("User", backref="organization", lazy=True)