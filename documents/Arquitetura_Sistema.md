# Arquitetura do Sistema: Case Suno 

## 1. Como ler este documento

Cada item traz um status:

- **Decidido**: definido.
- **Recomendado**: proposta, ainda não confirmada.
- **Em aberto**: sem decisão.
- **Do case**: exigência do documento do case.

Itens que dependem de fatos externos (termos de uso, limites de planos, estado de bibliotecas) estão marcados como **verificar**: não foram confirmados em profundidade.

## 2. Contexto e objetivo

**Problema (do case).** O mercado financeiro publica comunicados densos (atas do Copom, fatos relevantes, relatórios de inflação, releases de resultado). Resumos por LLM costumam encurtar ou trivializar o conteúdo, e a validação costuma depender de um LLM-as-a-judge sujeito a viés de complacência e de extensão.

**Objetivo (Decidido).** Manter as pessoas informadas sobre o que está acontecendo de verdade no mercado, e não só sobre eventos já passados, por meio de materiais adaptados ao nível de conhecimento de cada público.

**Escopo técnico (Do case).** Um sistema em grafo com estado que recebe documentos financeiros e gera conteúdo para 3 níveis (Iniciante, Intermediário, Avançado) em 3 formatos (Texto Analítico, Carrossel, Roteiro de Vídeo de até 60s), totalizando 9 saídas por documento. O diferencial é o **Avaliador Híbrido de Calibração e Rigor**, com métricas determinísticas, extração de entidades e julgamento estruturado.

**Premissas.** Projeto individual (Decidido). Execução em Docker local (Decidido). Modelo de linguagem em plano gratuito (Decidido), com o Groq travado como provedor (Decidido nesta sessão de análise); dois modelos distintos, um para gerar e um para julgar, com IDs fixados em configuração e teste de qualidade em português antes da entrega (Decidido nesta sessão de análise). Usuário único e sem login, já que roda localmente (Recomendado).

## 3. Visão geral do fluxo

1. **Coleta**: um agente varre as fontes todos os dias às 8h, com botão de atualização manual (Decidido).
2. **Triagem e ranking**: regras determinísticas escolhem os cards do dia (Recomendado).
3. **Cards**: título, breve descrição e fonte (Decidido).
4. **Seleção**: o humano escolhe um card ou envia link ou texto, e marca quais níveis gerar (Decidido).
5. **Admissão e integridade**: o conteúdo é limpo, classificado e checado antes de entrar no sistema (regra de classificação de texto colado na seção 4.3).
6. **Extração e âncora**: pontos centrais, números e afirmações são extraídos e guardados com o trecho de origem (Do case).
7. **Geração**: para cada nível escolhido, o gerador recebe os pontos centrais com seus trechos de origem, os dados numéricos, as entradas do glossário e as regras do nível e do formato, e produz texto analítico, carrossel com legenda e roteiro de vídeo (Do case + Recomendado).
8. **Avaliação híbrida**: métricas determinísticas primeiro, juiz estruturado depois (Do case).
9. **Reflexão**: se o nível não for atendido, o grafo reprocessa com o relatório de falha, dentro de um limite de tentativas (Do case).
10. **Validação humana**: a mesma pessoa que escolheu valida o resultado, depois do juiz (Decidido).
11. **Renderização e exportação**: slides do carrossel em imagens, roteiro para gravação ou para IA, texto em Markdown e HTML; só depois da aprovação (Decidido + Recomendado).
12. **Dashboard**: matriz de saídas, pontuações, rastreabilidade e cota de tokens do dia (Do case + Recomendado).

Os dados ficam em dois armazenamentos: um grafo para conhecimento ligado (documentos, trechos, afirmações, entidades, eventos e relações entre cards) e um banco relacional para registros operacionais (materiais, tentativas, pontuações, decisões, custos e execuções de avaliação). A divisão é descrita na seção 5 e ainda está em avaliação.

## 4. Componentes

### 4.1 Coleta e curadoria dos cards

**Fontes.** A lista varrida (Decidido) é composta por fontes brasileiras, priorizando as primárias (Recomendado):

| Fonte | Tipo | Conteúdo | Endereço |
| --- | --- | --- | --- |
| Banco Central (Copom) | Primária | Atas e comunicados | https://www.bcb.gov.br/publicacoes/atascopom/cronologicos |
| Banco Central (página do Copom) | Primária | Visão geral | https://www.bcb.gov.br/controleinflacao/copom |
| Banco Central (dados abertos) | Primária | Conjunto de atas e comunicados | https://dadosabertos.bcb.gov.br/dataset/atas-comunicados-copom |
| CVM (dados abertos) | Primária | Portal de dados | https://dados.cvm.gov.br/ |
| CVM (documentos IPE) | Primária | Fatos relevantes e comunicados | https://dados.cvm.gov.br/dataset/groups/cia_aberta-doc-ipe |
| CVM (institucional) | Primária | Notícias e normas | https://www.gov.br/cvm/pt-br |
| B3 (RI) | Primária | Relações com investidores | https://ri.b3.com.br/pt-br/ |
| IBGE | Primária | IPCA e indicadores | https://www.ibge.gov.br |
| IBGE (Agência de Notícias) | Primária | Releases de divulgações | https://agenciadenoticias.ibge.gov.br |
| Forbes Brasil | Secundária | Manchetes | https://forbes.com.br/ |

A Forbes entra apenas como fonte de manchetes para os cards, com link, sem usar o texto como base de extração (Recomendado). Releases de empresas não serão coletados automaticamente de páginas de relações com investidores. Quando o usuário inserir manualmente um release, ele recebe o mesmo tratamento dos demais documentos financeiros, sem lista predefinida de empresas nem restrição a empresas monitoradas. **Verificar**: existência de feeds ou APIs, termos de uso e robots.txt de cada fonte antes de montar o coletor. Yahoo Finance, Yahoo News e Google Finance foram descartados por idioma, tipo de conteúdo e restrições de coleta.

**Cadência.** Varredura diária às 8h (Decidido), no fuso de Brasília (Recomendado), mais um botão de atualização manual (Recomendado). Em Docker local o agendamento roda de verdade dentro de um serviço do compose.

**Categorias de card (Recomendado).** Para atender ao objetivo de informar sobre o que está acontecendo, os cards se dividem em: *acabou de acontecer* (decisão do Copom, IPCA divulgado, resultado, fato relevante) e *em andamento* (histórias que se desdobram). Não há categoria "vem aí"; informações futuras presentes nas fontes fornecidas continuam sendo identificadas e classificadas pelo extrator como projeções ou eventos futuros, conforme a seção 4.4. Fontes e integrações dedicadas exclusivamente a calendários de eventos futuros não fazem parte do escopo, e não há coleta automática de releases em páginas de relações com investidores (veja a seção 17).

**Seleção dos cards.** Notícias menos técnicas também entram (Decidido). A densidade técnica não filtra. O ranking usa uma pontuação transparente (Recomendado) com os sinais: tipo de evento (hierarquia fixa), recência, integridade do conteúdo, ausência de duplicata, variação declarada na fonte e diversidade de assuntos. A triagem é feita por regras antes de qualquer chamada a LLM, para controlar custo e tempo. Quando uma notícia de veículo e um documento primário tratam do mesmo evento, vira um único card apontando para o primário. O card mostra o motivo de ter entrado (Recomendado).

**Título, fonte e descrição.** Fonte e título vêm do metadado de origem, sem reescrita por modelo: documentos primários usam um modelo de texto (por exemplo, 'Ata do Copom nº X, data') e manchetes usam o título original (Recomendado). A breve descrição pode usar LLM, sempre checada contra o texto de origem (Recomendado). Como a varredura diária também gasta a cota do plano gratuito, a descrição pode ser extrativa (o início do documento) e o LLM entra só para os cards escolhidos (Recomendado).

**Limite diário de cards.** Em aberto. Será calibrado por medição (seção 8), não por palpite.

**Histórico.** Cards antigos ficam visíveis só com um filtro de até uma semana antes do dia atual (Decidido). Esconder não é apagar: os dados permanecem no banco (Recomendado).

### 4.2 Interface

