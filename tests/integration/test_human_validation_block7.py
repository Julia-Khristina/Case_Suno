import uuid

import psycopg
import pytest

from src.pipeline.nodes.human_validation import apply_human_decision
from src.persistence.database import get_database_url


EDITED_MARKDOWN = """# T

S

## Contexto

A Selic ficou em 10,50%.

## Dados

O IPCA ficou em 4,5%.

## Riscos

Há risco fiscal.

## Síntese

A inflação segue acima da meta.

## Fonte

Fonte: BCB.
"""


def _material(conn):
    material_id = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute("INSERT INTO materiais (id_material, nivel, formato) VALUES (%s, %s, %s)", (material_id, "iniciante", "texto_analitico"))
    conn.commit()
    return material_id


def test_human_validation_flow():
    conn = psycopg.connect(get_database_url(), connect_timeout=5)
    created = []
    try:
        material_blocked = _material(conn)
        created.append(material_blocked)
        blocked = apply_human_decision(conn, material_blocked, "aprovar", pending_terms=["selic"])
        assert blocked["status"] == "bloqueado_por_termos_pendentes"
        assert blocked["exports_enabled"] is False

        material_approved = _material(conn)
        created.append(material_approved)
        approved = apply_human_decision(conn, material_approved, "aprovar")
        assert approved["status"] == "aprovado"
        assert approved["exports_enabled"] is True
        with conn.cursor() as cur:
            cur.execute("SELECT estado FROM materiais WHERE id_material = %s", (material_approved,))
            assert cur.fetchone()[0] == "aprovado"

        material_rejected = _material(conn)
        created.append(material_rejected)
        with pytest.raises(ValueError, match="motivo"):
            apply_human_decision(conn, material_rejected, "rejeitar")  # rejeitar exige motivo
        rejected = apply_human_decision(conn, material_rejected, "rejeitar", note="[Erro factual] Selic errada no slide 3")
        assert rejected["status"] == "rejeitado"
        assert rejected["exports_enabled"] is False
        # rejeitado é estado final: aprovar fica bloqueado até reabrir
        assert apply_human_decision(conn, material_rejected, "aprovar")["status"] == "bloqueado_material_rejeitado"
        assert apply_human_decision(conn, material_rejected, "reabrir")["status"] == "aguardando_revisao"
        assert apply_human_decision(conn, material_rejected, "aprovar", note="ok após reabrir")["status"] == "aprovado"
        with conn.cursor() as cur:
            cur.execute("SELECT decisao, observacao FROM decisoes_humanas WHERE id_material = %s ORDER BY criado_em",
                        (material_rejected,))
            assert cur.fetchall() == [("rejeitar", "[Erro factual] Selic errada no slide 3"), ("reabrir", None),
                                      ("aprovar", "ok após reabrir")]

        material_edited = _material(conn)
        created.append(material_edited)
        source = "A Selic ficou em 10,50%. O IPCA ficou em 4,5%. Há risco fiscal. A inflação segue acima da meta."
        with pytest.raises(ValueError, match="observação"):  # editar exige descrever a mudança
            apply_human_decision(conn, material_edited, "editar", edited_content=EDITED_MARKDOWN, source_text=source)
        edited = apply_human_decision(conn, material_edited, "editar", edited_content=EDITED_MARKDOWN,
                                      source_text=source, note="Ajustei o IPCA para 4,5%")
        assert edited["status"] == "editado"
        assert edited["evaluation"] is not None  # reavaliado no nível e formato do material (iniciante, texto)
        assert edited["exports_enabled"] is False
        with pytest.raises(ValueError, match="não foi alterado"):  # salvar de novo o mesmo texto não é edição
            apply_human_decision(conn, material_edited, "editar", edited_content=EDITED_MARKDOWN, source_text=source,
                                 note="nada mudou")
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM decisoes_humanas WHERE id_material = ANY(%s)", (created,))
            cur.execute("DELETE FROM materiais WHERE id_material = ANY(%s)", (created,))
        conn.commit()
        conn.close()