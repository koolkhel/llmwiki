"""Synthetic «Суть времени» digest pages in rossaprimavera.ru markup (rp-digest-items change).

Everything here is invented: places, outlets, people and events. Only the markup
(class names, nesting, service blocks) follows the real site.
"""

from __future__ import annotations

RP_URL = "https://rossaprimavera.ru/article/0000abcd"

AD = """<div class="ad_container" id="yandex_rtb_R-A-1-3"></div>
<script>window.yaContextCb.push(function(){ Ya.Context.AdvManager.render({"blockId": "R-A-1-3"}) })</script>"""

WIDGET = """<div class="widget embed" style="padding: 0;background: #222">
<div style="font-weight: bold;">Смотрите также:</div>
<div class="preview"><iframe src="/embed/video/0000ffff"></iframe></div>
<h2><a href="/video/0000ffff">Выдуманный ролик про выдуманные дела</a></h2>
</div>"""

# What the real pages put before the first section, inside the same container as the items.
HEADER = (
    '<div class="pre_title">Выдуманная война: На фронтах; Милитарии всех стран</div>'
    "<h1>{title}</h1>"
    '<div class="back-article-0000abcd"></div>'
    '<figure class="art_img classic cover"><footer><small>Изображение: (cc)</small></footer>'
    '<img src="/x.jpg" alt="Выдуманный человек"><figcaption class="cover">Выдуманный человек</figcaption></figure>'
)

DEFAULT_BODY = (
    "<h3><strong>На фронтах</strong></h3>"
    "<p class=\"block_date\">ЗАРЕЧЬЕ, 18&nbsp;сентября&nbsp;— «Вестник»</p>"
    "<p class=\"quote\"><em>Дрон повредил</em> градирню Заречной станции, сообщил выдуманный&nbsp;агент.</p>"
    + WIDGET +
    "<p class=\"quote\">Директор станции Иван Выдуманов призвал к сдержанности.</p>"
    "<p style=\"display: none\">(служебный скрытый текст)</p>"
    "<p class=\"block_comment\">Вообще-то, тревожный звонок для выдуманной&nbsp;энергетики.</p>"
    + AD +
    "<p class=\"block_date\">ЛЕСНОЙ, 19 сентября — РИА Север</p>"
    "<p class=\"quote\">Жители Лесного получили новые фонари.</p>"
    "<h3><strong>Милитарии всех стран </strong></h3>"
    "<p class=\"block_date\">НЬЮ-ГОРОД, 20 сентября — «Газета.XX»</p>"
    "<p class=\"quote\">Нью-Город закупил сто тысяч выдуманных дронов.</p>"
    "<p class=\"block_comment\">Примечательно, что закупка совпала с выборами.</p>"
    "<p class=\"block_comment\">И это не случайность.</p>"
)


def digest_html(body: str = DEFAULT_BODY, issue_date: str | None = "2026-09-26T08:41:00+03:00",
                number: str | None = "123", title: str = "Выдуманное «обострение»") -> str:
    ld = (f'<script type="application/ld+json">{{"@context": "https://schema.org", "@type": "NewsArticle", '
          f'"headline": "{title}", "datePublished": "{issue_date}"}}</script>') if issue_date else ""
    issue = (f'<div class="subject">/ Газета «<a href="/gazeta/{number}">Суть времени</a>» №{number} /</div>'
             if number else "")
    sidebar = ('<aside><div class="gazwidget_h2">Газета «Суть времени» № 99</div>'
               '<p class="quote">Цитата из боковой колонки, не из статьи.</p></aside>')
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{title} | ИА Красная Весна</title>"
        f"<link rel='canonical' href='{RP_URL}'>{ld}</head><body>"
        f"<nav>Новости | Газета | Поиск</nav>{issue}"
        f"<article><div class=\"article_block gazeta\"><div class=\"body\">{HEADER.format(title=title)}{body}"
        f"<div class=\"comment_position\"></div></div></div></article>{sidebar}"
        f"<footer>Подвал сайта</footer></body></html>"
    )


