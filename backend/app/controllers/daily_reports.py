"""Deprecated module: API082–087 are registered explicitly by m5_report_routes in app.main.
No second daily-report writer exists. Import app.main:app for the complete backend.
"""
from fastapi import APIRouter
router=APIRouter(tags=['日报兼容模块'])
