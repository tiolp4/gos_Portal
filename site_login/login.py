from flask import Flask
from flask import request
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash

from models.Users import app, User


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(login=login_value).first()

        if not user:
            flash("Пользователь не зарегистрирован.", "error")
            return render_template("login.html")

        if not check_password_hash(user.password_hash, password):
            flash("Неверный логин или пароль.", "error")
            return render_template("login.html")

        session["user_id"] = user.id
        session["user_login"] = user.login
        return redirect(url_for("dashboard"))

    return render_template("login.html")