- **Cards**: título, breve descrição e fonte (Decidido); marcação de fonte primária ou secundária e motivo de entrada (Recomendado).
- **Entrada manual**: link e texto colado (Decidido). Upload de PDF foi adiado por você, com OCR para depois. Decidido: aceitar PDF com texto digital, que está no escopo do case e não exige OCR; se a extração trouxer pouco texto, o sistema pede para colar.
- **Clique no card**: abre a seleção de níveis e inicia a geração (Decidido). Todos os níveis vêm marcados por padrão, com estimativa de tempo antes de confirmar (Recomendado).
- **Seleção de níveis**: o botão permite escolher só os níveis (Iniciante, Intermediário, Avançado), e não os formatos (Decidido). Os níveis restantes podem ser gerados depois, no mesmo card, reaproveitando a extração (Recomendado). A matriz de saídas mostra as células ainda não geradas com um botão para gerar (Recomendado).
- **Estado e cota**: a tela mostra os estados (na fila, extraindo, gerando, avaliando, aguardando revisão), permite uma tarefa ativa por card, reaproveita resultados já gerados para o mesmo conteúdo e mostra a cota de tokens restante do dia (Recomendado).
- **Erros**: toast com a causa real (Decidido). Para link que exige login: 'Não consegui acessar a página pois exige login, mande por texto' (Decidido).
- **Painel do glossário**: você decidiu que o painel permite editar os arquivos de glossário e de apelidos, e a aprovação de termos pendentes faz parte disso (Decidido). Mantido o combinado: o painel permite adicionar, aprovar e editar entradas, com validação do esquema e registro de versão a cada alteração (detalhes Recomendados).
- **Exportação**: botões de exportação ativos só depois da aprovação humana (Recomendado). Detalhes na seção 4.6.

### 4.3 Admissão e integridade

- **Links**: a página é lida com Playwright e passa por limpeza do conteúdo antes de entrar no banco (Decidido). Em Docker, o coletor roda em serviço separado (Recomendado).
- **Conteúdo parcial**: paywall costuma entregar só o começo do texto. Checagens determinísticas após a limpeza: tamanho mínimo, texto termina em frase completa, ausência de marcadores como 'assine para continuar'. Se falhar, o conteúdo é marcado como parcial e a geração é bloqueada, com toast explicativo (Recomendado).
- **O texto é financeiro?** Decidido: regra determinística, com pelo menos 5 termos distintos do glossário e 200 palavras; caso contrário, aviso com a opção de seguir mesmo assim. A extração estruturada que classifica o tipo de documento num conjunto fechado de categorias, incluindo 'não financeiro', fica como metadado e sinal auxiliar: em caso de divergência, a regra determinística é o árbitro e a classificação estruturada não veta a entrada (Decidido nesta sessão de análise). Os limiares da contagem e o calibrador com exemplos positivos e negativos reais seguem recomendados.
- **Origem obrigatória na entrada manual (Recomendado)**: para link, o sistema extrai instituição, título e data da página; para texto colado, o formulário pede instituição ou veículo, título, data e link, se houver. Sem esses dados o bloco de fonte, montado por regra, não pode ser gerado. Sem origem informada, o material mostra 'texto enviado pelo usuário'.
- **Idioma (Recomendado)**: detecção de idioma na admissão. Texto fora do português é recusado ou avisado, porque a legibilidade e o glossário são calibrados para o português.
- **Conteúdo coletado é dado, nunca instrução (Recomendado)**: páginas e textos enviados podem conter instruções escondidas dirigidas ao modelo. O extrator e o gerador tratam o conteúdo como material a analisar, e as saídas estruturadas validadas por Pydantic limitam o que um texto malicioso pode causar.
- **Documentos longos (Decidido nesta sessão de análise)**: divisão por sentença/pragações preservando os offsets de origem, com uma segunda passagem de agregação dos pontos centrais; chunks sem afirmações verificáveis são descartados. Uma saída que não consiga mapear trecho exato para uma afirmação não entra no grafo. A divisão continua acontecendo dentro do limite de tokens do modelo e as agregações alimentam a extração normal.

### 4.4 Extração e âncora

- O extrator produz até três pontos centrais ranqueados, números-chave e afirmações. Cada afirmação guarda o **trecho exato de origem** e um **tipo**: fato consumado, projeção ou evento futuro (Do case + Recomendado). A distinção impede apresentar expectativa como fato. Quando a fonte as declara, as afirmações também são marcadas como causa, impacto, risco ou fator a acompanhar, para alimentar a Análise e a Conclusão do texto (Recomendado).
- Os dados numéricos são guardados com indicador, valor, unidade, período de referência e trecho de origem (Recomendado). Servem para checar que todo número do material existe na fonte.
- **Mudanças**: o sistema só reproduz mudanças que a própria fonte declara (Decidido). O extrator marca a afirmação como variação declarada. Não há comparação entre documentos nem um 'o que mudou' calculado pelo sistema, porque isso seria uma inferência que nenhuma fonte fez.
- Entidades e eventos são normalizados pela lista de apelidos (seção 4.5).
- **Mesma história**: a ligação entre cards usa o nome do evento e os responsáveis (Decidido). Refinamentos (Recomendado): responsável como organização antes de pessoas; data de referência do evento quando existir; proximidade no tempo apenas como desempate; **na dúvida, não ligar**, porque um card sem vínculo é um erro barato e um vínculo errado engana o usuário.
- **Fato novo numa história em andamento**: cria um card novo (Decidido), ligado ao anterior por uma relação 'atualiza' que serve só de navegação, sem cálculo de diferenças (Recomendado). O card antigo pode ficar invisível depois de alguns dias, pelo filtro de uma semana (Decidido), mas os dados permanecem no banco e o card mostra um aviso 'há uma atualização' (Recomendado).
- **Validação do extrator**: um erro aqui contamina tudo o que vem depois, então o extrator é testado nos documentos de referência (seção 8) (Recomendado).

**Padrões do extrator (Recomendado).** O modelo ranqueia os pontos centrais pela importância indicada na própria fonte (título, resumo, ênfase) e registra a justificativa. Documentos longos são divididos em partes no limite de tokens, e os pontos são agregados por uma segunda passagem. Causa, impacto e risco só são marcados quando a fonte os declara.

### 4.5 Glossário e apelidos

**Dois arquivos separados (Decidido).**

- **Glossário de termos técnicos**: conceitos financeiros (Selic, hiato do produto, EBITDA ajustado). Serve à densidade de termos, à detecção de jargão e às explicações do nível Iniciante.
- **Lista de apelidos**: nomes próprios e suas variações, para reconhecer a mesma instituição, empresa ou evento em textos diferentes (por exemplo, BC, BCB e Bacen; códigos de negociação de ações). Alimenta a ligação entre cards.

**Formato (Recomendado).** YAML versionado no repositório, validado por Pydantic na leitura. Campos do glossário: termo, variações, nível (iniciante, intermediário ou avançado), explicação para o Iniciante, explicação geral de impacto (Decidido, ver 4.6), pronúncia (opcional, usada na narração por IA), fonte da definição com data de consulta, trecho original e status (aprovado, pendente, sem definição, autoria manual). Campos dos apelidos: id, tipo (instituição, empresa, evento recorrente), nome canônico e apelidos. O id vira o nó correspondente no grafo. Regra de validação: a mesma variação não pode apontar para dois termos.

**Cobertura (Recomendado).** O glossário precisa cobrir os três níveis, inclusive o jargão avançado, senão a métrica de densidade penaliza textos Avançados corretos. O tamanho inicial é guiado pela frequência dos termos nos documentos reais de teste, e a cobertura é medida (fração dos termos técnicos dos documentos de teste presentes no glossário).

**Autoria (Decidido).** Você define e aprova o glossário, começando por termos corriqueiros em notícias de finanças.

**Fluxo de termo pendente (Decidido, com detalhes Recomendados).**

