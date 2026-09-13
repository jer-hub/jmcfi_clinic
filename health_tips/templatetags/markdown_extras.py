import re

import markdown
import nh3
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Allow common markdown output tags; strip scripts/handlers.
_ALLOWED_TAGS = {
    'a', 'abbr', 'b', 'blockquote', 'br', 'code', 'div', 'em', 'h1', 'h2', 'h3',
    'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 'ol', 'p', 'pre', 'span', 'strong',
    'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul',
}
_ALLOWED_ATTRIBUTES = {
    'a': {'href', 'title', 'rel'},
    'img': {'src', 'alt', 'title'},
    'code': {'class'},
    'div': {'class', 'id'},
    'span': {'class'},
    'td': {'align', 'colspan', 'rowspan'},
    'th': {'align', 'colspan', 'rowspan'},
}
_ALLOWED_URL_SCHEMES = {'http', 'https', 'mailto'}


@register.filter(name='markdown')
def markdown_format(text):
    """
    Convert markdown text to HTML, then sanitize with nh3.
    Supports: headers, bold, italic, lists, links, images, code blocks, blockquotes, tables.
    """
    if not text:
        return ''

    md = markdown.Markdown(
        extensions=[
            'nl2br',
            'fenced_code',
            'tables',
            'toc',
            'sane_lists',
        ],
        extension_configs={
            'toc': {
                'permalink': False,
            },
        },
    )

    html = md.convert(text)
    cleaned = nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes=_ALLOWED_URL_SCHEMES,
    )
    return mark_safe(cleaned)


@register.filter(name='strip_images')
def strip_images(text):
    """
    Remove markdown image syntax and formatting from text.
    Strips images, bold, italic, headers, links, code blocks, etc.
    """
    if not text:
        return ''

    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'<img[^>]*>', '', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'\[(.+?)\]\(.*?\)', r'\1', text)
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    return text
