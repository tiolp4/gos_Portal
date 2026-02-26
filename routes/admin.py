from flask import Blueprint, render_template, request, redirect, url_for, flash

from models import db, User, USER_ROLES
from helpers import role_required

admin_bp = Blueprint("admin", __name__)


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