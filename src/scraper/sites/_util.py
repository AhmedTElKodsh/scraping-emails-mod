from selectolax.parser import HTMLParser


def _first_text(tree: HTMLParser, selectors: list[str]) -> str:
    for sel in selectors:
        node = tree.css_first(sel)
        if node and node.text(strip=True):
            return node.text(strip=True)
    return ""


def _first_attr(tree: HTMLParser, selectors: list[str], attr: str) -> str:
    for sel in selectors:
        node = tree.css_first(sel)
        if node and node.attrs.get(attr):
            return str(node.attrs[attr])
    return ""
