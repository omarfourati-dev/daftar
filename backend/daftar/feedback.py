"""Feedback button of the app (section 15, J2): "Une idée ? Un problème ?".

- ``POST /api/feedback {message ≤ 2000, page?}`` → 201 (staff; also with a suspended subscription – a practice
  that is blocked must still be able to tell us). 10 per user and hour. Counter ``daftar_feedback_total``.
- ``GET /api/admin/feedback`` (newest first) · ``DELETE /api/admin/feedback/{id}`` → 204 (admin).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Response
from pydantic import Field
from sqlalchemy import delete, insert, select

from .deps import AdminUser, Conn, Ctx, StaffUser
from .problems import not_found
from .schemas import ApiModel, TunisDateTime
from .tables import app_user, feedback, practice

router = APIRouter(prefix="/api/feedback", tags=["feedback"])
admin_router = APIRouter(prefix="/api/admin/feedback", tags=["admin"])

PER_USER = 10
WINDOW = timedelta(hours=1)


class FeedbackIn(ApiModel):
    message: Annotated[str, Field(min_length=1, max_length=2000)]
    page: Annotated[str, Field(max_length=300)] = ""


class FeedbackOut(ApiModel):
    id: int
    message: str
    page: str
    created_at: TunisDateTime


class AdminFeedbackOut(FeedbackOut):
    practice_id: int
    practice_name: str
    user_id: int | None
    user_name: str | None
    user_role: str | None


@router.post("", status_code=201)
def send_feedback(body: FeedbackIn, user: StaffUser, ctx: Ctx, conn: Conn) -> FeedbackOut:
    ctx.limiter("feedback-user", PER_USER, WINDOW).enforce(str(user.user_id))
    row = conn.execute(
        insert(feedback)
        .values(practice_id=user.pid, user_id=user.user_id, message=body.message, page=body.page, created_at=ctx.clock.now())
        .returning(feedback)
    ).one()
    ctx.metrics.feedback.inc()
    return FeedbackOut.model_validate(row, from_attributes=True)


@admin_router.get("")
def list_feedback(_: AdminUser, conn: Conn) -> list[AdminFeedbackOut]:
    rows = conn.execute(
        select(
            feedback,
            practice.c.name.label("practice_name"),
            app_user.c.name.label("user_name"),
            app_user.c.role.label("user_role"),
        )
        .select_from(
            feedback.join(practice, practice.c.id == feedback.c.practice_id).outerjoin(
                app_user, app_user.c.id == feedback.c.user_id
            )
        )
        .order_by(feedback.c.created_at.desc(), feedback.c.id.desc())
    )
    return [AdminFeedbackOut.model_validate(r, from_attributes=True) for r in rows]


@admin_router.delete("/{feedback_id}", status_code=204)
def delete_feedback(feedback_id: int, _: AdminUser, conn: Conn) -> Response:
    if not conn.execute(delete(feedback).where(feedback.c.id == feedback_id)).rowcount:
        raise not_found()
    return Response(status_code=204)