1. O sistema encontra no texto um termo técnico fora do glossário.
2. Busca a definição só nas fontes autorizadas: o [glossário de Cidadania Financeira do Banco Central](https://www.bcb.gov.br/content/cidadaniafinanceira/documentos_cidadania/Informacoes_gerais/glossario_cidadania_financeira.pdf) e o [glossário do Bora Investir da B3](https://borainvestir.b3.com.br/glossario/). Não usa conhecimento do próprio modelo. Se nenhuma tiver o termo, fica 'sem definição' e você escreve a explicação.
3. A descrição proposta aparece numa mensagem pedindo aprovação, junto do trecho original e do link da fonte. O material não pode ser aprovado enquanto houver termo pendente.
4. Você aprova, edita ou rejeita. Se rejeitar, escreve a definição na hora (Decidido). Ela entra no glossário com status 'autoria manual', com data, e passa pela métrica de legibilidade do nível Iniciante.
5. O resultado da busca fica guardado, para o resultado não mudar entre execuções.

**Versões (Decidido).** Edições do glossário valem só para materiais novos. Cada material guarda a versão (hash) do glossário usada. Os resultados reportados no relatório devem vir de uma versão congelada. **Verificar**: o BCB e a B3 provavelmente cobrem melhor termos básicos do que o jargão avançado.

**Outros arquivos de configuração.**

- Verbos de ação da legenda: compartilhar, curtir, comentar e salvar, com as formas do imperativo (Decidido).
- Termos proibidos: expressões sensacionalistas e promessas (Recomendado).
- Guia de estilo do projeto: voz sóbria e factual em português do Brasil, uma linha por nível, sem emojis (sem emojis é Decidido). Como não há material de tom de voz nem exemplos publicados da Suno (Decidido), o guia e duas ou três legendas e carrosséis de exemplo por nível são escritos por você (Recomendado).
- Estrutura do texto analítico: instruções por seção (Decidido).
- Vocabulário controlado de enquadramentos para o roteiro: close, plano médio, plano aberto (Recomendado).
- Tokens visuais do design system, extraídos do guia de marca da Suno (Decidido a origem; formato Recomendado).
- Limiares por nível (Em aberto).

### 4.6 Geração 3×3

**Níveis (Do case).**

- *Iniciante*: nenhum jargão sem analogia cotidiana, foco no impacto prático no bolso.
- *Intermediário*: vocabulário padrão de mercado (CDI, Selic, IPCA, dividendos), foco em alocação e tendências.
- *Avançado*: jargão pleno (curva de juros, forward guidance, hiato do produto, EBITDA ajustado, covenants), foco analítico e metodológico.

**Níveis a gerar (Decidido).** O usuário escolhe os níveis no clique. A suíte de avaliação offline sempre gera os três, para a matriz de confusão de níveis (Recomendado).

**Entrada do gerador (Recomendado).** O gerador recebe os três pontos centrais, cada um com suas afirmações e o trecho original correspondente, os dados numéricos, as entradas do glossário dos termos presentes, as regras do nível e do formato, o guia de estilo e a lista de termos proibidos. Não recebe o documento inteiro nem documentos anteriores. Assim cada frase gerada continua ligada a uma afirmação ancorada, a nuance do trecho original não se perde e o custo em tokens cai.

**Regra de fidelidade (Decidido).** O material sempre segue o original, com simplificação ou não, mas nunca o modificando. Para tornar a regra testável (Recomendado):

- *Permitido*: reformular, trocar jargão por explicação, omitir detalhe secundário, reorganizar a ordem.
- *Proibido*: alterar números, datas ou a direção de uma variação; mudar o grau de certeza (projeção apresentada como fato); acrescentar afirmações factuais que a fonte não faz; omitir algo cuja ausência muda o sentido; calcular mudanças comparando documentos.
- *Analogia*: só sinônimo ou explicação de termo técnico, nunca história ou narrativa (Decidido). A analogia explica o termo, não o acontecimento, e usa as explicações aprovadas do glossário.
- *Informações futuras presentes na fonte*: o material relata o que a fonte diz sobre projeções e eventos futuros, sem previsão própria do sistema.
- *Sem recomendação de compra ou venda* (Recomendado) e *sem emojis* em nenhum material (Decidido).
- *Impacto prático no Iniciante* (Decidido): o case pede foco no impacto no bolso, o que é uma inferência. Solução adotada: um campo no glossário com explicações gerais de impacto, aprovadas por você, que o gerador só pode usar com o marcador 'Em geral,'. A checagem confirma que toda frase com o marcador existe no glossário.

**Orquestração (Do case).** Fluxo com estado em LangGraph ou Pydantic AI, com nós de extração, adaptadores por audiência, sintetizadores por formato, avaliador e roteamento condicional. Decidido: LangGraph. A interface usa Streamlit (Decidido). Com o limite de tokens por minuto do plano gratuito, o paralelismo não encurta o tempo (seção 7).

#### Texto analítico (Decidido, com detalhes Recomendados)

- **Estrutura (Decidido, com ajustes aceitos)**: título, subtítulo e quatro seções em ordem, com as instruções de cada uma em arquivo de configuração. Tudo baseado na fonte e sem chamada para ação, que fica na legenda do Instagram.

| Seção | Função | Regra de fidelidade |
| --- | --- | --- |
| Introdução (contextualização) | Apresentar o tema, explicar por que ele importa e formular a questão central | A relevância vem da fonte ou da explicação geral aprovada do glossário |
| Desenvolvimento (evidências) | Dados, indicadores ou acontecimentos que ajudam a entender o cenário | Todo número e data existe na fonte |
| Análise (implicações) | Causas, impactos e riscos | Só os que a fonte declara; se ela não detalha, a seção fica curta ou avisa isso |
| Conclusão (síntese) | Retomar a questão central, resumir o que a fonte conclui e indicar o que acompanhar | Sem opinião própria; só fatores que a própria fonte indica |

- **Pontos centrais**: cada parágrafo registra os pontos centrais que cobre, e a verificação confere que os três aparecem em algum lugar do texto. O extrator marca as afirmações também como causa, impacto, risco ou fator a acompanhar, para alimentar a Análise e a Conclusão.
- **Intertítulos**: os nomes das seções acima são papéis internos. Para o leitor, intertítulos curtos e informativos gerados pelo modelo (Recomendado).
- **Tamanho (Decidido)**: o mesmo intervalo de palavras para os três níveis, para a diferença vir do vocabulário, da densidade de termos e do foco, e não do tamanho. O intervalo vale por formato: o texto tem o seu, e o carrossel e o roteiro têm limites próprios, também iguais entre os níveis. Ponto de partida a calibrar para o texto: 350 a 500 palavras, com proporção por seção de 15% na introdução, 35% no desenvolvimento, 30% na análise e 20% na conclusão (Decidido).
- **Caixa 'Entenda os termos' (Recomendado)**: só no Iniciante, no fim do texto, depois da conclusão e antes da fonte. Lista os termos técnicos do texto com as explicações aprovadas do glossário, montada por regra, sem o modelo e fora da contagem de palavras.
- **Impacto prático no Iniciante (Decidido)**: usa o campo de explicação geral de impacto do glossário, com o marcador 'Em geral,'.
- **Verificações**: as quatro seções existem, na ordem; os três pontos centrais presentes; contagem de palavras total e por seção; limites de caracteres de título e subtítulo; limite de tamanho de parágrafo; todo número e data (inclusive no título) existe na fonte; toda causa, impacto ou risco corresponde a uma afirmação da fonte; legibilidade e densidade de termos na faixa do nível; no Iniciante, cada termo técnico com explicação dentro de uma janela curta de palavras; bloco de fonte igual ao montado por regra; sem emojis, sem termos proibidos e sem linguagem de recomendação.
- **Exportação**: pré-visualização como artigo, exportação em Markdown e HTML e opção de copiar o texto. O local de publicação está em aberto e não bloqueia nada.
- **Custo**: é o formato com a maior saída, estimada em 800 a 1.000 tokens por material (hipótese a medir).

#### Carrossel e legenda (Instagram)

- **Estrutura (Decidido)**: 5 slides: gancho na capa, três de corpo (um ponto central por slide) e conclusão. Sem slide dedicado de chamada para ação. O gancho se apoia em um fato ou número da fonte, sem exagero que o distorça (Recomendado).
- **Legenda (Decidido: o sistema a gera)**: abertura com o ponto central, contexto curto na linguagem do nível, fonte montada por regra, chamada para ação, aviso institucional se houver configuração ativa (nenhum texto obrigatório confirmado pela Suno; a frase "Conteúdo educativo. Não é recomendação de investimento." é apenas uma sugestão provisória e não oficial, e a geração não é bloqueada pela ausência de aviso) e hashtags derivadas das entidades reconhecidas, se você quiser (estrutura Recomendada). O tamanho máximo é de 2.000 caracteres, por segurança (Decidido), e respeita o limite do Instagram (**verificar**).
- **Chamada para ação (Decidido: só na legenda)**: um verbo da lista (compartilhar, curtir, comentar, salvar) mais uma frase ligada ao conteúdo, gerada. Regras (Recomendado): sem afirmação factual nova, sem números, sem incentivo a comprar ou vender, tamanho limitado.
- **Design system (Decidido)**: padrão visual da Suno a partir do guia de marca, do logotipo e das fontes, que você possui com permissão de uso. Paleta apenas vermelha e branca. Os valores do guia entram em um arquivo de tokens, com poucos modelos de slide (capa, texto, dado em destaque, conclusão) (Recomendado).
- **Indicador de nível (Decidido)**: o mesmo padrão para os três níveis, com uma linha vermelha sutil cuja posição muda: Iniciante em cima, Intermediário nas laterais (duas linhas verticais, uma em cada lado) e Avançado embaixo. O rótulo exibido é separado do nome interno do nível, e sobre fundo vermelho a linha passa a branca (Recomendado).
- **Formato técnico (Recomendado, verificar no Instagram)**: 1080 × 1350 px (proporção 4:5) em PNG; título da capa centralizado, porque a grade do perfil recorta o primeiro slide em 3:4; margens de segurança; limite de slides configurável (hoje 5).
- **Renderização**: HTML e CSS com Playwright, sem LLM, depois da avaliação textual e antes da sua validação; a pré-visualização usa os mesmos modelos. As fontes são carregadas dos arquivos do projeto, e o renderizador espera o carregamento antes de capturar a imagem. Exportação em um PNG por slide, numerados, mais um ZIP, depois da aprovação (visualização e exportação de imagens: Decidido).
- **Verificações determinísticas (Recomendado)**: o texto cabe no campo (medido na renderização); limites de caracteres por campo; contraste entre texto e fundo, com os valores reais do guia; posição da linha igual ao nível; número de slides; gancho e conclusão presentes; sem emojis nem termos proibidos; chamada com verbo da lista, considerando o imperativo.

#### Roteiro de vídeo (Reels)

- **Plataforma (Decidido)**: Instagram Reels, vertical (9:16), até 60 segundos (limite do case). Legenda e chamada para ação como no carrossel.
- **Estrutura (Decidido: mesma lógica do carrossel)**: JSON estruturado, regras de formato e verificações. Cinco cenas (gancho, três de corpo e conclusão), com os mesmos três pontos centrais.
- **Campos da cena (Recomendado)**: ordem; papel; início e fim em segundos; fala escrita, que o avaliador confere contra a fonte; fala falada, derivada por regra com números, porcentagens e datas por extenso; texto na tela; visual (descrição, elementos na tela, movimento); enquadramento e observação de direção para a gravação por pessoa, em vocabulário controlado (close, plano médio, plano aberto).
- **Verificações determinísticas (Recomendado)**: soma das cenas até 60 segundos, com tempos contínuos e sem sobreposição; palavras de cada fala compatíveis com a duração (cerca de 2 a 3 palavras por segundo, a calibrar lendo em voz alta); limite de palavras por frase; limite de caracteres no texto na tela; gancho na primeira cena e conclusão na última; todo número citado no visual existe na fonte; o visual não retrata pessoas reais identificáveis; sem emojis nem termos proibidos.
- **Exportação para pessoa (Decidido)**: cenas com marcações de tempo, fala corrida, texto na tela, indicação do que mostrar e sugestões de enquadramento, com duração estimada.
- **Exportação para IA (Decidido)**: prompt de produção genérico, sem plataforma específica, detalhado o bastante para um bom resultado. É montado por modelo de texto a partir do JSON, e não por LLM: um bloco geral (9:16, até 60 segundos, paleta vermelha e branca, português do Brasil, tom sóbrio, sem emojis), um bloco por cena e instruções negativas (sem texto renderizado na imagem, sem números ou gráficos não descritos, sem logotipos de terceiros, sem pessoas reais identificáveis). A ferramenta também gera a narração (Decidido), e a pronúncia de siglas vem do glossário. O texto na tela é adicionado na edição (Recomendado).
- **Os dois botões** só ficam ativos depois da aprovação humana (Recomendado).
- **Limites declarados**: a meta é ambiguidade mínima, e não garantia, porque ferramentas generativas variam; o vídeo gerado fica fora da avaliação do sistema e exige revisão humana; **verificar** as regras de rotulagem de conteúdo gerado por IA no Instagram.

### 4.7 Avaliação híbrida e reflexão

**Métricas determinísticas (Do case, com adaptações Recomendadas).**

- Legibilidade: Flesch Reading Ease com coeficientes adaptados ao português, provavelmente em implementação própria (o textstat tem suporte limitado ao português; **verificar**). Para o roteiro falado, os limiares podem precisar ser diferentes dos do texto escrito.
- Domain Term Density Score: densidade e contextualização de termos contra o glossário.
- Grounding Checker: cada afirmação precisa ter respaldo no documento de origem. As explicações de termos são conferidas contra o glossário, e não contra a fonte.
- Número e data: todo número e data do material deve existir na fonte.
- Cobertura dos pontos centrais: quantos dos três sobrevivem em cada nível e formato, para detectar trivialização.
- Termo técnico no Iniciante com explicação dentro de uma janela curta de palavras.
- Verificações de formato de cada saída (seção 4.6), sem emojis, sem termos proibidos e verbos de ação da lista.

**RAG (Recomendado).** A geração não usa recuperação de documentos anteriores, porque comparar documentos exigiria inferências que a fonte não faz (Decidido). A recuperação entra na verificação de fidelidade, para achar o trecho que sustenta cada afirmação gerada, e na consulta ao glossário pelos termos detectados. Decidido: não usar vetores de embedding; a busca é por percurso no grafo e por números, entidades e termos exatos.

**Eval (Recomendado).** Dois usos: em tempo de execução (métricas determinísticas e loop de reflexão) e suíte offline (documentos de referência e casos de teste, com pytest, DeepEval ou Ragas; Do case). Cada execução registra o contexto completo: versões do glossário, dos prompts, do modelo, dos limiares, da rubrica e do guia de estilo, para os resultados serem comparáveis. Os resultados ficam em cache, e mudanças nas métricas determinísticas não chamam o modelo de novo.

**LLM-as-a-judge.** Complemento às métricas determinísticas, nunca árbitro único (Do case). Roda só nos textos que passaram nas métricas determinísticas (Recomendado; Em aberto). O modelo do juiz é diferente do que gerou o texto (Recomendado). Cada avaliação registra a rubrica (versão), o modelo, as notas por critério com justificativa curta, o tamanho do texto, para medir o viés de extensão, e a evidência usada. As suas decisões de aprovar, editar ou rejeitar servem para medir a concordância do juiz com você.

**Limiares.** Valores iniciais (Decidido, hipóteses a calibrar com dados): Flesch com Iniciante a partir de 55, Intermediário de 40 a 55 e Avançado até 40; densidade de termos técnicos por 100 palavras de até 3, de 3 a 8 e acima de 8. Ficam em arquivo de configuração. Decidido nesta sessão de análise: as faixas absolutas continuam como critério principal, mas a complexidade da fonte (legibilidade e densidade de termos do documento original) é registrada e o rótulo 'indistinto' é um outcome válido quando nenhum nível se encaixa de forma inequívoca, justificando caso o limite de tentativas seja atingido. O aviso ao revisor e o limite de tentativas seguem aplicáveis.

**Reflexão (Do case).** Se a pontuação ficar abaixo do limiar do nível, o grafo reitera injetando o relatório de falha no contexto. Decidido: duas reescritas e, se esgotadas, encaminhar ao revisor com aviso, sem repetir indefinidamente.

**Testes automatizados (Do case).** pytest, DeepEval ou Ragas sobre os outputs.

**Classificador de nível e complexidade da fonte (Decidido nesta sessão de análise, antes Recomendado).** A matriz de confusão compara o nível-alvo com o nível que o avaliador classifica no texto gerado, e o classificador segue regras sobre a legibilidade e a densidade de termos, com faixas por nível calibradas nos documentos de referência; um texto fora de todas as faixas ou entre duas fica como 'indistinto', outcome válido e registrado. A complexidade da fonte é medida pela legibilidade e pela densidade de termos da própria fonte, para explicar por que os níveis ficaram pouco distintos, e fica registrada por execução.

### 4.8 Validação humana

A mesma pessoa que escolhe o card valida o conteúdo, depois do juiz (Decidido). Como há menos 'olhar novo', a tela de validação deve mostrar (Recomendado): o texto, as pontuações, os trechos de origem de cada afirmação, o tipo da fonte, a complexidade da fonte, a versão do glossário e os termos pendentes. Ações: aprovar, editar, rejeitar. O texto editado é reavaliado pelas métricas determinísticas e marcado como editado por humano, preservando a versão original gerada (Recomendado). Só depois da aprovação ficam ativas as exportações. As decisões servem para calibrar o juiz (Recomendado). Fechado nesta sessão de análise: seus outros usos são apenas métricas de concordância do juiz, histórico versionado e auditoria; decisões humanas não alteram automaticamente limiares, prompts ou ranking, para preservar a comparabilidade experimental.

### 4.9 Dashboard e relatório

O dashboard compara a matriz de 9 saídas lado a lado, com células vazias e um botão de gerar para o que ainda não foi gerado, e mostra a rastreabilidade das fontes, as pontuações por nível e a cota de tokens do dia (Do case + Recomendado). O relatório experimental traz metodologia, matriz de confusão de níveis, trade-offs de custo e latência e instruções de reprodutibilidade (Do case). A matriz de confusão compara o nível-alvo pedido com o nível que o avaliador classifica no texto gerado (Recomendado, o case não define).

### 4.10 Estado do pipeline (LangGraph, Recomendado)

**Estado.** Modelo Pydantic com: identificador da execução; documento (texto e origem, com instituição, título, data e link); níveis escolhidos; versões de configuração (glossário, prompts, modelos, limiares, estilo); extração (pontos centrais, afirmações com tipo, papel e trecho, dados numéricos, termos detectados e termos pendentes); saídas por nível e formato, cada uma com o histórico de tentativas (conteúdo, métricas, falhas, tokens, latência e modelo); avaliação do juiz por tentativa; decisão humana; contagem de tokens e erros.

**Nós.** Admitir; extrair; gerar (um por nível, com os três formatos); avaliar de forma determinística; julgar; rotear; validação humana (pausa até a sua decisão); exportar.

**Arestas condicionais.**

- Reprovou nas métricas e tem reescrita sobrando: volta a gerar com o relatório de falha.
- Passou nas métricas: segue ao juiz.
- O juiz reprova e tem reescrita sobrando: volta a gerar.
- Esgotou as duas reescritas: segue à validação humana com aviso.
- Aprovado: segue à validação humana.

**Persistência e pausa.** O estado é gravado no PostgreSQL (checkpointer do LangGraph compatível com o driver psycopg), para a validação humana poder pausar e retomar o fluxo sem manter um segundo banco.

**Execução.** Os níveis rodam em sequência controlada por um limitador de tokens compartilhado por todos os nós, já que o paralelismo não encurta o tempo no plano gratuito. Uma saída que não passa na validação Pydantic conta como falha da tentativa.

## 5. Dados: grafo e relacional

Usar um único banco relacional com um grafo lógico modelado por arestas é a decisão atual (Decidido): menos complexidade operacional, uma única fonte de verdade e traversals por SQL.

- **Percurso** (seguir ligações) vai no **grafo**.
- **Agregação e filtro** (somar, filtrar, comparar) vai no **relacional**.

Cada fato mora em um lugar só. Os dois lados compartilham identificadores únicos de documento, afirmação, card e material; campos que mudam (status, pontuação) ficam só no relacional.

**Grafo (rascunho).**

| Nós | Relações |
| --- | --- |
| Documento, Trecho, PontoCentral, Afirmação, Dado | Documento -TEM_TRECHO-> Trecho; Afirmação -EXTRAIDA_DE-> Trecho; Afirmação -SUSTENTA-> PontoCentral; Dado -EXTRAIDO_DE-> Trecho |
| Entidade, Evento | Afirmação -SOBRE-> Entidade ou Evento; Documento -TRATA_DE-> Evento |
| Card | Card -ATUALIZA-> Card (só navegação); Card -APONTA_PARA-> Documento |
| Termo (referência ao glossário) | Documento -MENCIONA-> Termo |
| Material, FraseGerada | Material -TEM_FRASE-> FraseGerada; FraseGerada -BASEADA_EM-> Afirmação |

**Relacional (PostgreSQL, Decidido).** Tabelas operacionais, incluindo as arestas do grafo lógico, no mesmo banco:

| Tabela | Conteúdo |
| --- | --- |
| cards | Metadados, fonte, tipo de fonte, categoria, motivo de entrada, data e estado |
| documentos | Hash, origem (card, link ou texto), integridade, idioma e data de criação; o texto original fica em arquivo no volume, identificado pelo hash |
| execucoes | Configuração completa (versões de glossário, prompts, modelos, limiares, rubrica e estilo), seu hash e os tokens totais |
| materiais | Nível, formato, estado, conteúdo gerado e conteúdo editado |
| tentativas | Conteúdo, métricas, falhas, motivo de reprovação, tokens, latência e modelo |
| avaliacoes_juiz | Rubrica (versão), modelo, notas por critério, justificativa, tamanho do texto e evidência |
| decisoes_humanas | Aprovar, editar ou rejeitar, com observação e data |
| termos_pendentes | Termo, definição proposta, trecho original, fonte e estado |
| coletas | Fonte, horário, itens e erros |
| eval_execucoes e eval_resultados | Suíte offline: contexto, caso, métrica e resultado |

**Motores (Decidido).** Banco único relacional: PostgreSQL em Docker com volume persistente, para todos os dados operacionais e para o grafo lógico (documentos, trechos, afirmações, entidades, eventos, cards, materiais e suas arestas). Isso elimina a segunda fonte de verdade e simplifica backup, migração e consistência. Usar psycopg e o checkpointer do LangGraph compatível com PostgreSQL. O grafo deixa de ser um banco separado (Neo4j/Memgraph/Kuzu) e passa a ser um modelo de arestas dentro do PostgreSQL, com consultas por JOIN e WITH RECURSIVE. Decidido nesta sessão de análise: manter PostgreSQL como única fonte de verdade; antes do commit, definir a profundidade máxima de recursão, criar índices para nós e arestas, instrumentar memória e tempo de travessia e executar o teste de uma hora. O fallback para SQLite em volume continua restrito a ambientes muito simples, não ao padrão principal.

**Esquema detalhado do grafo (Recomendado).** Propriedades dos nós: Documento (id, hash, título, instituição, data, url, idioma); Trecho (id, ordem, texto); PontoCentral (id, ordem, título); Afirmação (id, texto, tipo: fato, projeção ou evento futuro; papel: nenhum, causa, impacto, risco ou acompanhar; variação declarada); Dado (id, indicador, valor, unidade, período); Entidade e Evento (id, nome canônico, tipo; data de referência no evento); Card e Material (id, só como referência ao relacional); FraseGerada (id, campo, texto, tentativa); Termo (id do glossário). A unidade mínima de informação é a afirmação, sempre ligada a um trecho. O tipo da afirmação é uma propriedade dela. Cada tentativa do loop é um registro no relacional, com as frases geradas ligadas às afirmações no grafo. A decisão humana e as versões vivem no relacional, ligadas ao material pelo identificador.

## 6. Consultas do dashboard e do relatório

**Percurso** = segue ligações entre registros (grafo). **Agregação/filtro** = números e linhas (relacional). **Mista** = precisa dos dois.

### Dashboard

| # | Consulta | Tipo | Onde |
| --- | --- | --- | --- |
| D1 | Listar cards do dia e da semana com título, descrição, fonte, tipo de fonte e motivo de entrada | Filtro | Relacional |
| D2 | Dado um card, listar os cards da mesma história, anteriores e posteriores | Percurso | Grafo |
| D3 | Dado um material, mostrar cada frase com as afirmações de origem e o trecho exato do documento | Percurso | Grafo |
| D4 | Dado um documento, mostrar os pontos centrais e quantos sobreviveram em cada nível | Mista | Grafo + relacional |
| D5 | Dado um material, mostrar pontuações, versão do glossário, tentativas e motivo de cada reprovação | Filtro | Relacional |
| D6 | Dado um documento, listar os termos técnicos e se cada um tem explicação no Iniciante | Mista | Grafo + relacional |
| D7 | Fila de revisão: materiais aguardando aprovação e termos pendentes | Filtro | Relacional |
| D8 | Estado da geração de um card (na fila, gerando, avaliando) | Filtro | Relacional |
| D9 | Sequência de cards ligados de uma história (navegação, sem cálculo de diferenças) | Percurso | Grafo |
| D10 | Dada uma afirmação marcada como projeção, mostrar o evento e a fonte a que se refere | Percurso | Grafo |
| D11 | Cards e documentos de uma entidade ou evento | Percurso | Grafo |

### Relatório

| # | Consulta | Tipo | Onde |
| --- | --- | --- | --- |
| R1 | Matriz de confusão de níveis (nível-alvo contra nível classificado) | Agregação | Relacional |
| R2 | Legibilidade e densidade de termos por nível e formato (média, distribuição) | Agregação | Relacional |
| R3 | Taxa de aprovação, edição e rejeição humana por nível e formato | Agregação | Relacional |
| R4 | Tentativas do loop até aprovar, taxa de convergência e motivos de reprovação | Agregação | Relacional |
| R5 | Custo e latência por material, nível e formato | Agregação | Relacional |
| R6 | Cobertura do glossário nos documentos de teste | Mista | Grafo + relacional |
| R7 | Termos pendentes aprovados, editados e rejeitados ao longo do tempo | Agregação | Relacional |
| R8 | Fidelidade: fração das afirmações com origem rastreada e números que não existem na fonte | Mista | Grafo + relacional |
| R9 | Acurácia da ligação entre cards (pares certos e errados nos exemplos rotulados) | Agregação | Relacional |
| R10 | Cobertura dos cards: recall nos N primeiros contra os dias de referência | Agregação | Relacional |
| R11 | Comparação de resultados entre versões do glossário | Agregação | Relacional |
| R12 | Rastreabilidade ponta a ponta: fração das frases com caminho completo até o trecho de origem | Percurso | Grafo |

**Consultas adicionais (decorrentes de cota, RAG, eval e juiz).**

| # | Consulta | Tipo | Onde |
| --- | --- | --- | --- |
| D12 | Cota de tokens restante do dia (para a interface) | Filtro | Relacional |
| R13 | Concordância entre o juiz e as decisões humanas (aprovar, editar, rejeitar) | Agregação | Relacional |
| R14 | Relação entre a nota do juiz e o tamanho do texto (viés de extensão) | Agregação | Relacional |
| R15 | Consumo de tokens por documento, por dia e por nível (cota do plano) | Agregação | Relacional |

**Leitura do resultado.** Das 27 consultas, 6 são percurso puro (D2, D3, D9, D10, D11, R12), 4 são mistas (D4, D6, R6, R8) e 17 são agregação ou filtro. O grafo se justifica por proveniência (de onde veio cada frase), ligação de histórias e relação entre entidades e eventos. D9 é só a sequência de cards ligados, sem cálculo de diferenças, porque o sistema só reproduz mudanças declaradas pela fonte. O relacional cuida de tudo que vira número ou tabela no relatório, e por isso recomendo mantê-lo para materiais, pontuações, decisões, custos e avaliação.

## 7. Infraestrutura

**Docker local (Decidido).** A hospedagem foi descartada. O plano gratuito do Render dorme após inatividade, tem sistema de arquivos efêmero, sem disco, sem cron e 512 MB de memória, o que não combina com banco embutido, Playwright e agendamento. A Vercel não combina com processo contínuo e gerações longas.

**Serviços do compose (Recomendado).** Aplicação (interface e API), PostgreSQL com volume persistente, coletor e agendador, renderizador de slides (com Playwright, compartilhando imagem com a aplicação quando possível) e arquivo .env para chaves, com .env.example no repositório. Não há mais serviço separado de banco de grafo.

**Modelo de linguagem e limites (plano gratuito Decidido; Groq travado nesta sessão de análise).** Os valores de exemplo publicados para modelos de texto no plano gratuito do Groq são 30 requisições por minuto, 1.000 por dia, 8.000 tokens por minuto e 200.000 tokens por dia ([benchlm.ai](https://benchlm.ai/free-tier/groq)); os limites reais da conta aparecem na tela de limites do console (**verificar**). Os tokens por minuto somam entrada e saída numa janela de 60 segundos, e o catálogo de modelos abertos muda com frequência, então o identificador de cada modelo deve ser fixado. Recomendado: dois modelos diferentes, um para gerar e outro para julgar, e um teste de qualidade em português com um nível completo antes de escolher.

Estimativa ilustrativa, com suposições minhas (documento de 6.000 tokens, material de 600 tokens de saída, juiz lendo cerca de 2.300 tokens), a medir:

| Níveis gerados | Tokens por documento | Tempo mínimo | Documentos por dia |
| --- | --- | --- | --- |
| 1 | cerca de 24.600 | cerca de 3 min | cerca de 8 |
| 2 | cerca de 41.700 | cerca de 5 min | cerca de 4 a 5 |
| 3 | cerca de 58.800 | cerca de 7 min | cerca de 3 |

O paralelismo não acelera nada, porque o gargalo é o teto de tokens por minuto. Uma passada da suíte offline com 12 a 15 documentos consome 700 mil a 880 mil tokens, cerca de 3,5 a 4,5 dias de cota. O texto analítico tende a ter saída maior do que a suposta.

**Adaptações ao limite (Recomendado).** Fila com controle dos tokens da janela de 60 segundos, com nova tentativa e espera crescente quando o limite é excedido; cache de tudo o que foi gerado, indexado por documento, prompt, modelo e versões; juiz só nos textos que passaram nas métricas determinísticas; gerar por nível, e não por formato, se a qualidade permitir; documentos longos divididos em partes na extração; descrição dos cards e classificação de admissão sem LLM sempre que possível, porque a varredura diária e a admissão também gastam a cota; cota do dia visível na interface; demonstração com resultados pré-gerados e uma geração ao vivo só de um caso curto.

**Entrega (Decidido nesta sessão de análise, antes Recomendado).** Um único comando de subida, dados de exemplo já carregados, requisitos (Docker, memória mínima) no README, e teste de subida do zero numa máquina limpa. Fechado nesta sessão: entrega considerada 100% local, com vídeo demonstrativo do ambiente funcionando; podem ser mantidos hooks mínimos de configuração, mas não entra no escopo atual infraestrutura remota nem banco hospedado. Se a organização exigir link público depois, isso passa a ser incremento posterior, não bloqueio da entrega atual.

## 8. Plano de validação

Como o projeto é individual, a calibração dispensa outras pessoas (Recomendado):

- **Dias de referência**: 12 a 15 dias passados, espalhados em semanas diferentes e de tipos variados (com Copom ou IPCA, temporada de resultados, dias calmos), com histórico acessível nas mesmas fontes que o sistema varre. Marque em cada dia o que você transformaria em material e a categoria (aconteceu, em andamento).
- **Separação**: cerca de dez dias para ajustar pesos e cinco para medir, sem mexer.
- **Eventos agendados como checagem objetiva**: calendários públicos do Copom e do IBGE indicam o que deve aparecer.
- **Limite de cards**: calcular a cobertura (recall) para vários N, observar o cotovelo da curva e usar o maior número de eventos obrigatórios num mesmo dia como piso. Definir a hipótese antes de medir.
- **Pares de notícias**: montar pares (mesma história e histórias diferentes) para medir a acurácia da ligação.
- **Extrator**: conferir à mão, nos documentos de referência, pontos centrais, números e trechos de origem.
- **Fatia fina de ponta a ponta**: um documento real (por exemplo, uma ata do Copom) passando por extração, grafo, uma geração e uma avaliação, medindo tokens, tempo e memória.
- **Qualidade do modelo**: gerar um nível completo (os três formatos) em um documento real e olhar o português, o respeito aos limites de formato e a fidelidade.
- **Juiz**: medir a concordância com as suas decisões e a relação da nota com o tamanho do texto.
- **Limitação a declarar**: um único avaliador, sem medida de concordância entre pessoas.
- **Reprodutibilidade**: todos os resultados do relatório com uma versão congelada do glossário e do restante do contexto de execução.

## 9. Riscos e mitigações

| Risco | Mitigação |
| --- | --- |
| Coleta quebra perto da entrega | Acervo local de documentos reais como reserva; botão manual |
| Fontes sem permissão para coleta automatizada | Verificar termos e robots.txt; preferir dados abertos |
| Conteúdo truncado entra como completo | Checagens de integridade antes do grafo |
| Texto não financeiro contamina o grafo | Etapa de admissão com classificação e contagem de termos |
| Texto coletado ou enviado com instruções escondidas para o modelo | Conteúdo tratado como dado; saídas estruturadas validadas por Pydantic; revisão humana |
| Erro do extrator contamina todo o resto | Teste do extrator nos documentos de referência; trecho de origem visível na validação |
| Avaliador reprova por falta de jargão na fonte | Limiares relativos ou aviso; limite de tentativas |
| Matriz de confusão sem classificador de nível definido | Definir o classificador por faixas de legibilidade e densidade, calibradas nos documentos de referência |
| Juiz LLM reproduz vieses | Métricas determinísticas decidem primeiro; modelo diferente do gerador; tamanho do texto registrado; calibração com as suas decisões |
| Definição de termo errada entra no glossário | Fontes autorizadas, trecho original visível, sua aprovação |
| Material afirma uma mudança que a fonte não declarou | Só reproduzir variações declaradas; nenhuma comparação entre documentos |
| Linguagem de recomendação de investimento | Lista de termos proibidos, regras para a chamada para ação, aviso institucional opcional (nenhum confirmado pela Suno) |
| Duas fontes de verdade (grafo e relacional) | At mitigação: agora há uma única fonte de verdade em PostgreSQL; o grafo é modelado por nós e arestas no mesmo banco, com transações únicas |
| Limite do plano gratuito trava o projeto | Fila com controle de tokens, cache, seleção de níveis, demonstração com resultados pré-gerados |
| Varredura diária e admissão consomem a cota do plano | Triagem por regras, descrição extrativa, LLM só para cards escolhidos |
| Modelo aberto escreve português com menos nuance | Teste de qualidade antes de escolher; métricas determinísticas e validação humana |
| Vídeo gerado por IA com números ou imagens inventados | Instruções negativas no prompt; vídeo fora da avaliação, com revisão humana; verificar regras de rotulagem |
| Voz sintética lê números ou siglas errado | Fala falada derivada por regra; pronúncia no glossário |
| Custo e latência de 9 saídas com tentativas | Reaproveitamento, limite de tentativas, medição desde cedo |
| Falha na demonstração | Teste completo do zero; gravar com a mesma configuração |

## 10. Mapeamento com os entregáveis do case

| Entregável | Onde aparece |
| --- | --- |
| 1. Pipeline de adaptação e GitHub consistente | Seções 4.4 a 4.6 e commits regulares |
| 2. Suíte de avaliação híbrida | Seção 4.7 e testes automatizados |
| 3. Reflection Loop demonstrado | Seção 4.7, com um caso de nível Iniciante difícil demais |
| 4. Interface e dashboard | Seções 4.2, 4.8 e 4.9, com seleção de níveis, visualização e exportação |
| 5. Vídeo demonstrativo | Responsabilidade da autora (roteiro, gravação e apresentação), fora do escopo de implementação. O caso exige até 5 minutos e prova do funcionamento real do código e da interface. A demonstração usa resultados pré-gerados e uma geração ao vivo de um caso curto. A aplicação fornece apenas os formatos usuais do escopo, inclusive o roteiro do Reels; não há componentes exclusivos para produzir o vídeo de entrega |
| 6. Relatório experimental e README | Seções 6, 7 e 8, com matriz de confusão, custo e latência e reprodutibilidade |

## 11. Pontos em aberto

1. Fechado nesta sessão: limite diário com padrão provisório de 8, configurável; hipótese registrada antes da medição; recall medido para vários N nos dias de referência; maior número de eventos obrigatórios num mesmo dia como piso.
2. Fechado nesta sessão: Groq travado como provedor, com dois modelos distintos (geração e juiz), IDs fixados em configuração e teste de qualidade em português antes da entrega. Os limites reais da conta continuam a ser verificados no console do provedor.
3. Fechado nesta sessão: fontes não coletáveis automaticamente ficam inativas e a entrega se apoia em acervo local de documentos reais mais botão de atualização manual; não se buscam fontes/APIs alternativas não verificadas. A verificação de feeds, APIs, robots.txt e termos de uso das fontes primárias continua a ser feita antes da implementação da coleta.
4. Fechado nesta sessão para a entrega atual: cenário 100% local com vídeo demonstrativo do ambiente funcionando; link público, se exigido pela organização, fica como incremento posterior. Não há texto de aviso institucional obrigatório confirmado pela Suno, e a geração não é bloqueada por sua ausência; eventual aviso segue como recurso configurável provisório.
5. Fechado nesta sessão: prompts por nível e formato vivem em configuração versionada; você os revisa antes da suíte offline; nenhuma execução de relatório usa prompt não aprovado; o hash do prompt entra no contexto da execução.
6. Fechado nesta sessão: decisões humanas alimentam apenas métricas de concordância do juiz, histórico versionado e auditoria; não alteram automaticamente limiares, prompts ou ranking, preservando comparabilidade experimental.
7. Fechado nesta sessão: local de publicação fica agnóstico ao código; exportação em Markdown/HTML, pré-visualização como artigo e cópia de texto; integração com CMS/plataforma não entra no escopo.
8. Fechado nesta sessão para a arquitetura: PostgreSQL único mantido, com profundidade máxima de recursão, índices para nós/arestas e teste de travessia de uma hora a executar antes do commit.

## 12. Observações para implementações futuras

- Hospedagem com banco de grafo gerenciado (por exemplo, camada gratuita do Neo4j Aura, com limites e pausa por inatividade a verificar).
- OCR para PDFs escaneados.
- Comparações entre documentos com dados estruturados (indicador, valor, unidade, período e trecho de origem), calculadas por função e escritas como 'a fonte A informa X e a fonte B informa Y', nunca como 'mudou'.
- Reavaliação de materiais antigos após mudanças no glossário (hoje só valem para materiais novos).
- Aprendizado do ranking a partir dos cards clicados.
- Persistência dos dados de demonstração entre reinícios em ambiente hospedado.
- Busca por similaridade com vetores de embedding.
- Integração com ferramentas de design, como o Figma (não verificada).
- Geração de vídeo integrada a uma plataforma de IA, em vez de só exportar o prompt.
- Texto alternativo (alt text) dos slides do carrossel, montado por regra a partir do texto de cada slide.
- Backup e exportação dos volumes do grafo e do relacional.

## 13. Escopo e ordem de construção

**Escopo completo (Decidido).** Todas as funcionalidades descritas neste documento fazem parte da entrega, sem corte de MVP. O prazo é de 3 dias a partir de 12/10/2026 (Decidido). A implementação será feita por outra IA, a partir de um plano de implementação que você gera com base neste documento.

**Ordem de construção sugerida (Recomendado).** Serve só para organizar o trabalho e não remove nada do escopo:

1. Estrutura do repositório, Docker compose, arquivos de configuração e modo simulado do modelo.
2. Admissão, extração com âncora e gravação nos dois bancos.
3. Geração do texto analítico, métricas determinísticas e loop de reflexão.
4. Carrossel com legenda e roteiro de vídeo, com suas verificações.
5. Juiz estruturado, registro de custos e calibração com as decisões humanas.
6. Interface: cards, seleção de níveis, validação humana e dashboard.
7. Renderização do carrossel, exportações e botões do roteiro de vídeo.
8. Coleta, agendador e ranking de cards.
9. Suíte offline, relatório experimental, README e teste de subida do zero.

## 14. Critérios de aceitação

| Área | Critério verificável |
| --- | --- |
| Entrada e cards | Um card do acervo abre a seleção de níveis; texto colado e PDF digital entram; link inacessível mostra a mensagem definida; conteúdo parcial é bloqueado com toast |
| Extração | Para um documento de teste, três pontos centrais, afirmações com tipo e trecho de origem e dados numéricos gravados nos dois bancos |
| Geração | Para cada nível escolhido, os três formatos em JSON válido: texto com quatro seções, carrossel de 5 slides, roteiro de 5 cenas com até 60 segundos e legenda com fonte, verbo da lista e aviso institucional apenas se configurado |
| Fidelidade | Nenhum número ou data fora da fonte nas saídas aprovadas; nenhuma frase com o marcador 'Em geral,' fora do glossário; nenhuma mudança afirmada sem declaração da fonte; sem emojis |
| Avaliação | Métricas determinísticas gravadas por tentativa; juiz com modelo diferente do gerador; nível classificado registrado |
| Loop de reflexão | Demonstração em que um texto Iniciante reprovado por legibilidade é reescrito com feedback numérico e aprovado em até duas reescritas |
| Validação humana | Aprovar, editar (com reavaliação) e rejeitar; exportações só depois de aprovar; termos pendentes bloqueiam a aprovação |
| Dashboard | Matriz de 9 saídas com células vazias e botão de gerar; frase rastreada até o trecho de origem; pontuações por nível; cota de tokens do dia |
| Exportação | Markdown e HTML do texto; PNGs 1080 × 1350 do carrossel com a linha do nível na posição certa; roteiro para pessoa e prompt para IA |
| Coleta | Botão manual e agendamento das 8h gravam cards, com título, fonte e descrição conforme as regras |
| Reprodutibilidade | Um comando de subida; testes automatizados em modo simulado, sem chamar o modelo; resultados com a versão do glossário |
| Suíte offline | Roda sobre os documentos de referência e produz matriz de confusão de níveis, custo e latência |

## 15. Instruções para a implementação

- **Pilha (Decidido e Recomendado)**: Python, LangGraph, Pydantic, Streamlit, PostgreSQL em Docker compose, Playwright para coleta e renderização, Groq como provedor com os modelos fixados em configuração. O grafo é modelado como tabelas de nós e arestas no PostgreSQL.
- **Pastas sugeridas**: config (arquivos YAML de termos, apelidos, verbos, termos proibidos, guia de estilo, limiares, estrutura do texto, enquadramentos e tokens visuais), src (admissão, extração, geração, avaliação, pipeline, persistência, coleta, renderização, exportação e interface), tests (com respostas gravadas do modelo), data (acervo e documentos de referência) e docs.
- **Modo simulado (importante)**: todas as chamadas ao modelo passam por uma interface que pode ler respostas gravadas. Os testes automatizados usam só o modo simulado, para não gastar a cota do plano gratuito. Há cache indexado por documento, prompt, modelo e versões.
- **Contratos**: cada saída (texto, carrossel, roteiro e legenda) é um modelo Pydantic, e uma saída inválida conta como falha da tentativa.
- **Limites**: limitador global de tokens, nova tentativa com espera crescente nas respostas de limite excedido, e tokens e latência registrados por chamada.
- **Regras que o código não pode violar**: nunca comparar documentos; tratar o conteúdo coletado como dado, nunca como instrução; sem emojis; verbo da chamada dentro da lista; só reproduzir mudanças declaradas pela fonte.
- **Prompts**: a IA implementadora escreve os prompts por nível e formato a partir deste documento, e você os revisa.
- **Ordem de construção e critérios de aceitação**: seções 13 e 14.

## 16. Fontes consultadas

Páginas que apareceram em resultados de busca durante o planejamento. Não foram lidas na íntegra, então confirme os dados antes de depender deles.

- Limites do plano gratuito do Groq: [benchlm.ai](https://benchlm.ai/free-tier/groq) e [comunidade Groq](https://community.groq.com/t/is-there-a-free-tier-and-what-are-its-limits/790).
- Tamanhos e regras de carrossel do Instagram: [socialk.it](https://socialk.it/en/sizes/instagram-carousel-size) e [wavegen.ai](https://wavegen.ai/instagram-carousel-size).
- Render (plano gratuito e planos pagos): [jwatte.com](https://jwatte.com/blog/render-com-platform-review.md) e [kuberns.com](https://kuberns.com/blogs/is-render-good-for-production/).
- Limites das funções da Vercel: [vercel.com](https://vercel.com/docs/functions/limitations).
- Neo4j AuraDB Free: [neo4j.com](https://neo4j.com/free-graph-database/).
- Estado do Kuzu e do fork da comunidade: [puppygraph.com](https://www.puppygraph.com/blog/what-is-kuzudb).
- Glossários autorizados para definições: [Banco Central](https://www.bcb.gov.br/content/cidadaniafinanceira/documentos_cidadania/Informacoes_gerais/glossario_cidadania_financeira.pdf) e [B3 Bora Investir](https://borainvestir.b3.com.br/glossario/).

## Atualização da especificação — Decisões consolidadas

### 1. Releases de empresas como entrada manual

A lista de empresas acompanhadas deve ser removida da especificação. Não será implementada uma coleta automática de releases em sites de relações com investidores.

Os releases serão tratados como documentos de entrada manual, assim como os demais documentos financeiros. O usuário será responsável por decidir se deseja inserir esse tipo de documento e fornecer seu conteúdo.

**Implicações para a implementação:**
- Remover a lista de empresas monitoradas e qualquer configuração relacionada à coleta automática de seus releases.
- Manter o suporte à análise de releases inseridos manualmente, por texto colado ou arquivo compatível.
- Não restringir a entrada a uma lista predefinida de empresas.
- Preservar a extração de informações, a rastreabilidade das afirmações e as demais etapas de processamento previstas para os documentos financeiros.

### 2. Remoção da categoria de cards “Vem aí”

A categoria “Vem aí” deve ser removida do projeto, incluindo suas regras específicas e a necessidade de fontes externas dedicadas a calendários de eventos futuros.

A apresentação dos acontecimentos continuará contemplada pelas categorias restantes, como “Acabou de acontecer” e “Em andamento”. Informações futuras presentes nos documentos de entrada continuarão sendo identificadas e classificadas pelo extrator conforme as regras já definidas para projeções e eventos futuros.

**Implicações para a implementação:**
- Remover a categoria “Vem aí” da interface, das configurações, dos prompts, dos esquemas de dados e das validações aplicáveis.
- Remover as fontes e integrações previstas exclusivamente para alimentar essa categoria.
- Preservar as classificações de afirmações como fato, projeção e evento futuro.
- Não eliminar a capacidade de analisar acontecimentos futuros mencionados nas fontes fornecidas pelo usuário.

### 3. Vídeo de entrega do case

A elaboração do roteiro, a gravação e a apresentação do vídeo de demonstração são responsabilidades da autora do projeto. Portanto, esses elementos não devem integrar o escopo de implementação da aplicação nem permanecer como pendências de desenvolvimento na especificação técnica.

O documento deve ser focado nos requisitos e no funcionamento do sistema, sem incluir uma seção dedicada ao roteiro ou à duração do vídeo de entrega.

**Implicações para a implementação:**
- Remover o roteiro do vídeo de demonstração da lista de tarefas e dos pontos em aberto do desenvolvimento.
- Não criar funcionalidades, integrações ou componentes exclusivos para produzir o vídeo de entrega.
- Manter, normalmente, os formatos de conteúdo gerados pela própria aplicação, incluindo o roteiro de vídeo destinado ao Reels, caso já previsto no escopo. Esse recurso é diferente do vídeo de demonstração do case.

### 4. Aviso padrão e comunicação institucional

A Suno não disponibilizou uma mensagem obrigatória para inclusão nos conteúdos produzidos pela aplicação.

Assim, não existe um texto institucional obrigatório confirmado. A frase anteriormente sugerida — “Conteúdo educativo. Não é recomendação de investimento.” — não deve ser tratada como uma exigência oficial da Suno.

**Implicações para a implementação:**
- Remover qualquer indicação de que a frase sugerida foi exigida ou aprovada pela Suno.
- Não bloquear a geração de conteúdo pela ausência de uma mensagem institucional.
- Se o aviso for mantido como recurso configurável, tratá-lo como uma configuração provisória, e não como uma regra institucional confirmada.
- Não inventar outras mensagens obrigatórias nem atribuir à Suno uma orientação que ela não forneceu.

### 5. Diretriz de consistência documental

As alterações acima devem ser aplicadas a todas as partes da especificação, e não apenas à seção de decisões. Isso inclui requisitos funcionais, arquitetura, esquemas de dados, prompts, configurações, critérios de aceitação, testes, interface e lista de pendências.

O objetivo é evitar referências contraditórias a funcionalidades removidas ou a decisões que não foram oficialmente confirmadas.

**Regra geral:** preservar as funcionalidades e decisões previamente acordadas que não tenham sido explicitamente alteradas nesta atualização. Não reduzir o escopo do projeto nem transferir funcionalidades para uma fase futura por conveniência de implementação.

### 6. Decisões da sessão de análise de brechas

1. **Provedor de LLM.** Groq travado como provedor padrão, com dois modelos distintos (geração e juiz), IDs fixados em configuração e teste de qualidade em português antes da entrega. O modo simulado e o cache por documento, prompt, modelo e versões continuam obrigatórios.
2. **Persistência.** PostgreSQL único mantido como fonte de verdade. Antes do commit: profundidade máxima de recursão definida, índices para nós e arestas, instrumentação de memória e tempo de travessia, teste de uma hora. Fallback SQLite restrito a ambientes muito simples.
3. **Admissão de texto não financeiro.** A regra determinística (≥5 termos distintos do glossário e ≥200 palavras) é o árbitro; a extração estruturada com conjunto fechado de categorias, incluindo 'não financeiro', é metadado/sinal auxiliar e não veta a entrada sozinha.
4. **Documentos longos.** Divisão por sentença/pragações preservando offsets de origem, com segunda passagem de agregação dos pontos centrais. Afirmação sem trecho exato mapeável não entra no grafo.
5. **Limiares de nível e fontes pouco técnicas.** Faixas absolutas de Flesch e densidade continuam como critério principal; a complexidade da fonte é registrada por execução; o rótulo 'indistinto' é outcome válido quando nenhum nível se encaixa de forma inequívoca, e o caso pode atingir o limite de tentativas com aviso ao revisor.
6. **Classificador de nível.** Segue legibilidade e densidade de termos, calibrado nos documentos de referência; texto fora de todas as faixas ou entre duas é 'indistinto', outcome válido e registrado, com complexidade da fonte registrada.
7. **Retroalimentação.** Decisões humanas (aprovar, editar, rejeitar) alimentam apenas métricas de concordância do juiz, histórico versionado e auditoria. Elas não alteram automaticamente limiares, prompts ou ranking, para preservar a comparabilidade experimental. Ajustes de configuração exigem decisão explícita.
8. **Entrega.** Cenário 100% local com vídeo demonstrativo do ambiente funcionando. Link público, se exigido pela organização, fica como incremento posterior. Hooks mínimos de configuração podem ser mantidos, mas não entra no escopo atual infraestrutura remota nem banco hospedado.

9. **Limite diário de cards.** Padrão provisório de 8, configurável, com hipótese registrada antes da medição, recall medido nos dias de referência e maior número de eventos obrigatórios num mesmo dia como piso.

10. **Coleta e fontes.** Fontes não coletáveis automaticamente ficam inativas; a reserva é o acervo local de documentos reais mais o botão manual. Não se buscam fontes ou APIs alternativas não verificadas; a verificação de feeds, robots.txt e termos de uso continua a preceder a implementação.

11. **Prompts.** Vivem em configuração versionada, com revisão sua antes da suíte offline; nenhuma execução de relatório usa prompt não aprovado; o hash do prompt entra no contexto da execução.

12. **Publicação do texto analítico.** O escopo permanece agnóstico: exportação em Markdown/HTML, pré-visualização como artigo e cópia de texto. Integração com CMS ou plataforma não entra no escopo.
