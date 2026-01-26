import re
from django import template
from django.utils.safestring import mark_safe
import markdown

register = template.Library()


@register.filter(name='markdown')
def markdown_format(text):
    """
    Convert markdown text to HTML.
    Supports: headers, bold, italic, lists, links, images, code blocks, blockquotes, tables.
    """
    if not text:
        return ''
    
    md = markdown.Markdown(
        extensions=[
            'nl2br',           # Convert newlines to <br>
            'fenced_code',     # Support ```code blocks```
            'tables',          # Support tables
            'toc',             # Table of contents
            'sane_lists',      # Better list handling
            'attr_list',       # Add attributes to elements
        ],
        extension_configs={
            'toc': {
                'permalink': False,
            },
        }
    )
    
    html = md.convert(text)
    return mark_safe(html)


@register.filter(name='strip_images')
def strip_images(text):
    """
    Remove markdown image syntax and formatting from text.
    Strips images, bold, italic, headers, links, code blocks, etc.
    """
    if not text:
        return ''
    
    # Remove markdown images: ![alt](url)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # Remove HTML img tags
    text = re.sub(r'<img[^>]*>', '', text)
    # Remove headers: # Header
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    # Remove italic: *text* or _text_
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)
    # Remove inline code: `code`
    text = re.sub(r'`(.+?)`', r'\1', text)
    # Remove code blocks: ```code```
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove links but keep text: [text](url)
    text = re.sub(r'\[(.+?)\]\(.*?\)', r'\1', text)
    # Remove blockquotes: > text
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Remove list markers
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Clean up extra whitespace
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text
