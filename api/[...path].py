# -*- coding: utf-8 -*-
"""
Vercel Serverless 函数入口（Python）。
所有 /api/* 请求统一转发到 core.app_dispatch。
配合 vercel.json：前端静态资源由 Vercel 同源托管于 /app/。
"""
from werkzeug.wrappers import Request, Response
import sys
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from core import app_dispatch


@Request.application
def handler(request):
    method = request.method
    path = request.path
    query = request.args.to_dict() if hasattr(request.args, "to_dict") else dict(request.args)
    headers = dict(request.headers)
    raw = request.get_data()
    status, payload, extra = app_dispatch(method, path, query, headers, raw)
    resp_headers = {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"}
    resp_headers.update(extra or {})
    return Response(json.dumps(payload, ensure_ascii=False), status=status, headers=resp_headers)
