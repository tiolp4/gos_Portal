import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.security import generate_password_hash

from models import db, User, USER_ROLES, TicketCategory
from helpers import role_required, get_or_create_org_by_inn, is_valid_inn

admin_bp = Blueprint("admin", __name__)


def send_email(to_address, login, password):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Добрый день! Система выдала вам учётные данные"
    msg["From"] = current_app.config["MAIL_USER"]
    msg["To"] = to_address

    body = f"""Добрый день!

Система выдала вам учётные данные для входа в ГИС Портал:

Логин: {login}
Пароль: {password}

Пожалуйста, сохраните эти данные и не передавайте третьим лицам.

С уважением,
Администрация ГИС Портала"""

    msg.attach(MIMEText(body, "plain", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        current_app.config["MAIL_HOST"],
        current_app.config["MAIL_PORT"],
        context=context
    ) as server:
        server.login(current_app.config["MAIL_USER"], current_app.config["MAIL_PASSWORD"])
        server.sendmail(current_app.config["MAIL_USER"], to_address, msg.as_string())


@admin_bp.route("/admin/users", methods=["GET", "POST"])
@role_required("admin")
def admin_users():
    if request.method == "POST":
        user_id = request.form.get("user_id")
        new_role = request.form.get("role", "").strip()
        if new_role in USER_ROLES and user_id:
            target = User.query.get(int(user_id))
            if target:
                target.role = new_role
                db.session.commit()
                flash(f"Роль {target.login} изменена на {new_role}.", "success")

    users = User.query.order_by(User.id).all()
    return render_template("admin_users.html", users=users, roles=USER_ROLES)


@admin_bp.route("/admin/users/create", methods=["GET", "POST"])
@role_required("admin")
def admin_user_create():
    if request.method == "POST":
        surname = request.form.get("surname", "").strip()
        first_name = request.form.get("name", "").strip()
        patronymic = request.form.get("patronymic", "").strip()
        position = request.form.get("position", "").strip()
        inn = request.form.get("inn", "").strip()
        login_value = request.form.get("login", "").strip()
        password_value = request.form.get("password", "").strip()
        email_value = request.form.get("email", "").strip()
        role_value = request.form.get("role", "user").strip()

        if not all([surname, first_name, inn, login_value, password_value]):
            flash("Заполните все обязательные поля.", "error")
            return render_template("admin_user_create.html", roles=USER_ROLES)

        if not is_valid_inn(inn):
            flash("ИНН должен содержать 10 или 12 цифр.", "error")
            return render_template("admin_user_create.html", roles=USER_ROLES)

        if User.query.filter_by(login=login_value).first():
            flash("Пользователь с таким логином уже существует.", "error")
            return render_template("admin_user_create.html", roles=USER_ROLES)

        if role_value not in USER_ROLES:
            role_value = "user"

        org = get_or_create_org_by_inn(inn)

        user = User(
            name=surname,
            firstname=first_name,
            otchestvo=patronymic or None,
            organization_id=org.id,
            position=position or None,
            login=login_value,
            password=generate_password_hash(password_value),
            email=email_value or None,
            role=role_value,
        )

        db.session.add(user)
        db.session.commit()

        flash("Пользователь создан.", "success")
        return render_template(
            "admin_user_created.html",
            login=login_value,
            password=password_value,
            email=email_value,
            user=user,
        )

    return render_template("admin_user_create.html", roles=USER_ROLES)


@admin_bp.route("/admin/users/<int:user_id>/send_email", methods=["POST"])
@role_required("admin")
def admin_send_email(user_id):
    user = User.query.get_or_404(user_id)
    plain_password = request.form.get("plain_password", "").strip()

    if not user.email:
        flash("У пользователя не указан email.", "error")
        return redirect(url_for("admin.admin_users"))

    if not plain_password:
        flash("Пароль не передан.", "error")
        return redirect(url_for("admin.admin_users"))

    try:
        send_email(user.email, user.login, plain_password)
        flash(f"Письмо отправлено на {user.email}.", "success")
    except Exception as e:
        flash(f"Ошибка отправки письма: {e}", "error")

    return redirect(url_for("admin.admin_users"))


@admin_bp.route("/admin/categories", methods=["GET", "POST"])
@role_required("admin")
def admin_categories():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            name = request.form.get("name", "").strip()
            if not name:
                flash("Название категории не может быть пустым.", "error")
            elif TicketCategory.query.filter_by(name=name).first():
                flash("Такая категория уже существует.", "error")
            else:
                db.session.add(TicketCategory(name=name))
                db.session.commit()
                flash(f"Категория {name} добавлена.", "success")

        elif action == "delete":
            cat_id = request.form.get("cat_id")
            if cat_id:
                cat = TicketCategory.query.get(int(cat_id))
                if cat:
                    db.session.delete(cat)
                    db.session.commit()
                    flash(f"Категория {cat.name} удалена.", "success")

    categories = TicketCategory.query.order_by(TicketCategory.id).all()
    return render_template("admin_categories.html", categories=categories)
