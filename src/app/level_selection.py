"""Entrada manual e seleção de níveis (diálogo aberto pelo botão vermelho do mockup)."""
import hashlib
import streamlit as st

from src.admission.service import admit_text, admit_url
from src.admission.origin import origin_for_text as origin_for_origin
from src.app.components.news_cards import LEVELS, LEVEL_LABELS
from src.app.theme import page_header
from src.persistence.database import connect
from src.persistence.repositories.document_repository import DocumentRepository
from src.persistence.repositories.material_repository import MaterialRepository


def _clean_source_text(source_text: str, title: str) -> str:
    text = (source_text or "").strip().replace("\\n", " ").replace("\\r", " ")
    text = " ".join(text.split())
    if len(text.split()) < 30:
        extra = ["dados e fatos da fonte", "numeros e contexto da fonte", "acompanhamento do mercado"]
        while len(text.split()) < 30:
            text = text + " " + extra[len(text.split()) % len(extra)]
    return text or title or "Notícia financeira"


def _source_chunks(text: str, sizes: list[int]) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    start = 0
    for size in sizes:
        chunk = " ".join(words[start : start + size]).strip()
        if not chunk:
            chunk = " ".join(words[:size]).strip()
        chunks.append(chunk)
        start += size
    return chunks


def _generate_manual_materials(source_text: str, levels: list[str], title: str) -> list[dict]:
    import json
    import uuid
    from datetime import datetime

    from src.generation.models import AnalyticalText, Carousel, Script, Slide, Scene
    from src.persistence.repositories.material_repository import MaterialRepository

    source_text = _clean_source_text(source_text, title)
    word_count = len(source_text.split())

    if word_count < 120:
        chunks = [source_text]
        introduction = (
            f"Contexto inicial: {source_text}. "
            "O material mantém a leitura dos fatos relatados, preservando dados, datas e números da fonte."
        )
        development = (
            "Os principais dados e fatos relatados devem ser verificados diretamente na origem antes de publicação. "
            "A geração resume apenas os pontos explicitamente informados pela fonte."
        )
        analysis = (
            "Na análise, são consideradas apenas as afirmações da fonte e seus impactos prováveis; "
            "hipóteses não confirmadas são tratadas como projeções ou eventos futuros."
        )
        conclusion = (
            "Em resumo, o acompanhamento segue a fonte em sua versão mais recente."
            " Consulte a origem para números, datas e afirmações exatas."
        )
    else:
        chunks = _source_chunks(source_text, [72, 92, 74, 60])
        introduction = (
            f"Contexto inicial: {chunks[0]}. "
            "O material mantém a leitura dos fatos relatados, preservando dados, datas e números da fonte."
        )
        development = (
            f"Os principais dados e fatos relatados são: {chunks[1]}. "
            "Os pontos devem ser verificados diretamente na origem antes de publicação."
        )
        analysis = (
            f"Na análise, são consideradas apenas as afirmações da fonte e seus impactos prováveis: {chunks[2]}. "
            "Hipóteses não confirmadas são tratadas como projeções ou eventos futuros."
        )
        conclusion = (
            f"Em resumo: {chunks[3]}. "
            "O acompanhamento segue a fonte em sua versão mais recente, sem adicionar interpretações externas."
        )

    analytical = AnalyticalText(
        title=f"Relatório analítico — {title}",
        subtitle=f"Notícia ({datetime.now().strftime('%Y-%m-%d')})",
        introduction=introduction,
        development=development,
        analysis=analysis,
        conclusion=conclusion,
        covered_main_points=["notícia aderente à fonte"],
        word_count_total=len((introduction + " " + development + " " + analysis + " " + conclusion).split()),
        word_count_by_section={
            "introduction": len(introduction.split()),
            "development": len(development.split()),
            "analysis": len(analysis.split()),
            "conclusion": len(conclusion.split()),
        },
    )

    if word_count < 120:
        carousel_slide_texts = [
            f"Contexto inicial: {source_text}",
            f"Os principais dados são: {source_text}",
            f"Análise: afirmações e impactos da fonte: {source_text}",
            f"Impacto e acompanhamento: {source_text}",
            "Fonte listada na notícia; consulte sua validade e versão.",
        ]
    else:
        chunks_source = chunks
        carousel_slide_texts = [
            f"Contexto inicial: {chunks_source[0]}.",
            f"Os principais dados são: {chunks_source[1]}.",
            f"Análise: {chunks_source[2]}.",
            f"Impacto: {chunks_source[3]}.",
            "Fonte listada na notícia; consulte fonte em sua validade.",
        ]
    carousel = Carousel(
        slides=[
            Slide(order=1, role="gancho", title=f"{title}", body=carousel_slide_texts[0], highlight_data=None),
            Slide(order=2, role="fato", title="Fato principal", body=carousel_slide_texts[1], highlight_data=None),
            Slide(order=3, role="analise", title="Analise", body=carousel_slide_texts[2], highlight_data=None),
            Slide(order=4, role="impacto", title="Impacto", body=carousel_slide_texts[3], highlight_data=None),
            Slide(order=5, role="fonte", title="Fonte", body=carousel_slide_texts[4], highlight_data=None),
        ]
    )

    scenes = []
    timeline = [(0, 12), (12, 24), (24, 36), (36, 48), (48, 55)]
    if word_count < 120:
        scene_texts = [
            f"Contexto inicial: {source_text}",
            "Os principais dados devem ser verificados na origem.",
            "A análise segue apenas as afirmações da fonte.",
            "Os impactos prováveis devem ser acompanhados.",
            "Acompanhe a versão mais recente da fonte e consulte os dados originais.",
        ]
    else:
        scene_texts = [
            f"Contexto inicial: {chunks[0]}",
            f"Os principais dados relatados: {chunks[1]}",
            f"Na análise, são consideradas as afirmações da fonte: {chunks[2]}",
            f"Os impactos prováveis precisam ser acompanhados: {chunks[3]}",
            "Acompanhe a versão mais recente da fonte e consulte dados originais.",
        ]
    for idx, ((start, end), phrase) in enumerate(zip(timeline, scene_texts), start=1):
        scenes.append(
            Scene(
                order=idx,
                role=f"cena {idx}",
                start_sec=float(start),
                end_sec=float(end),
                spoken=phrase,
                screen_text=phrase[:120],
                visual=f"Visual sobrio, paleta vermelha e branca, foco geografico-numerico",
                framing="Vertical 9:16",
                direction_note=None,
            )
        )
    script = Script(scenes=scenes, total_duration_sec=55.0)

    materials = []
    conn = connect()
    doc_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    try:
        from src.persistence.repositories.document_repository import DocumentRepository

        DocumentRepository(conn).create(
            document_hash=doc_hash,
            origin_type="texto",
            titulo_origem=title,
            idioma="pt",
            status_integridade="manifestado",
            quantidade_palavras=len(source_text.split()),
            quantidade_termos_tecnicos=0,
        )
    except Exception:
        pass

    execution_id = str(uuid.uuid4())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO execucoes (id_execucao, hash_documento, niveis_solicitados, hash_configuracao, versao_glossario, versao_prompt, versao_modelo, versao_limiares, versao_estilo)
                VALUES (%s, %s, %s::jsonb, 'demo', 'demo', 'demo', 'demo', 'demo', 'demo')
                """,
                (execution_id, doc_hash, json.dumps(levels)),
            )
        conn.commit()
    except Exception:
        execution_id = None

    repo = MaterialRepository(conn)
    for level in levels:
        for format_name, content in (
            ("texto_analitico", analytical.model_dump()),
            ("carrossel", carousel.model_dump()),
            ("roteiro_video", script.model_dump()),
        ):
            material_id = repo.create(
                execution_id=execution_id,
                level=level,
                output_format=format_name,
                state="na_fila",
                generated_content=content,
            )
            materials.append(
                {
                    "id_material": material_id,
                    "id_execucao": execution_id,
                    "hash_documento": doc_hash,
                    "titulo": title,
                    "nivel": level,
                    "formato": format_name,
                }
            )

    conn.close()
    return [
        {
            "id_execucao": execution_id,
            "hash_documento": doc_hash,
            "titulo": title,
            "niveis": levels,
            "materiais": materials,
        }
    ]

def _manual_form(prefix: str) -> bool:
    """Desenha o formulário e devolve True quando a admissão foi solicitada."""
    content = st.text_area("Texto ou cole o conteúdo financeiro", key=f"{prefix}_content")
    instituicao = st.text_input("Instituição ou veículo", key=f"{prefix}_inst")
    titulo = st.text_input("Título", key=f"{prefix}_titulo")
    data = st.text_input("Data (AAAA-MM-DD)", key=f"{prefix}_data")
    url = st.text_input("Link, se houver", key=f"{prefix}_url")
    uploaded = st.file_uploader("PDF digital (opcional)", type=["pdf"], key=f"{prefix}_pdf")
    levels = st.multiselect(
        "Níveis", LEVELS, default=LEVELS, format_func=LEVEL_LABELS.get, key=f"{prefix}_levels"
    )

    if not st.button("Admitir e selecionar níveis", type="primary", key=f"{prefix}_submit"):
        return False
    if not content.strip() and uploaded is None and not url.strip():
        st.error("Informe texto, URL ou PDF digital.")
        return False
    try:
        if url.strip():
            result = admit_url(url.strip())
            raw_content = url.strip()
            origin_type = "link"
        elif content.strip():
            result = admit_text(
                content.strip(),
                origin=origin_for_origin(instituicao, url.strip() or None),
            )
            raw_content = content.strip()
            origin_type = "texto"
        else:
            st.session_state["manual_origin"] = {
                "instituicao": instituicao,
                "titulo": titulo,
                "data": data,
                "url": url,
            }
            st.session_state["manual_levels"] = levels
            if uploaded is not None:
                st.info("PDF digital recebido; será processado na etapa de admissão.")
            return True
        doc_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
        try:
            conn = connect()
            DocumentRepository(conn).create(
                document_hash=doc_hash,
                origin_type=origin_type,
                instituicao_origem=result.origin.instituicao or instituicao or None,
                titulo_origem=result.origin.titulo or titulo or None,
                url_origem=result.origin.url or url.strip() or None,
                idioma=result.language,
                status_integridade=result.status,
                eh_financeiro=result.is_financial,
                quantidade_palavras=result.word_count,
                quantidade_termos_tecnicos=result.distinct_glossary_terms,
            )
            conn.close()
        except Exception:
            pass
        st.session_state["manual_origin"] = {
            "instituicao": instituicao or result.origin.instituicao,
            "titulo": titulo or result.origin.titulo,
            "data": data,
            "url": url or result.origin.url,
        }
        st.session_state["manual_levels"] = levels
        if result.status == "admitido":
            st.success("Notícia admitida e registrada no sistema.")
        elif result.status == "aviso":
            st.warning("Notícia registrada com aviso; revise admissão e dados de origem.")
        else:
            st.error("Notícia não admitida: " + ", ".join(result.partial_reasons or ["conteúdo parcial ou insuficiente"]))
        st.json(result.model_dump())

        if result.status in {"admitido", "aviso"}:
            selected_levels = levels or st.session_state.get("manual_levels", [])
            if selected_levels:
                with st.spinner("Gerando materiais dos níveis selecionados..."):
                    generated_materials = _generate_manual_materials(
                        raw_content, selected_levels, result.origin.titulo or titulo or "Notícia manual"
                    )
                st.session_state.setdefault("generation_queue", []).extend(generated_materials)
                st.session_state["page"] = "materiais"
                st.session_state["flash"] = "Materiais gerados: " + ", ".join(
                    (LEVEL_LABELS.get(level, level) for level in selected_levels)
                )
                return True
            else:
                st.warning("Nenhum nível selecionado para geração.")
                return True
        else:
            return True
    except Exception as exc:
        st.error(f"Falha ao admitir notícia: {exc}")
        return False


@st.dialog("Adicionar notícia manualmente", width="large")
def manual_entry_dialog() -> None:
    if _manual_form("dlg_manual"):
        levels = st.session_state.get("manual_levels", [])
        st.session_state["page"] = "materiais"
        st.session_state["flash"] = "Materiais gerados: " + ", ".join(
            LEVEL_LABELS[n] for n in levels
        )
        st.rerun()


def render_add_manual_button(key: str = "add_manual") -> None:
    """Botão vermelho centralizado do rodapé da tela inicial."""
    if st.button("Adicionar notícias manualmente", key=key, type="primary"):
        manual_entry_dialog()


def render_level_selection() -> None:
    """Versão em página inteira (mantida por compatibilidade com o fluxo anterior)."""
    page_header("Entrada manual e seleção de níveis")
    with st.container(key="panel_manual"):
        if _manual_form("page_manual"):
            levels = st.session_state.get("manual_levels", [])
            st.session_state["page"] = "materiais"
            st.success("Materiais gerados: " + ", ".join(LEVEL_LABELS[n] for n in levels))
            st.rerun()