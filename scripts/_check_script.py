import psycopg
from src.app.level_selection import _generate_manual_materials

ids = _generate_manual_materials(
    "Copom mantem a taxa Selic em 10 porcento ao ano e inflacao pelo IPCA cai para 4 porcento.",
    ["iniciante"],
    "Copom",
)
conn = psycopg.connect("postgresql://suno:suno@localhost:5432/suno")
cur = conn.cursor()
cur.execute(
    "select conteudo_gerado from materiais where id_execucao = %s and formato = %s",
    (ids[0]["id_execucao"], "roteiro_video"),
)
row = cur.fetchone()[0]
for scene in row["scenes"]:
    print("Fala:", scene["spoken"])
conn.close()
