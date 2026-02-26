from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

TICKET_CATEGORIES = ["сбой", "ограничение доступа", "проблемы с сетью"]
TICKET_PRIORITIES = ["low", "medium", "high", "critical"]
TICKET_STATUSES = ["new", "in_progress", "resolved", "closed"]
USER_ROLES = ["user", "operator", "admin"]


class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.BigInteger, primary_key=True)
    inn = db.Column(db.String(12), unique=True, nullable=False)
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
    name = db.Column(db.String(100), nullable=False)
    firstname = db.Column(db.String(100), nullable=False)
    otchestvo = db.Column(db.String(100), nullable=True)
    organization_id = db.Column(db.BigInteger, db.ForeignKey("organizations.id"), nullable=False)
    position = db.Column(db.String(150), nullable=True)
    login = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")

    created_tickets = db.relationship("Ticket", foreign_keys="Ticket.creator_id", backref="creator", lazy=True)
    assigned_tickets = db.relationship("Ticket", foreign_keys="Ticket.assigned_to_id", backref="assigned_to", lazy=True)
    messages = db.relationship("TicketMessage", backref="author", lazy=True)


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.BigInteger, primary_key=True)
    subject = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    priority = db.Column(db.String(20), nullable=False, default="medium")
    status = db.Column(db.String(20), nullable=False, default="new")
    creator_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    assigned_to_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = db.relationship("TicketMessage", backref="ticket", lazy=True, order_by="TicketMessage.created_at")


class TicketMessage(db.Model):
    __tablename__ = "ticket_messages"

    id = db.Column(db.BigInteger, primary_key=True)
    ticket_id = db.Column(db.BigInteger, db.ForeignKey("tickets.id"), nullable=False)
    author_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)