"""Jinja2 environment shared by the routes."""

from __future__ import annotations

from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from app import config, i18n
from app.lang import of

templates = Jinja2Templates(directory=str(config.TEMPLATE_DIR))


@pass_context
def _t(context, key: str, **values) -> str:
    return i18n.t(of(context["request"]), key, **values)


@pass_context
def _num(context, value: float, decimals: int | None = None) -> str:
    return i18n.num(of(context["request"]), value, decimals)


templates.env.globals.update(t=_t, num=_num)
