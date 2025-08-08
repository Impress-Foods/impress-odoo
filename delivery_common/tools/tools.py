import re

from lxml import etree


def text_from_html(html_fragment, collapse_whitespace=False):
    """
    Returns the plain non-tag text from an html

    :param html_fragment: document from which text must be extracted

    :return: text extracted from the html
    """
    # lxml requires one single root element
    tree = etree.fromstring("<p>%s</p>" % html_fragment, etree.XMLParser(recover=True))

    # Remove scripts or other technical elements that should not be converted
    # into text.
    xpath_filters = [
        "//script",
        "//style",
        "//svg",
        '//*[@class="css_non_editable_mode_hidden"]',
    ]
    for xpath_filter in xpath_filters:
        for element in tree.xpath(xpath_filter):
            element.getparent().remove(element)

    content = " ".join(tree.itertext())
    if collapse_whitespace:
        content = re.sub("\\s+", " ", content).strip()
    return content
