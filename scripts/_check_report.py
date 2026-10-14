import os
os.environ["PYTHONPATH"] = "."
from src.app.level_selection import _generate_manual_materials
ids = _generate_manual_materials("Copom mantem a taxa Selic em 10 porcento ao ano e inflacao pelo IPCA cai para 4 porcento.", ["iniciante"], "Copom")
import psycopg
conn = psycopg.connect("postgresql://suno:suno@localhost:5432/suno")
cur = conn.cursor()
cur.execute("select conteudo_gerado from materiais where id_execucao=%s and formato=%s", (ids[0]["id_execucao"], "texto_analitico"))
row = cur.fetchone()[0]
print(row["introduction"])
print("---")
print(row["development"])
conn.close()