YEAR_BOUNDARY_BODY = (
    "<h3>Итоги</h3>"
    "<p class=\"block_date\">ЗАРЕЧЬЕ, 29&nbsp;декабря&nbsp;— «Вестник»</p>"
    "<p class=\"quote\">Заречье подвело итоги выдуманного года.</p>"
    "<p class=\"block_date\">ЛЕСНОЙ, 5 января — РИА Север</p>"
    "<p class=\"quote\">В Лесном открыли каток.</p>"
)

BAD_DATELINE_BODY = (
    "<h3>Разное</h3>"
    "<p class=\"block_date\">ЗАРЕЧЬЕ — «Вестник»</p>"
    "<p class=\"quote\">Без даты.</p>"
    "<p class=\"block_date\">ЛЕСНОЙ, 19 сентября — РИА Север</p>"
    "<p class=\"quote\">С датой.</p>"
)

UNASSIGNED_BODY = (
    "<h3>Разное</h3>"
    "<p class=\"quote\">Цитата до первой строки с датой.</p>"
    "<p class=\"block_date\">ЛЕСНОЙ, 19 сентября — РИА Север</p>"
    "<p class=\"quote\">Обычная новость.</p>"
)


def article_html(title: str = "Выдуманная статья") -> str:
    """An ordinary rossaprimavera.ru article: no datelines."""
    paras = "".join(f"<p>Абзац {i} выдуманной статьи о выдуманных событиях, достаточно длинный для "
                    f"извлечения основного текста страницы.</p>" for i in range(6))
    return (f"<!DOCTYPE html><html><head><title>{title}</title>"
            f"<script type=\"application/ld+json\">{{\"@type\": \"NewsArticle\", "
            f"\"datePublished\": \"2026-09-20T10:00:00+03:00\"}}</script></head>"
            f"<body><article><h1>{title}</h1>{paras}</article></body></html>")


# Lists as on issue №681: class-less <ul> blocks with one bullet each.
LIST_AFTER_QUOTE_BODY = (
    "<h3>Земля</h3>"
    "<p class=\"block_date\">ЗАРЕЧЬЕ, 1 сентября — «Вестник»</p>"
    "<p class=\"quote\">Заречье распродало выдуманные земли. Детали:</p>"
    "<ul><li>первая выдуманная деталь;</li></ul>"
    "<ul><li><em>вторая</em> выдуманная деталь;</li></ul>"
    "<ul><li>третья выдуманная деталь.</li></ul>"
    "<p class=\"quote\">Итог выдуманной распродажи.</p>"
)

LIST_AFTER_COMMENT_BODY = (
    "<h3>Земля</h3>"
    "<p class=\"block_date\">ЗАРЕЧЬЕ, 1 сентября — «Вестник»</p>"
    "<p class=\"quote\">Новость.</p>"
    "<p class=\"block_comment\">Редакция отмечает:</p>"
    "<ul><li>первое замечание;</li><li>второе замечание.</li></ul>"
)

LIST_AFTER_DATELINE_BODY = (
    "<h3>Земля</h3>"
    "<p class=\"block_date\">ЗАРЕЧЬЕ, 1 сентября — «Вестник»</p>"
    "<ul><li>пункт сразу после даты</li></ul>"
    "<p class=\"quote\">Потом абзац.</p>"
)

LIST_BEFORE_DATELINE_BODY = (
    "<h3>Земля</h3>"
    "<ul><li>пункт до первой даты</li></ul>"
    "<p class=\"block_date\">ЗАРЕЧЬЕ, 1 сентября — «Вестник»</p>"
    "<p class=\"quote\">Новость.</p>"
)

UNKNOWN_P_BODY = (
    "<h3>Разное</h3>"
    "<p class=\"block_date\">ЗАРЕЧЬЕ, 1 сентября — «Вестник»</p>"
    "<p class=\"quote\">Первый абзац.</p>"
    "<p>Непонятный абзац</p>"
    "<p class=\"quote\">Второй абзац.</p>"
)

UNKNOWN_TABLE_BODY = (
    "<h3>Разное</h3>"
    "<p class=\"block_date\">ЗАРЕЧЬЕ, 1 сентября — «Вестник»</p>"
    "<p class=\"quote\">Таблица ниже.</p>"
    "<table><tr><td>выдуманная ячейка</td></tr></table>"
)
