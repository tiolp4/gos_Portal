from datetime import datetime, timedelta
from collections import defaultdict

from flask import Blueprint, render_template
from sqlalchemy import func, and_

from models import db, Ticket, TicketMessage, User, TICKET_STATUSES, TICKET_PRIORITIES
from helpers import role_required

analytics_bp = Blueprint("analytics", __name__)


def _fmt_hours(seconds):
    """Секунды → строка вида '2ч 35м'"""
    if seconds is None or seconds <= 0:
        return "—"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0:
        return f"{h}ч {m}м"
    return f"{m}м"


def _get_summary():
    """Сводные цифры."""
    total = Ticket.query.count()
    by_status = dict(
        db.session.query(Ticket.status, func.count(Ticket.id))
        .group_by(Ticket.status)
        .all()
    )
    open_count = by_status.get("new", 0) + by_status.get("in_progress", 0)
    closed_count = by_status.get("closed", 0) + by_status.get("resolved", 0)
    unassigned = Ticket.query.filter(
        Ticket.assigned_to_id.is_(None),
        Ticket.status.in_(["new", "in_progress"]),
    ).count()

    return {
        "total": total,
        "open": open_count,
        "closed": closed_count,
        "new": by_status.get("new", 0),
        "in_progress": by_status.get("in_progress", 0),
        "resolved": by_status.get("resolved", 0),
        "closed_only": by_status.get("closed", 0),
        "unassigned": unassigned,
    }


def _get_avg_first_response():
    """
    Среднее время первого ответа оператора (не автора заявки).
    Возвращает (средние секунды, dict дата→секунды за 30 дней).
    """
    since = datetime.utcnow() - timedelta(days=30)

    tickets = (
        Ticket.query
        .filter(Ticket.created_at >= since)
        .all()
    )

    daily = defaultdict(list)
    all_deltas = []

    for t in tickets:
        first_msg = (
            TicketMessage.query
            .filter(
                TicketMessage.ticket_id == t.id,
                TicketMessage.author_id != t.creator_id,
            )
            .order_by(TicketMessage.created_at.asc())
            .first()
        )
        if first_msg:
            delta = (first_msg.created_at - t.created_at).total_seconds()
            if delta >= 0:
                all_deltas.append(delta)
                day_key = t.created_at.strftime("%Y-%m-%d")
                daily[day_key].append(delta)

    avg_total = sum(all_deltas) / len(all_deltas) if all_deltas else 0

    daily_avg = {}
    for d, vals in daily.items():
        daily_avg[d] = sum(vals) / len(vals)

    return avg_total, daily_avg


def _get_avg_resolution_time():
    """
    Среднее время закрытия (created_at → updated_at для closed/resolved).
    Возвращает (средние секунды, dict дата→секунды за 30 дней).
    """
    since = datetime.utcnow() - timedelta(days=30)

    tickets = (
        Ticket.query
        .filter(
            Ticket.status.in_(["closed", "resolved"]),
            Ticket.created_at >= since,
        )
        .all()
    )

    daily = defaultdict(list)
    all_deltas = []

    for t in tickets:
        delta = (t.updated_at - t.created_at).total_seconds()
        if delta >= 0:
            all_deltas.append(delta)
            day_key = t.created_at.strftime("%Y-%m-%d")
            daily[day_key].append(delta)

    avg_total = sum(all_deltas) / len(all_deltas) if all_deltas else 0

    daily_avg = {}
    for d, vals in daily.items():
        daily_avg[d] = sum(vals) / len(vals)

    return avg_total, daily_avg


def _get_tickets_per_day(days=30):
    """Создано / закрыто заявок по дням."""
    since = datetime.utcnow() - timedelta(days=days)

    created_raw = (
        db.session.query(
            func.date(Ticket.created_at).label("day"),
            func.count(Ticket.id),
        )
        .filter(Ticket.created_at >= since)
        .group_by("day")
        .all()
    )

    closed_raw = (
        db.session.query(
            func.date(Ticket.updated_at).label("day"),
            func.count(Ticket.id),
        )
        .filter(
            Ticket.status.in_(["closed", "resolved"]),
            Ticket.updated_at >= since,
        )
        .group_by("day")
        .all()
    )

    created_map = {str(r[0]): r[1] for r in created_raw}
    closed_map = {str(r[0]): r[1] for r in closed_raw}

    labels = []
    created_vals = []
    closed_vals = []

    for i in range(days, -1, -1):
        d = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        labels.append(d)
        created_vals.append(created_map.get(d, 0))
        closed_vals.append(closed_map.get(d, 0))

    return labels, created_vals, closed_vals


