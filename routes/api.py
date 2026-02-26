from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError

from models import db, Organization
from helpers import is_valid_inn, fetch_org_from_service, parse_date, org_to_dict

api_bp = Blueprint("api", __name__)


@api_bp.get("/v1/orgs/find/by_inn")
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