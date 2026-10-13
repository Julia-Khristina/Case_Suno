"""Text export helpers."""
from src.generation.models import AnalyticalText


def to_markdown(text: AnalyticalText) -> str:
    return f"""# {text.title}

{text.subtitle}

## Introdução

{text.introduction}

## Desenvolvimento

{text.development}

## Análise

{text.analysis}

## Conclusão

{text.conclusion}
"""


def to_html(text: AnalyticalText) -> str:
    return f"""<article>
<h1>{text.title}</h1>
<h2>{text.subtitle}</h2>
<section><h3>Introdução</h3><p>{text.introduction}</p></section>
<section><h3>Desenvolvimento</h3><p>{text.development}</p></section>
<section><h3>Análise</h3><p>{text.analysis}</p></section>
<section><h3>Conclusão</h3><p>{text.conclusion}</p></section>
</article>"""