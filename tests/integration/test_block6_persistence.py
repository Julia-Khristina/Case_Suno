import json
import uuid

import psycopg

from src.persistence.database import get_database_url
from src.persistence.repositories.attempt_repository import AttemptRepository
from src.persistence.repositories.judge_repository import JudgeRepository

def test_attempt_and_judge_persistence():
    material_id = str(uuid.uuid4())
    conn = psycopg.connect(get_database_url(), connect_timeout=5)
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO materiais (id_material, nivel, formato) VALUES (%s, %s, %s)", (material_id, "iniciante", "texto_analitico"))
        conn.commit()

        attempt_repo = AttemptRepository(conn)
        attempt_id = attempt_repo.create(material_id=material_id, attempt_number=1, content={"title": "x"}, metrics={"passed": True}, tokens=150, latency=1.2, model_id="generator")
        judge_repo = JudgeRepository(conn)
        judge_id = judge_repo.create(attempt_id=attempt_id, rubric_version="0.1", judge_model_id="judge", scores={"fidelidade": 9.0}, justification="ok", text_length=10, evidence=["trecho"])
        assert attempt_id
        assert judge_id
        attempts = attempt_repo.list_by_material(material_id)
        judges = judge_repo.list_by_attempt(attempt_id)
        assert len(attempts) == 1
        assert len(judges) == 1
        assert judges[0]["notas"] == {"fidelidade": 9.0}
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM avaliacoes_juiz WHERE id_tentativa IN (SELECT id_tentativa FROM tentativas WHERE id_material = %s)", (material_id,))
            cur.execute("DELETE FROM tentativas WHERE id_material = %s", (material_id,))
            cur.execute("DELETE FROM materiais WHERE id_material = %s", (material_id,))
        conn.commit()
        conn.close()