from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime

from models import db, User, Ticket, TicketMessage, TicketCategory, TICKET_PRIORITIES, TICKET_STATUSES
from helpers import login_required, role_required

tickets_bp = Blueprint("tickets", __name__)


@tickets_bp.route("/tickets")
@login_required
def ticket_list():
    user = User.query.get(session["user_id"])
    status_filter = request.args.get("status", "new")
    category_filter = request.args.get("category", "")

    if user.role == "user":
        query = Ticket.query.filter_by(creator_id=user.id)
    else:
        query = Ticket.query

    if status_filter:
        query = query.filter_by(status=status_filter)
    if category_filter:
        query = query.filter_by(category=category_filter)

    tickets = query.order_by(Ticket.updated_at.desc()).all()
    categories = TicketCategory.query.order_by(TicketCategory.name).all()

    return render_template(
        "tickets.html",
        tickets=tickets,
        user=user,
        categories=categories,
        statuses=TICKET_STATUSES,
        current_status=status_filter,
        current_category=category_filter,
    )


@tickets_bp.route("/tickets/create", methods=["GET", "POST"])
@login_required
def ticket_create():
    categories = TicketCategory.query.order_by(TicketCategory.name).all()

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        priority = request.form.get("priority", "medium").strip()

        if not all([subject, description, category]):
            flash("Заполните все обязательные поля.", "error")
            return render_template("ticket_create.html", categories=categories, priorities=TICKET_PRIORITIES)

        valid_names = [c.name for c in categories]
        if category not in valid_names:
            flash("Неверная категория.", "error")
            return render_template("ticket_create.html", categories=categories, priorities=TICKET_PRIORITIES)

        if priority not in TICKET_PRIORITIES:
            priority = "medium"

        ticket = Ticket(
            subject=subject,
            description=description,
            category=category,
            priority=priority,
            status="new",
            creator_id=session["user_id"],
        )

        db.session.add(ticket)
        db.session.commit()

        flash("Заявка создана.", "success")
        return redirect(url_for("tickets.ticket_detail", ticket_id=ticket.id))

    return render_template("ticket_create.html", categories=categories, priorities=TICKET_PRIORITIES)


@tickets_bp.route("/tickets/<int:ticket_id>", methods=["GET", "POST"])
@login_required
def ticket_detail(ticket_id):
    user = User.query.get(session["user_id"])
    ticket = Ticket.query.get_or_404(ticket_id)

    if user.role == "user" and ticket.creator_id != user.id:
        flash("Нет доступа к этой заявке.", "error")
        return redirect(url_for("tickets.ticket_list"))

    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if body:
            msg = TicketMessage(ticket_id=ticket.id, author_id=user.id, body=body)
            db.session.add(msg)
            ticket.updated_at = datetime.utcnow()
            db.session.commit()
            flash("Сообщение отправлено.", "success")
        return redirect(url_for("tickets.ticket_detail", ticket_id=ticket.id))

    messages = TicketMessage.query.filter_by(ticket_id=ticket.id).order_by(TicketMessage.created_at.asc()).all()
    operators = User.query.filter(User.role.in_(["operator", "admin"])).all()
    categories = TicketCategory.query.order_by(TicketCategory.name).all()

    return render_template(
        "ticket_detail.html",
        ticket=ticket,
        messages=messages,
        user=user,
        operators=operators,
        statuses=TICKET_STATUSES,
        categories=categories,
        priorities=TICKET_PRIORITIES,
    )


@tickets_bp.route("/tickets/<int:ticket_id>/assign", methods=["POST"])
@role_required("operator", "admin")
def ticket_assign(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    ticket.assigned_to_id = session["user_id"]
    if ticket.status == "new":
        ticket.status = "in_progress"
    ticket.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Заявка взята в работу.", "success")
    return redirect(url_for("tickets.ticket_detail", ticket_id=ticket.id))


@tickets_bp.route("/tickets/<int:ticket_id>/status", methods=["POST"])
@role_required("operator", "admin")
def ticket_status(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    new_status = request.form.get("status", "").strip()
    if new_status in TICKET_STATUSES:
        ticket.status = new_status
        ticket.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f"Статус изменён: {new_status}", "success")
    return redirect(url_for("tickets.ticket_detail", ticket_id=ticket.id))


@tickets_bp.route("/tickets/<int:ticket_id>/close", methods=["POST"])
@role_required("operator", "admin")
def ticket_close(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    ticket.status = "closed"
    ticket.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Заявка закрыта.", "success")
    return redirect(url_for("tickets.ticket_detail", ticket_id=ticket.id))


@tickets_bp.route("/tickets/<int:ticket_id>/close_with_message", methods=["POST"])
@role_required("operator", "admin")
def ticket_close_with_message(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    body = request.form.get("body", "").strip()

    if body:
        msg = TicketMessage(ticket_id=ticket.id, author_id=session["user_id"], body=body)
        db.session.add(msg)

    ticket.status = "closed"
    ticket.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Сообщение отправлено, заявка закрыта.", "success")
    return redirect(url_for("tickets.ticket_detail", ticket_id=ticket.id))


@tickets_bp.route("/tickets/<int:ticket_id>/category", methods=["POST"])
@role_required("operator", "admin")
def ticket_category(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    new_category = request.form.get("category", "").strip()
    valid_names = [c.name for c in TicketCategory.query.all()]
    if new_category in valid_names:
        ticket.category = new_category
        ticket.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f"Категория изменена: {new_category}", "success")
    return redirect(url_for("tickets.ticket_detail", ticket_id=ticket.id))


@tickets_bp.route("/tickets/<int:ticket_id>/priority", methods=["POST"])
@role_required("operator", "admin")
def ticket_priority(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    new_priority = request.form.get("priority", "").strip()
    if new_priority in TICKET_PRIORITIES:
        ticket.priority = new_priority
        ticket.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f"Приоритет изменён: {new_priority}", "success")
    return redirect(url_for("tickets.ticket_detail", ticket_id=ticket.id))
