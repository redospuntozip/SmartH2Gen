# -*- coding: utf-8 -*-
"""
build_dashboard.py — Inyecta results.json en la plantilla y genera
dashboard.html (autocontenido: se abre con doble clic, sin servidor).

Ejecutar:  python build_dashboard.py
"""
import json

with open("results.json", encoding="utf-8") as f:
    data = json.load(f)
with open("dashboard_template.html", encoding="utf-8") as f:
    tpl = f.read()

html = tpl.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
with open("dashboard.html", "w", encoding="utf-8") as f:
    f.write(html)
print("dashboard.html generado (ábrelo en el navegador).")
