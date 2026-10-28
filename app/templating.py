"""Jinja2 environment shared by the routes."""

from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app import config

templates = Jinja2Templates(directory=str(config.TEMPLATE_DIR))
