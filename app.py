import os
from flask import Flask, redirect, url_for
from werkzeug.security import generate_password_hash
from sqlalchemy import text, inspect

from models import db, User, Organization

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = "super-secret-key-gov"
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://db1:db1@10.1.92.144:5432/gov_portal"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.tickets import tickets_bp
from routes.admin import admin_bp
from routes.api import api_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(tickets_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)


@app.route("/")
def index():
    return redirect(url_for("auth.login"))


def init_db():
    with app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
        except Exception as e:
            print("Ошибка подключения:", e)
            return

        inspector = inspect(db.engine)
        if inspector.has_table("users"):
            print("Таблицы уже существуют  пропуск инициализации")
            return

        db.create_all()
        print("Таблицы созданы")

        admin_org = Organization(inn="0000000000", full_name="Администрация", short_name="Админ")
        db.session.add(admin_org)
        db.session.commit()

        admin_user = User(
            name="Админ",
            firstname="Системный",
            otchestvo=None,
            organization_id=admin_org.id,
            position="Администратор",
            login="admin",
            password=generate_password_hash("admin"),
            role="admin",
        )
        db.session.add(admin_user)
        db.session.commit()
        print("Создан пользователь admin / admin")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)