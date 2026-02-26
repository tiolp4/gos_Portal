import os
import re
import requests
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = "super-secret-key-gov"

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://db1:db1@10.1.92.144:5432/gov_portal"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

ORG_SERVICE_BASE = os.getenv("ORG_SERVICE_BASE", "http://10.1.92.144:8000")
INN_RE = re.compile(r"^\d{10}(\d{2})?$")  # 10 или 12 цифр


# -------------------- Models --------------------
class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.BigInteger, primary_key=True)
    inn = db.Column(db.String(12), unique=True, nullable=False)

    # данные из сервиса (могут быть NULL)
    org_id = db.Column(db.BigInteger, nullable=True, index=True)
    full_name = db.Column(db.Text, nullable=True)
    short_name = db.Column(db.Text, nullable=True)
    date_of_registration = db.Column(db.Date, nullable=True)
    kpp = db.Column(db.String(9), nullable=True)
    ogrn = db.Column(db.String(13), nullable=True)
    head_name = db.Column(db.Text, nullable=True)
    head_position = db.Column(db.Text, nullable=True)
    head_inn = db.Column(db.String(12), nullable=True)
    full_address_text = db.Column(db.Text, nullable=True)

    users = db.relationship("User", backref="organization", lazy=True)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True)

    name = db.Column(db.String(100), nullable=False)        # фамилия
    firstname = db.Column(db.String(100), nullable=False)   # имя
    otchestvo = db.Column(db.String(100), nullable=True)    # отчество

    organization_id = db.Column(
        db.BigInteger,
        db.ForeignKey("organizations.id"),
        nullable=False
    )

    position = db.Column(db.String(150), nullable=True)
    login = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)


# -------------------- Helpers --------------------
def is_valid_inn(inn: str) -> bool:
    inn = (inn or "").strip()
    return bool(INN_RE.match(inn))


def parse_date(s: str | None):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def fetch_org_from_service(inn: str) -> dict | None:
    try:
        r = requests.get(
            f"{ORG_SERVICE_BASE}/v1/orgs/find/by_inn",
            params={"inn": inn, "view": "full"},
            headers={"accept": "application/json"},
            timeout=8,
        )
    except requests.RequestException:
        return None

    if r.status_code != 200:
        return None

    try:
        return r.json()
    except ValueError:
        return None


def get_or_create_org_by_inn(inn: str) -> Organization:
    org = Organization.query.filter_by(inn=inn).first()
    if org:
        return org

    data = fetch_org_from_service(inn)

    if data:
        org = Organization(
            inn=data.get("inn", inn),
            org_id=data.get("org_id"),
            full_name=data.get("full_name"),
            short_name=data.get("short_name"),
            date_of_registration=parse_date(data.get("date_of_registration")),
            kpp=data.get("kpp"),
            ogrn=data.get("ogrn"),
            head_name=data.get("head_name"),
            head_position=data.get("head_position"),
            head_inn=data.get("head_inn"),
            full_address_text=data.get("full_address_text"),
        )
    else:
        # сервис недоступен/не нашел — сохраняем хотя бы ИНН
        org = Organization(inn=inn)

    db.session.add(org)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        org = Organization.query.filter_by(inn=inn).first()

    return org


def org_to_dict(org: Organization, view: str) -> dict:
    if view == "minimal":
        return {
            "org_id": org.org_id,
            "full_name": org.full_name,
            "short_name": org.short_name,
            "inn": org.inn,
        }

    return {
        "org_id": org.org_id,
        "full_name": org.full_name,
        "short_name": org.short_name,
        "date_of_registration": org.date_of_registration.isoformat() if org.date_of_registration else None,
        "inn": org.inn,
        "kpp": org.kpp,
        "ogrn": org.ogrn,
        "head_name": org.head_name,
        "head_position": org.head_position,
        "head_inn": org.head_inn,
        "full_address_text": org.full_address_text,
    }


def ensure_org_columns():
    """
    create_all() не добавляет колонки в существующую таблицу.
    Этот блок безопасно добавляет недостающие колонки.
    """
    ddl = """
    ALTER TABLE organizations
      ADD COLUMN IF NOT EXISTS org_id BIGINT,
      ADD COLUMN IF NOT EXISTS full_name TEXT,
      ADD COLUMN IF NOT EXISTS short_name TEXT,
      ADD COLUMN IF NOT EXISTS date_of_registration DATE,
      ADD COLUMN IF NOT EXISTS kpp VARCHAR(9),
      ADD COLUMN IF NOT EXISTS ogrn VARCHAR(13),
      ADD COLUMN IF NOT EXISTS head_name TEXT,
      ADD COLUMN IF NOT EXISTS head_position TEXT,
      ADD COLUMN IF NOT EXISTS head_inn VARCHAR(12),
      ADD COLUMN IF NOT EXISTS full_address_text TEXT;
    CREATE INDEX IF NOT EXISTS ix_organizations_org_id ON organizations (org_id);
    """
    statements = [s.strip() for s in ddl.split(";") if s.strip()]
    for stmt in statements:
        db.session.execute(text(stmt))
    db.session.commit()


