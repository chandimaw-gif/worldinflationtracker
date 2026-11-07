import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

LINK = re.compile(r'\[([^\]]+)\]\((https?://[^\s)]+|/[^\s)]*)\)')
BOLD = re.compile(r'\*\*(.+?)\*\*')


def _inline(text):
    text = escape(text)
    text = LINK.sub(r'<a href="\2" rel="noopener">\1</a>', text)
    return BOLD.sub(r'<strong>\1</strong>', text)


@register.filter
def markdownify(text):
    """
    Render the small part of Markdown that articles use: ## headings, - bullets,
    > notes, **bold**, [links](url) and paragraphs. All other HTML is escaped.
    """
    html, paragraph, bullets = [], [], []

    def flush():
        if paragraph:
            html.append(f"<p>{_inline(' '.join(paragraph))}</p>")
            paragraph.clear()
        if bullets:
            items = ''.join(f'<li>{_inline(b)}</li>' for b in bullets)
            html.append(f'<ul>{items}</ul>')
            bullets.clear()

    for raw in (text or '').splitlines():
        line = raw.strip()
        heading = re.match(r'^(#{2,4})\s+(.*)$', line)
        if not line:
            flush()
        elif heading:
            flush()
            level = len(heading.group(1))
            html.append(f'<h{level}>{_inline(heading.group(2))}</h{level}>')
        elif line.startswith('- '):
            if paragraph:
                flush()
            bullets.append(line[2:])
        elif line.startswith('> '):
            flush()
            html.append(f'<blockquote>{_inline(line[2:])}</blockquote>')
        else:
            if bullets:
                flush()
            paragraph.append(line)
    flush()
    return mark_safe('\n'.join(html))
