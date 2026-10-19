CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS cards (
    id_card UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo TEXT NOT NULL,
    descricao TEXT,
    tipo_fonte TEXT NOT NULL CHECK (tipo_fonte IN ('primaria', 'secundaria')),
    nome_fonte TEXT NOT NULL,
    url_fonte TEXT,
    categoria TEXT,
    motivo_entrada TEXT,
    data_card DATE,
    estado TEXT NOT NULL DEFAULT 'ativo',
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS documentos (
    hash TEXT PRIMARY KEY,
    id_card UUID REFERENCES cards(id_card),
    tipo_origem TEXT NOT NULL CHECK (tipo_origem IN ('card', 'link', 'texto', 'pdf')),
    instituicao_origem TEXT,
    titulo_origem TEXT,
    data_origem DATE,
    url_origem TEXT,
    idioma TEXT,
    status_integridade TEXT NOT NULL DEFAULT 'pendente',
    parcial BOOLEAN NOT NULL DEFAULT FALSE,
    eh_financeiro BOOLEAN,
    quantidade_termos_tecnicos INTEGER NOT NULL DEFAULT 0,
    quantidade_palavras INTEGER NOT NULL DEFAULT 0,
    caminho_texto_bruto TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS execucoes (
    id_execucao UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hash_documento TEXT REFERENCES documentos(hash),
    niveis_solicitados JSONB NOT NULL DEFAULT '[]'::jsonb,
    hash_configuracao TEXT NOT NULL,
    versao_glossario TEXT NOT NULL,
    versao_prompt TEXT NOT NULL,
    versao_modelo TEXT NOT NULL,
    versao_limiares TEXT NOT NULL,
    versao_rubrica TEXT,
    versao_estilo TEXT NOT NULL,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    latencia_total NUMERIC NOT NULL DEFAULT 0,
    estado TEXT NOT NULL DEFAULT 'em_andamento',
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS materiais (
    id_material UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_execucao UUID REFERENCES execucoes(id_execucao),
    nivel TEXT NOT NULL CHECK (nivel IN ('iniciante', 'intermediario', 'avancado')),
    formato TEXT NOT NULL CHECK (formato IN ('texto_analitico', 'carrossel', 'roteiro_video')),
    estado TEXT NOT NULL DEFAULT 'na_fila',
    conteudo_gerado JSONB,
    conteudo_editado JSONB,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tentativas (
    id_tentativa UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_material UUID REFERENCES materiais(id_material),
    numero_tentativa INTEGER NOT NULL,
    conteudo JSONB,
    metricas JSONB,
    falhas JSONB,
    motivo_reprovacao TEXT,
    tokens INTEGER NOT NULL DEFAULT 0,
    latencia NUMERIC NOT NULL DEFAULT 0,
    id_modelo TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS avaliacoes_juiz (
    id_avaliacao_juiz UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_tentativa UUID REFERENCES tentativas(id_tentativa),
    versao_rubrica TEXT NOT NULL,
    id_modelo_juiz TEXT NOT NULL,
    notas JSONB,
    justificativa TEXT,
    tamanho_texto INTEGER,
    evidencias JSONB,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decisoes_humanas (
    id_decisao UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_material UUID REFERENCES materiais(id_material),
    decisao TEXT NOT NULL CHECK (decisao IN ('aprovar', 'editar', 'rejeitar')),
    observacao TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS termos_pendentes (
    id_pendente UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    termo TEXT NOT NULL,
    definicao_proposta TEXT,
    trecho_origem TEXT,
    url_fonte TEXT,
    estado TEXT NOT NULL DEFAULT 'pendente',
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolvido_em TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS coletas (
    id_coleta UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome_fonte TEXT,
    iniciado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finalizado_em TIMESTAMPTZ,
    quantidade_itens INTEGER NOT NULL DEFAULT 0,
    erros JSONB
);

CREATE TABLE IF NOT EXISTS avaliacoes_offline_execucoes (
    id_avaliacao_offline UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hash_contexto TEXT NOT NULL,
    iniciado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finalizado_em TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS avaliacoes_offline_resultados (
    id_resultado UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_avaliacao_offline UUID REFERENCES avaliacoes_offline_execucoes(id_avaliacao_offline),
    caso_teste TEXT,
    metrica TEXT,
    resultado JSONB,
    metadados JSONB
);

CREATE TABLE IF NOT EXISTS nos_grafo (
    id_no UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo_no TEXT NOT NULL CHECK (tipo_no IN ('documento', 'trecho', 'ponto_central', 'afirmacao', 'dado', 'entidade', 'evento', 'card', 'material', 'frase_gerada', 'termo')),
    propriedades JSONB NOT NULL DEFAULT '{}'::jsonb,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS arestas_grafo (
    id_aresta UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_no_origem UUID REFERENCES nos_grafo(id_no),
    id_no_destino UUID REFERENCES nos_grafo(id_no),
    tipo_relacao TEXT NOT NULL CHECK (tipo_relacao IN ('TEM_TRECHO', 'EXTRAIDA_DE', 'SUSTENTA', 'EXTRAIDO_DE', 'SOBRE', 'TRATA_DE', 'ATUALIZA', 'APONTA_PARA', 'MENCIONA', 'TEM_FRASE', 'BASEADA_EM')),
    propriedades JSONB NOT NULL DEFAULT '{}'::jsonb,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Decisões humanas (18/10/2026): além de aprovar/editar/rejeitar, "reabrir" um rejeitado e "regenerar" (nova
-- versão gerada a partir do motivo da rejeição).
ALTER TABLE decisoes_humanas DROP CONSTRAINT IF EXISTS decisoes_humanas_decisao_check;
ALTER TABLE decisoes_humanas ADD CONSTRAINT decisoes_humanas_decisao_check
    CHECK (decisao IN ('aprovar', 'editar', 'rejeitar', 'reabrir', 'regenerar'));

-- Pautas (18/10/2026): notícias de fontes diferentes sobre o mesmo assunto, agrupadas na coleta.
CREATE TABLE IF NOT EXISTS pautas (
    id_pauta UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assunto TEXT NOT NULL,
    fontes_independentes INTEGER NOT NULL DEFAULT 1,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE cards ADD COLUMN IF NOT EXISTS id_pauta UUID REFERENCES pautas(id_pauta);

-- Acervo da coleta: tudo o que foi lido nos feeds (não só os cards escolhidos), para achar a mesma notícia
-- em fontes diferentes ao longo da janela de horas. O texto completo fica no volume, pelo hash.
CREATE TABLE IF NOT EXISTS itens_coletados (
    id_item UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL UNIQUE,
    titulo TEXT NOT NULL,
    descricao TEXT,
    nome_fonte TEXT NOT NULL,
    tipo_fonte TEXT NOT NULL DEFAULT 'secundaria',
    prioridade INTEGER NOT NULL DEFAULT 99,
    data_publicacao DATE,
    hash_texto TEXT,
    agencia TEXT,
    aceito BOOLEAN NOT NULL DEFAULT FALSE,
    motivo_exclusao TEXT,
    selecao JSONB NOT NULL DEFAULT '{}'::jsonb,
    id_pauta UUID REFERENCES pautas(id_pauta),
    id_card UUID REFERENCES cards(id_card),
    coletado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_itens_coletados_em ON itens_coletados (coletado_em);
CREATE INDEX IF NOT EXISTS idx_cards_pauta ON cards (id_pauta);

CREATE TABLE IF NOT EXISTS migracoes_schema (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    aplicado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cards_data ON cards (data_card);
CREATE INDEX IF NOT EXISTS idx_documentos_criado_em ON documentos (criado_em);
CREATE INDEX IF NOT EXISTS idx_execucoes_hash_documento ON execucoes (hash_documento);
CREATE INDEX IF NOT EXISTS idx_arestas_origem ON arestas_grafo (id_no_origem);
CREATE INDEX IF NOT EXISTS idx_arestas_destino ON arestas_grafo (id_no_destino);
CREATE INDEX IF NOT EXISTS idx_arestas_tipo ON arestas_grafo (tipo_relacao);

INSERT INTO migracoes_schema (nome)
VALUES ('001_initial_portugues')
ON CONFLICT (nome) DO NOTHING;
-- 002: registros por tentativa e por avaliação do juiz (seções 4.7 e 4.10)
ALTER TABLE materiais ADD COLUMN IF NOT EXISTS nivel_classificado TEXT;
ALTER TABLE materiais ADD COLUMN IF NOT EXISTS status_avaliacao TEXT;
ALTER TABLE materiais ADD COLUMN IF NOT EXISTS aviso TEXT;
ALTER TABLE materiais ADD COLUMN IF NOT EXISTS complexidade_fonte JSONB;
ALTER TABLE materiais ADD COLUMN IF NOT EXISTS versao_glossario TEXT;
ALTER TABLE tentativas ADD COLUMN IF NOT EXISTS nivel_classificado TEXT;
ALTER TABLE tentativas ADD COLUMN IF NOT EXISTS feedback_usado TEXT;
ALTER TABLE tentativas ADD COLUMN IF NOT EXISTS tamanho_texto INTEGER;
ALTER TABLE tentativas ADD COLUMN IF NOT EXISTS versao_prompt TEXT;
ALTER TABLE tentativas ADD COLUMN IF NOT EXISTS mudanca_vs_anterior NUMERIC;
ALTER TABLE avaliacoes_juiz ADD COLUMN IF NOT EXISTS media_ponderada NUMERIC;
ALTER TABLE avaliacoes_juiz ADD COLUMN IF NOT EXISTS aprovado BOOLEAN;
ALTER TABLE avaliacoes_juiz ADD COLUMN IF NOT EXISTS justificativas JSONB;
ALTER TABLE avaliacoes_juiz ADD COLUMN IF NOT EXISTS tokens INTEGER;
ALTER TABLE avaliacoes_juiz ADD COLUMN IF NOT EXISTS latencia NUMERIC;

INSERT INTO migracoes_schema (nome)
VALUES ('002_tentativas_juiz_rastreabilidade')
ON CONFLICT (nome) DO NOTHING;
