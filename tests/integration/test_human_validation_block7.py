import uuid

import psycopg

from src.pipeline.nodes.human_validation import apply_human_decision
from src.persistence.database import get_database_url


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
        rejected = apply_human_decision(conn, material_rejected, "rejeitar")
        assert rejected["status"] == "rejeitado"
        assert rejected["exports_enabled"] is False

        material_edited = _material(conn)
        created.append(material_edited)
        edited = apply_human_decision(
            conn,
            material_edited,
            "editar",
            edited_content={"title": "T", "subtitle": "S", "introduction": "i", "development": "d.", "analysis": "a.", "conclusion": "c.", "word_count_total": 5},
            source_text="Fonte curta.",
        )
        assert edited["status"] == "editado"
        assert edited["exports_enabled"] is False
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM decisoes_humanas WHERE id_material = ANY(%s)", (created,))
            cur.execute("DELETE FROM materiais WHERE id_material = ANY(%s)", (created,))
        conn.commit()
        conn.close()