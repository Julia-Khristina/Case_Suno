with open('tests/regression/brent/test_brent_regression.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('resultado["materiais"][0]["conteudo_gerado"]', 'resultado[0]["materiais"][0]["conteudo_gerado"]')

with open('tests/regression/brent/test_brent_regression.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Feito")