# -------------------- Routes --------------------
@app.route("/")
def index():
    return redirect(url_for("login"))


@app.get("/v1/orgs/find/by_inn")
def api_find_org_by_inn():
    inn = (request.args.get("inn") or "").strip()
    view = (request.args.get("view") or "minimal").strip()

    if not inn:
        return jsonify({"detail": "inn обязателен"}), 422
    if not is_valid_inn(inn):
        return jsonify({"detail": "inn должен содержать 10 или 12 цифр"}), 422
    if view not in ("minimal", "full"):
        return jsonify({"detail": "view должен быть minimal или full"}), 422

    org = Organization.query.filter_by(inn=inn).first()
    if org:
        return jsonify(org_to_dict(org, view)), 200

    data = fetch_org_from_service(inn)
    if not data:
        return jsonify({"detail": "Организация не найдена"}), 404

    org = Organization(
        inn=data.get("inn", inn),
        org_id=data.get("org_id"),
        full_name=data.get("full_name"),
        short_name=data.get("short_name"),
        date_of_registration=parse_date(data.get("date_of_registration")),
        kpp=data.get("kpp"),
        ogrn=data.get("ogrn"),
        head_name=data.get("head_name"),
        head_position=data.get("head_position"),
        head_inn=data.get("head_inn"),
        full_address_text=data.get("full_address_text"),
    )

    db.session.add(org)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        org = Organization.query.filter_by(inn=inn).first()

    return jsonify(org_to_dict(org, view)), 200


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        surname = request.form.get("surname", "").strip()
        first_name = request.form.get("name", "").strip()
        patronymic = request.form.get("patronymic", "").strip()
        position = request.form.get("position", "").strip()
        inn = request.form.get("inn", "").strip()
        login_value = request.form.get("login", "").strip()
        password_value = request.form.get("password", "")

        if not all([surname, first_name, inn, login_value, password_value]):
            flash("Заполните все обязательные поля.", "error")
            return render_template("register.html")

        if not is_valid_inn(inn):
            flash("ИНН должен содержать 10 или 12 цифр.", "error")
            return render_template("register.html")

        existing_user = User.query.filter_by(login=login_value).first()
        if existing_user:
            flash("Пользователь с таким логином уже существует.", "error")
            return render_template("register.html")

        org = get_or_create_org_by_inn(inn)

        user = User(
            name=surname,
            firstname=first_name,
            otchestvo=patronymic or None,
            organization_id=org.id,
            position=position or None,
            login=login_value,
            password=generate_password_hash(password_value)
        )

        db.session.add(user)
        db.session.commit()

        session["user_id"] = int(user.id)
        session["user_login"] = user.login

        flash("Регистрация успешна.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_value = request.form.get("login", "").strip()
        password_value = request.form.get("password", "")

        if not login_value or not password_value:
            flash("Введите логин и пароль.", "error")
            return render_template("login.html")

        user = User.query.filter_by(login=login_value).first()
        if not user:
            flash("Пользователь не зарегистрирован.", "error")
            return render_template("login.html")

        if not check_password_hash(user.password, password_value):
            flash("Неверный логин или пароль.", "error")
            return render_template("login.html")

        session["user_id"] = int(user.id)
        session["user_login"] = user.login

        flash("Вход выполнен успешно.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Сначала выполните вход.", "error")
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if not user:
        session.clear()
        flash("Пользователь не найден. Войдите снова.", "error")
        return redirect(url_for("login"))

    org = user.organization
    return render_template("dashboard.html", user=user, org=org)


@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы.", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    with app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
            print("✅ PostgreSQL подключен")

            # создаем таблицы (если нет)
            db.create_all()

            # добавляем новые колонки в organizations (если таблица уже старая)
            ensure_org_columns()

            print("✅ Таблицы созданы/проверены")
        except Exception as e:
            print("❌ Ошибка подключения/инициализации БД:", e)

    app.run(debug=True)