def _get_by_category():
    """Заявки по категориям."""
    rows = (
        db.session.query(Ticket.category, func.count(Ticket.id))
        .group_by(Ticket.category)
        .order_by(func.count(Ticket.id).desc())
        .all()
    )
    return {r[0]: r[1] for r in rows}


def _get_by_priority():
    """Заявки по приоритету."""
    rows = (
        db.session.query(Ticket.priority, func.count(Ticket.id))
        .group_by(Ticket.priority)
        .all()
    )
    return {r[0]: r[1] for r in rows}


def _get_by_status():
    """Заявки по статусу."""
    rows = (
        db.session.query(Ticket.status, func.count(Ticket.id))
        .group_by(Ticket.status)
        .all()
    )
    return {r[0]: r[1] for r in rows}


def _get_operator_stats():
    """Статистика по операторам: сколько заявок, среднее время решения."""
    operators = User.query.filter(User.role.in_(["operator", "admin"])).all()
    stats = []

    for op in operators:
        assigned = Ticket.query.filter_by(assigned_to_id=op.id).count()
        closed_tickets = Ticket.query.filter(
            Ticket.assigned_to_id == op.id,
            Ticket.status.in_(["closed", "resolved"]),
        ).all()

        if closed_tickets:
            deltas = [(t.updated_at - t.created_at).total_seconds() for t in closed_tickets]
            avg_sec = sum(deltas) / len(deltas)
        else:
            avg_sec = 0

        stats.append({
            "login": op.login,
            "name": f"{op.name} {op.firstname}",
            "assigned": assigned,
            "closed": len(closed_tickets),
            "avg_resolution": _fmt_hours(avg_sec),
            "avg_resolution_sec": avg_sec,
        })

    stats.sort(key=lambda x: x["closed"], reverse=True)
    return stats


def _fill_daily(daily_dict, days=30):
    """Заполняет пропуски нулями, возвращает (labels, values) в часах."""
    labels = []
    values = []
    for i in range(days, -1, -1):
        d = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        labels.append(d)
        sec = daily_dict.get(d, 0)
        values.append(round(sec / 3600, 2))
    return labels, values


@analytics_bp.route("/admin/analytics")
@role_required("admin", "operator")
def admin_analytics():
    summary = _get_summary()

    avg_response_sec, response_daily = _get_avg_first_response()
    avg_resolution_sec, resolution_daily = _get_avg_resolution_time()

    response_labels, response_values = _fill_daily(response_daily)
    resolution_labels, resolution_values = _fill_daily(resolution_daily)

    flow_labels, flow_created, flow_closed = _get_tickets_per_day(30)

    by_category = _get_by_category()
    by_priority = _get_by_priority()
    by_status = _get_by_status()
    operator_stats = _get_operator_stats()

    status_labels_map = {
        "new": "Новые",
        "in_progress": "В работе",
        "resolved": "Решённые",
        "closed": "Закрытые",
    }
    priority_labels_map = {
        "low": "Низкий",
        "medium": "Средний",
        "high": "Высокий",
        "critical": "Критический",
    }

    return render_template(
        "admin_analytics.html",
        summary=summary,
        avg_response=_fmt_hours(avg_response_sec),
        avg_resolution=_fmt_hours(avg_resolution_sec),
        avg_response_sec=avg_response_sec,
        avg_resolution_sec=avg_resolution_sec,
        response_labels=response_labels,
        response_values=response_values,
        resolution_labels=resolution_labels,
        resolution_values=resolution_values,
        flow_labels=flow_labels,
        flow_created=flow_created,
        flow_closed=flow_closed,
        cat_labels=list(by_category.keys()),
        cat_values=list(by_category.values()),
        pri_labels=[priority_labels_map.get(k, k) for k in by_priority.keys()],
        pri_values=list(by_priority.values()),
        sta_labels=[status_labels_map.get(k, k) for k in by_status.keys()],
        sta_values=list(by_status.values()),
        operator_stats=operator_stats,
    )