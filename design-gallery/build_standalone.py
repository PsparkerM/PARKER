# -*- coding: utf-8 -*-
"""Собирает единый самодостаточный HTML-файл галереи (все 60 макетов + конструктор
цвета встроены внутрь через srcdoc). Такой файл можно переслать партнёру — он
откроет его двойным кликом в любом браузере, без сервера и без папки mockups."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK = os.path.join(HERE, "mockups")

def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()

# 1) все 60 макетов по порядку 01..60
mockups = []
for i in range(1, 61):
    mockups.append(read(os.path.join(MOCK, f"{i:02d}.html")))

# 2) конструктор цвета
builder = read(os.path.join(HERE, "theme-builder.html"))

# 3) шаблон галереи
index = read(os.path.join(HERE, "index.html"))

def js_safe(obj):
    # json.dumps + экранируем </ чтобы строка не закрыла <script>
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")

data_script = (
    "<script>\n"
    "window.MOCKUPS_DATA = " + js_safe(mockups) + ";\n"
    "window.BUILDER_DATA = " + js_safe(builder) + ";\n"
    "</script>"
)

if "<!--EMBED-->" not in index:
    raise SystemExit("Маркер <!--EMBED--> не найден в index.html")

standalone = index.replace("<!--EMBED-->", data_script)

out = os.path.join(os.path.dirname(HERE), "P.A.R.K.E.R.-дизайны-60.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(standalone)

print("Готово:", out)
print("Размер: %.0f KB" % (len(standalone.encode("utf-8")) / 1024))
print("Встроено макетов:", len(mockups), "+ конструктор цвета")
