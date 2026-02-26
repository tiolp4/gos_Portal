from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User
from helpers import is_valid_inn, get_or_create_org_by_inn, login_required

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
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
        session["user_role"] = user.role

        flash("Вход выполнен.", "success")
        return redirect(url_for("dashboard.dashboard"))

    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
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

        if User.query.filter_by(login=login_value).first():
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
            password=generate_password_hash(password_value),
            role="user",
        )

        db.session.add(user)
        db.session.commit()

        session["user_id"] = int(user.id)
        session["user_login"] = user.login
        session["user_role"] = user.role

        flash("Регистрация успешна.", "success")
        return redirect(url_for("dashboard.dashboard"))

    return render_template("register.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы.", "success")
    return redirect(url_for("auth.login"))