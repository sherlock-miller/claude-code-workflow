"""Word OMML 公式注入 — LaTeX 转 Word 原生数学公式"""

import sys
from lxml import etree
import latex2mathml.converter

OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
M = "{%s}" % OMML_NS


def latex_to_mathml(latex):
    return latex2mathml.converter.convert(latex)


def mathml_to_omml(mathml_str):
    mathml = etree.fromstring(mathml_str.encode("utf-8"))
    return _convert(mathml)


def _el(tag, parent=None, text=None):
    elem = etree.Element(tag)
    if parent is not None:
        parent.append(elem)
    if text is not None:
        elem.text = text
    return elem


def _convert(node):
    tag = etree.QName(node).localname if isinstance(node.tag, str) else ""

    if tag in ("mi", "mn", "mo", "mtext"):
        e = etree.Element(M + "r")
        _el(M + "t", e, text=(node.text or "").strip())
        return e

    if tag == "mrow":
        children = _children(node)
        if len(children) == 1:
            return children[0]
        e = etree.Element(M + "oMath") if len(children) > 1 else children[0] if children else None
        if e is not None and len(children) > 1:
            for c in children:
                e.append(c)
        return e

    if tag == "math":
        e = etree.Element(M + "oMathPara")
        for child in _children(node):
            omath = etree.Element(M + "oMath")
            omath.append(child)
            e.append(omath)
        return e

    if tag == "mfrac":
        e = etree.Element(M + "f")
        children = _children(node)
        num = _el(M + "num", e)
        den = _el(M + "den", e)
        if len(children) >= 2:
            num.append(children[0])
            den.append(children[1])
        elif len(children) == 1:
            num.append(children[0])
        return e

    if tag == "msup":
        e = etree.Element(M + "sSup")
        children = _children(node)
        base = _el(M + "e", e)
        sup = _el(M + "sup", e)
        if len(children) >= 2:
            base.append(children[0])
            sup.append(children[1])
        return e

    if tag == "msub":
        e = etree.Element(M + "sSub")
        children = _children(node)
        base = _el(M + "e", e)
        sub = _el(M + "sub", e)
        if len(children) >= 2:
            base.append(children[0])
            sub.append(children[1])
        return e

    if tag == "msqrt":
        e = etree.Element(M + "rad")
        children = _children(node)
        if children:
            _el(M + "deg", e)
            ee = _el(M + "e", e)
            for c in children:
                ee.append(c)
        return e

    if tag in ("mover", "munder"):
        e = etree.Element(M + ("acc" if tag == "mover" else "bar"))
        children = _children(node)
        base = _el(M + "e", e)
        if len(children) >= 2:
            base.append(children[0])
        return e

    # 递归默认：返回第一个有效子节点
    children = _children(node)
    if children:
        return children[0]
    return None


def _children(node):
    result = []
    if node.text and node.text.strip():
        r = etree.Element(M + "r")
        _el(M + "t", r, text=node.text.strip())
        result.append(r)
    for child in node:
        c = _convert(child)
        if c is not None:
            result.append(c)
    return result


def latex_to_omml_xml(latex):
    mathml_str = latex_to_mathml(latex)
    omml = mathml_to_omml(mathml_str)
    if omml is None:
        return ""
    return etree.tostring(omml, encoding="unicode", pretty_print=True)


if __name__ == "__main__":
    tests = [
        r"x^{2}+\sqrt{x^{2}+1}=2",
        r"\frac{d}{dx}(x^3+3x^2+2x+1)=3x^2+6x+2",
        r"\int_{-\infty}^{\infty} e^{-x^{2}} dx = \sqrt{\pi}",
        r"S_n = \sum_{k=1}^{n} \frac{1}{k^2}",
        r"\cos(2\theta) = \cos^2 \theta - \sin^2 \theta",
        r"E = mc^{2}",
        r"\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
    ]
    for t in tests:
        print(f"=== {t} ===")
        try:
            result = latex_to_omml_xml(t)
            print(result[:300])
        except Exception as e:
            print(f"  ERROR: {e}")
        print()
