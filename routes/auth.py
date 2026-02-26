from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash

from models import User
from helpers import login_required

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


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы.", "success")
    return redirect(url_for("auth.login"))
