from flask import Blueprint, render_template, session, redirect, url_for, flash

from models import User, Ticket
from helpers import login_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    user = User.query.get(session["user_id"])
    if not user:
        session.clear()
        flash("Пользователь не найден.", "error")
        return redirect(url_for("auth.login"))

    org = user.organization

    if user.role == "user":
        tickets = Ticket.query.filter_by(creator_id=user.id).order_by(Ticket.updated_at.desc()).limit(5).all()
    elif user.role == "operator":
        tickets = Ticket.query.filter(
            (Ticket.assigned_to_id == user.id) | (Ticket.status == "new")
        ).order_by(Ticket.updated_at.desc()).limit(10).all()
    else:
        tickets = Ticket.query.order_by(Ticket.updated_at.desc()).limit(10).all()

    return render_template("dashboard.html", user=user, org=org, tickets=tickets)