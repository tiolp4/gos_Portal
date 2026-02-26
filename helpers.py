import os
import re
import requests
from datetime import datetime
from functools import wraps
from flask import session, redirect, url_for, flash
from sqlalchemy.exc import IntegrityError

from models import db, Organization

ORG_SERVICE_BASE = os.getenv("ORG_SERVICE_BASE", "http://10.1.92.144:8000")
INN_RE = re.compile(r"^\d{10}(\d{2})?$")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Сначала выполните вход.", "error")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                flash("Сначала выполните вход.", "error")
                return redirect(url_for("auth.login"))
            if session.get("user_role") not in roles:
                flash("Недостаточно прав.", "error")
                return redirect(url_for("dashboard.dashboard"))
            return f(*args, **kwargs)
        return decorated
    return decorator


def is_valid_inn(inn):
    inn = (inn or "").strip()
    return bool(INN_RE.match(inn))


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def fetch_org_from_service(inn):
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


def get_or_create_org_by_inn(inn):
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
        org = Organization(inn=inn)

    db.session.add(org)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        org = Organization.query.filter_by(inn=inn).first()

    return org


def org_to_dict(org, view):
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