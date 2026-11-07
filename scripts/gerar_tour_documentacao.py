# Gera o tour de documentação (padrão Dome) no relatório PBIR do CortesNordeste.
# Uso: python3 gerar_tour.py <pasta CortesNordeste.Report/definition>
import json, os, shutil, sys, math

DEF = sys.argv[1]
W, H = 1280, 720
BAL_W = 340
INK, AMARELO, BRANCO, CINZA, CINZA2 = "#191919", "#F2C811", "#FFFFFF", "#C8C6C4", "#605E5C"
SCHEMA_VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.3.0/schema.json"
SCHEMA_BM = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/bookmark/1.4.0/schema.json"
SCHEMA_BMS = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/bookmarksMetadata/1.0.0/schema.json"

def lit(v): return {"expr": {"Literal": {"Value": v}}}
def s(v): return lit("'" + v.replace("'", "''") + "'")
def cor(c): return {"solid": {"color": s(c)}}

# ---------------- conteúdo (escrito a partir das medidas reais do modelo) ----------------
FILTROS = dict(
    alvo=(640, 20, 616, 44), lado="baixo",
    titulo="Filtros da página",
    mostra="À direita, o resumo dos filtros em uso. O botão Filtros abre a gaveta com Ano, Fonte (eólica ou solar) e UF; o número no botão diz quantos estão ativos.",
    ler="Toda a página responde aos filtros, e a seleção vale em todas as páginas. Os gráficos também filtram: clique numa barra, num estado ou numa usina; clique num espaço vazio para limpar.",
    logica="Fonte e UF são dimensões compartilhadas (Fontes e Estados) ligadas ao cadastro das usinas; Ano vem do calendário, ligado ao dia de cada registro.",
    medidas="Não é medida: os filtros mudam o contexto de todas as medidas da página.",
    atencao="A fonte solar só tem dados a partir de abr/2024; a eólica, desde out/2021.")

PAGINAS = {
 "visao_geral": dict(sigla="vg", passos=[
  dict(alvo=(640, 20, 616, 44), lado="baixo",
   titulo="Filtros da página",
   mostra="À direita, o resumo dos filtros em uso. O botão Filtros abre a gaveta com Ano, Fonte (eólica ou solar) e UF; o número no botão diz quantos estão ativos.",
   ler="Sem filtro de ano, os gráficos mostram todo o histórico; cartões, destaques e razão e origem mostram os últimos 12 meses. Com um ano, tudo mostra esse ano.",
   logica="Fonte e UF são dimensões compartilhadas (Fontes e Estados) que filtram as usinas e o perfil horário. Ano vem do calendário.",
   medidas="Não é medida: os filtros mudam o contexto de todas as medidas da página.",
   atencao="A fonte solar só tem dados a partir de abr/2024. Antes disso não há base de comparação para ela."),
  dict(alvo=(24, 82, 1232, 140), lado="baixo",
   titulo="Indicadores do período",
   mostra="Quatro números do período: energia não gerada, % da geração possível cortada, geração verificada e usinas com corte.",
   ler="A seta compara com o mesmo intervalo um ano antes. Para cortes, alta é ruim (vermelho). A linha à direita é a tendência de 24 meses; ponto vazado indica mês ainda incompleto.",
   logica="Período = filtro de datas ou, sem filtro, os 12 meses até o último dia com dados. A comparação desloca esse intervalo um ano para trás, cortado na mesma data, para não comparar mês parcial com mês cheio.",
   medidas="[Não realizada · período], [% cortado · período] = não realizada / (verificada + não realizada), [Geração · período], [Usinas com corte · período]. Variações: [· var %] e [% cortado · var p.p.].",
   atencao="Se o período anterior não tem dados (por exemplo, solar antes de 2025), o cartão mostra \"sem base de comparação\"."),
  dict(alvo=(24, 232, 800, 300), lado="direita",
   titulo="Geração não realizada por mês",
   mostra="Energia cortada em cada mês, empilhando eólica (preto) e solar (amarelo).",
   ler="A altura da coluna é o total do mês em GWh. Passe o mouse para ver o valor de cada fonte.",
   logica="Soma mensal da geração não realizada apurada (GNRa) pelo ONS, convertida de MW médios de meia hora para MWh.",
   medidas="[Não realizada (GWh)] = SUM(nao_realizada_mwh) / 1000, por mês e fonte.",
   atencao="O último mês pode estar incompleto. A solar entra nos dados em abr/2024, o que explica parte do salto a partir daí."),
  dict(alvo=(24, 540, 800, 160), lado="direita",
   titulo="% cortado por mês e fonte",
   mostra="Parte da geração possível que foi cortada em cada mês, para eólica e solar.",
   ler="Compara a intensidade do corte entre as fontes, independentemente do tamanho de cada uma.",
   logica="Calculado no próprio gráfico, mês a mês: não realizada / (verificada + não realizada).",
   medidas="[Não realizada (GWh)] e [Geração (GWh)], por mês e fonte.",
   atencao="Nos primeiros meses da solar, com pouca geração, o percentual oscila mais."),
  dict(alvo=(840, 232, 416, 268), lado="esquerda",
   titulo="Destaques do período",
   mostra="Frases geradas automaticamente com os principais fatos do período dos cartões e dos filtros selecionados.",
   ler="Os números em negrito mudam com os filtros. Use como resumo antes de explorar os gráficos.",
   logica="Razão dominante = a maior entre ENE, CNF, REL e PAR. Também mostra a parte sistêmica, o estado e a usina com mais energia cortada e o mês com maior corte no período.",
   medidas="[ENE · período], [CNF · período], [REL · período], [PAR · período], [Origem sistêmica · período] e [Não realizada · período] por estado, usina e mês.",
   atencao="São associações descritivas. Não indicam a causa do corte."),
  dict(alvo=(840, 510, 416, 190), lado="esquerda",
   titulo="Razão e origem do corte",
   mostra="Como a energia cortada no período dos cartões se divide por razão e por origem da restrição.",
   ler="Cada barra soma 100%. Razão: ENE (energética: oferta maior que o consumo), CNF (confiabilidade elétrica), REL (indisponibilidade externa), PAR (parecer de acesso). Origem: local (rede próxima à usina) ou sistêmica (sistema interligado).",
   logica="A origem vem do campo cod_origemrestricao do ONS, somado por usina e dia no dbt.",
   medidas="[ENE · período] a [PAR · período], [Sem razão · período], [Origem local · período], [Origem sistêmica · período], [Sem origem · período].",
   atencao="As partes sem razão ou sem origem informada entram no total, em cinza claro."),
 ]),
 "razoes_sazonalidade": dict(sigla="rs", passos=[
  dict(FILTROS, ler="Toda a página responde aos filtros, os mesmos em todas as páginas. Sem filtro de ano, mostra todo o histórico, menos o calendário dia a dia."),
  dict(alvo=(24, 84, 620, 300), lado="direita",
   titulo="Participação das razões por mês",
   mostra="Como a energia cortada em cada mês se divide entre as razões informadas pelo ONS.",
   ler="Cada coluna soma 100%. ENE: razão energética (oferta maior que o consumo). CNF: confiabilidade elétrica da rede. REL: indisponibilidade de instalações externas. PAR: parecer de acesso.",
   logica="Mostra a participação, não o volume: um mês com pouco corte pesa igual a um mês com muito corte.",
   medidas="[Energética (ENE)], [Confiabilidade (CNF)], [Indisponibilidade externa (REL)], [Parecer de acesso (PAR)] e [Sem razão (GWh)].",
   atencao="Para o volume de cada mês, veja o gráfico mensal da Visão executiva."),
  dict(alvo=(656, 84, 600, 300), lado="baixo",
   titulo="Sazonalidade: mês do ano",
   mostra="Energia cortada em cada mês de cada ano, num quadro mês × ano.",
   ler="Cores mais escuras indicam mais corte. Compare as colunas para ver se o padrão se repete nos mesmos meses todo ano.",
   logica="Cada célula soma a geração não realizada do mês. A dica de ferramenta mostra também o % cortado.",
   medidas="[Não realizada (GWh)] e [Geração (GWh)], por mês.",
   atencao="Há mais de quatro ciclos anuais de eólica, mas a solar só entra em 2024. O crescimento dos anos recentes também pesa nas cores."),
  dict(alvo=(24, 396, 620, 304), lado="direita",
   titulo="Em que hora do dia o corte acontece",
   mostra="Energia cortada em cada hora do dia (barras, por fonte) e o % da geração possível cortado naquela hora (linha vermelha).",
   ler="Barras altas mostram onde está o volume; a linha mostra onde o corte é mais intenso em relação ao que se poderia gerar.",
   logica="Vem do mart fct_restricao_perfil_horario, que soma os patamares de 30 minutos do ONS por mês, fonte, estado e hora.",
   medidas="[Não realizada no horário (GWh)] e [% cortado no horário], calculados sobre a tabela Perfil horário.",
   atencao="Responde aos filtros de fonte, UF e ano, mas não identifica usinas: o perfil é agregado."),
  dict(alvo=(656, 396, 600, 304), lado="esquerda",
   titulo="Corte dia a dia",
   mostra="Calendário com a energia cortada em cada dia dos últimos 12 meses com dados.",
   ler="Cada coluna é uma semana e cada linha um dia da semana. Quadrados escuros são os dias de maior corte.",
   logica="Mostra os 365 dias até o último dia com dados que estejam dentro dos filtros.",
   medidas="[Não realizada (GWh)] por dia.",
   atencao="Com o filtro de um ano antigo, mostra os últimos 365 dias daquele ano."),
 ]),
 "estados_usinas": dict(sigla="eu", passos=[
  dict(FILTROS, ler="Toda a página responde aos filtros, os mesmos em todas as páginas. Sem filtro de ano, mostra todo o histórico."),
  dict(alvo=(24, 84, 440, 616), lado="direita",
   titulo="% cortado por estado",
   mostra="Parte da geração possível que foi cortada em cada estado, com o volume em GWh ao lado.",
   ler="Barras amarelas indicam estados com 20% ou mais da geração possível cortada.",
   logica="A mesma conta do cartão da Visão executiva, calculada por estado do cadastro da usina.",
   medidas="[% cortado] = não realizada / (verificada + não realizada) e [Não realizada (GWh)].",
   atencao="Um percentual alto pode vir de um volume pequeno. Confira o GWh antes de comparar estados."),
  dict(alvo=(476, 84, 780, 400), lado="baixo",
   titulo="Pontos de conexão (Pareto)",
   mostra="Os 25 pontos de conexão à rede com mais energia cortada, do maior para o menor.",
   ler="A linha preta acumula a participação no total; a linha vermelha marca 80%. Barras amarelas são os pontos que, juntos, chegam a 80%.",
   logica="Agrupa as usinas pelo ponto de conexão do cadastro do ONS. Ponto de conexão é onde a usina se liga à rede de transmissão.",
   medidas="[Não realizada (GWh)] por ponto de conexão; o acumulado é calculado no próprio gráfico.",
   atencao="A maior parte do corte é sistêmica (veja a Visão executiva). A concentração por ponto não indica, sozinha, gargalo local."),
  dict(alvo=(476, 496, 380, 204), lado="esquerda",
   titulo="Concentração do corte",
   mostra="Quantos pontos de conexão e quantas usinas respondem por 80% da energia cortada.",
   ler="Quanto menor o número em relação ao total, mais concentrado está o corte.",
   logica="Ordena pontos e usinas do maior para o menor corte e conta quantos são precisos para somar 80% do total.",
   medidas="[Não realizada (GWh)] por ponto de conexão e por usina.",
   atencao=""),
  dict(alvo=(868, 496, 388, 204), lado="esquerda",
   titulo="Corte por subsistema",
   mostra="Energia cortada e % cortado em cada subsistema do sistema interligado.",
   ler="Subsistema é a divisão regional do SIN usada pelo ONS (Nordeste, Sudeste/Centro-Oeste, Sul, Norte).",
   logica="Agrupa as usinas pelo subsistema do cadastro.",
   medidas="[Não realizada (GWh)] e [% cortado].",
   atencao=""),
 ]),
 "usinas_agentes": dict(sigla="ua", passos=[
  dict(FILTROS, ler="Toda a página responde aos filtros, os mesmos em todas as páginas. Sem filtro de ano, mostra todo o histórico."),
  dict(alvo=(24, 84, 700, 616), lado="direita",
   titulo="Ranking de usinas",
   mostra="As 10 usinas e conjuntos com mais energia cortada, com fonte, estado, agente, % cortado e tendência de 24 meses.",
   ler="A barra amarela compara o volume com o primeiro colocado. Ponto vazado no fim da linha indica mês ainda incompleto.",
   logica="Ordena as usinas pela geração não realizada nos filtros. A tendência ignora o filtro de datas e mostra sempre os 24 meses até o último dia com dados.",
   medidas="[Não realizada (GWh)], [% cortado] e [svg · sparkline não realizada] por usina.",
   atencao="O ONS publica algumas usinas agrupadas em conjuntos; cada conjunto é uma linha. Use a página Detalhe da usina para ver uma delas."),
  dict(alvo=(736, 84, 520, 360), lado="esquerda",
   titulo="Porte x % cortado",
   mostra="Cada ponto é uma usina: porte (geração possível, em escala log) no eixo X e % cortado no eixo Y. O tamanho do ponto é o volume cortado.",
   ler="As linhas tracejadas são as medianas e dividem o gráfico em quatro grupos; cada canto diz quantas usinas estão naquele grupo. No alto à direita, usinas grandes e muito cortadas.",
   logica="Geração possível = verificada + não realizada.",
   medidas="[Geração possível (GWh)], [% cortado] e [Não realizada (GWh)] por usina.",
   atencao="Associação não implica causa. Usinas grandes tendem a ficar em pontos de rede mais carregados, mas o gráfico não prova isso."),
  dict(alvo=(736, 456, 520, 244), lado="esquerda",
   titulo="Agentes operadores",
   mostra="Os 10 agentes operadores com mais energia cortada nas suas usinas.",
   ler="O rótulo mostra o volume e o % cortado do conjunto das usinas do agente.",
   logica="Agente operador do cadastro mais recente de cada usina.",
   medidas="[Não realizada (GWh)] e [% cortado].",
   atencao="Agentes com muitas usinas aparecem naturalmente no topo; compare também o %."),
 ]),
 "detalhe_usina": dict(sigla="du", passos=[
  dict(alvo=(640, 20, 616, 44), lado="baixo",
   titulo="Escolha a usina",
   mostra="O botão Filtros abre a gaveta; nesta página o primeiro filtro é a Usina. Sem seleção, a página mostra o total de todas as usinas. O resumo ao lado diz o que está selecionado.",
   ler="Abra Filtros, clique em Usina e digite parte do nome. Ano, fonte e UF também valem aqui.",
   logica="Filtra a tabela Usinas, que filtra a fato diária.",
   medidas="Não é medida.",
   atencao=""),
  dict(alvo=(24, 84, 1232, 104), lado="baixo",
   titulo="Ficha da usina",
   mostra="Cadastro da usina (fonte, estado, agente, ponto de conexão, CEG, período nos dados) e seus indicadores.",
   ler="Os indicadores respeitam os filtros. Razão principal é a razão com mais energia cortada.",
   logica="Cadastro atual do ONS, a partir do snapshot do dbt.",
   medidas="[Não realizada (GWh)], [% cortado], [Dias com corte], [Horas por dia com corte] = horas de restrição / dias-usina com corte.",
   atencao="Conjuntos de usinas não têm CEG individual."),
  dict(alvo=(24, 200, 760, 500), lado="direita",
   titulo="Série mensal",
   mostra="Energia cortada (barras) e % cortado (linha) mês a mês.",
   ler="Eixo da esquerda em GWh, da direita em %. Passe o mouse para ver os dois valores.",
   logica="Soma mensal da fato diária para a usina selecionada.",
   medidas="[Não realizada (GWh)] e [Geração (GWh)], com o % calculado no gráfico.",
   atencao=""),
  dict(alvo=(796, 200, 460, 212), lado="esquerda",
   titulo="Razão e origem",
   mostra="Como o corte da usina se divide por razão e por origem da restrição.",
   ler="Cada barra soma 100%. Origem local é a rede próxima à usina; sistêmica é o sistema interligado.",
   logica="As mesmas contas da Visão executiva, sobre todo o histórico ou o ano filtrado.",
   medidas="[Energética (ENE)] a [Parecer de acesso (PAR)], [Sem razão (GWh)], [Origem local (GWh)], [Origem sistêmica (GWh)], [Sem origem (GWh)].",
   atencao=""),
  dict(alvo=(796, 424, 460, 276), lado="esquerda",
   titulo="Corte dia a dia",
   mostra="Calendário com a energia cortada em cada dia dos últimos 12 meses com dados da usina.",
   ler="Quadrados escuros são os dias de maior corte.",
   logica="365 dias até o último dia com dados nos filtros.",
   medidas="[Não realizada (GWh)] por dia.",
   atencao=""),
 ]),
}

# ---------------- helpers de visual ----------------
def container_objs(bg=None, transp=0, borda=None, largura=0, padding=None):
    o = {"visualHeader": [{"properties": {"show": lit("false")}}],
         "title": [{"properties": {"show": lit("false")}}]}
    o["background"] = [{"properties": {"show": lit("true" if bg else "false"),
                                       **({"color": cor(bg), "transparency": lit(f"{transp}D")} if bg else {})}}]
    o["border"] = [{"properties": {"show": lit("true" if borda else "false"),
                                   **({"color": cor(borda), "width": lit(f"{largura}D"), "radius": lit("0D")} if borda else {})}}]
    if padding is not None:
        o["padding"] = [{"properties": {k: lit(f"{padding}D") for k in ("top", "bottom", "left", "right")}}]
    return o

def run(texto, tam, cor_, negrito=False):
    return {"value": texto, "textStyle": {"fontSize": f"{tam}pt", "fontWeight": "bold" if negrito else "normal", "color": cor_}}

def textbox(nome, x, y, w, h, z, paragrafos, pai=None, **co):
    v = {"$schema": SCHEMA_VC, "name": nome,
         "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
         "visual": {"visualType": "textbox",
                    "objects": {"general": [{"properties": {"paragraphs": paragrafos}}]},
                    "visualContainerObjects": container_objs(**co),
                    "drillFilterOtherVisuals": True}}
    if pai: v["parentGroupName"] = pai
    return v

def botao(nome, x, y, w, h, z, texto, destino, fundo=None, cor_texto=INK, pai=None, tam=10):
    """actionButton com texto, sem borda. Formato conferido num botão salvo pelo Desktop:
    'show' vai num item sem seletor; texto, cor e preenchimento vão no item com selector default."""
    v = {"$schema": SCHEMA_VC, "name": nome,
         "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
         "visual": {"visualType": "actionButton",
                    "objects": {
                        "icon": [{"properties": {"shapeType": s("blank")}, "selector": {"id": "default"}}],
                        "text": [{"properties": {"show": lit("true")}},
                                 {"properties": {"text": s(texto), "fontColor": cor(cor_texto), "fontSize": lit(f"{tam}D"),
                                                 "bold": lit("true")}, "selector": {"id": "default"}}],
                        "outline": [{"properties": {"show": lit("false")}}],
                        "fill": [{"properties": {"show": lit("true" if fundo else "false")}}]
                                + ([{"properties": {"fillColor": cor(fundo), "transparency": lit("0D")}, "selector": {"id": "default"}}] if fundo else [])},
                    "visualContainerObjects": {
                        **container_objs(padding=0),
                        "visualLink": [{"properties": {"show": lit("true"), "type": s("Bookmark"), "bookmark": s(destino)}}]},
                    "drillFilterOtherVisuals": True}}
    if pai: v["parentGroupName"] = pai
    return v

def linhas(texto, chars=48):
    return max(1, math.ceil(len(texto) / chars))

def paragrafos_balao(k, n, p):
    par = [{"textRuns": [run(f"PASSO {k} DE {n}", 8, CINZA, True)]},
           {"textRuns": [run(p["titulo"], 13, AMARELO, True)]}]
    altura = 18 + 26
    for rot, chave in (("O QUE MOSTRA", "mostra"), ("COMO LER", "ler"), ("LÓGICA", "logica"), ("MEDIDAS", "medidas"), ("ATENÇÃO", "atencao")):
        if not p.get(chave): continue
        par.append({"textRuns": [run(rot, 8, AMARELO, True)]})
        par.append({"textRuns": [run(p[chave], 10, BRANCO)]})
        altura += 16 + linhas(p[chave]) * 17 + 6
    return par, altura

def escrever(pasta_pagina, v):
    if isinstance(v, list):
        for item in v: escrever(pasta_pagina, item)
        return
    d = os.path.join(pasta_pagina, "visuals", v["name"]); os.makedirs(d, exist_ok=True)
    json.dump(v, open(os.path.join(d, "visual.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# ---------------- limpeza das amostras e de um tour anterior ----------------
for pg in PAGINAS:
    vis = os.path.join(DEF, "pages", pg, "visuals")
    for nome in os.listdir(vis):
        if nome.startswith("tour_") or nome in ("25d86fa0090ea701beba", "a7424ee085b40296bb20", "e664effe3aed0a58b8bd"):
            shutil.rmtree(os.path.join(vis, nome))
bm_dir = os.path.join(DEF, "bookmarks")
if os.path.isdir(bm_dir):
    shutil.rmtree(bm_dir)
os.makedirs(bm_dir)

# ---------------- geração ----------------
grupos_bm = []
for pg, info in PAGINAS.items():
    sg, passos = info["sigla"], info["passos"]; n = len(passos)
    pasta = os.path.join(DEF, "pages", pg)
    grupos = [f"tour_{sg}_{k}" for k in range(1, n + 1)]
    off = f"tour_{sg}_off"

    # botão fixo "Documentação"
    escrever(pasta, botao(f"tour_{sg}_btn_doc", 1008, 26, 120, 32, 20000, "Documentação", f"tour_{sg}_1", fundo=AMARELO))

    for k, p in enumerate(passos, 1):
        g = grupos[k - 1]; zb = 30000 + k * 20
        escrever(pasta, {"$schema": SCHEMA_VC, "name": g,
                         "position": {"x": 0, "y": 0, "z": zb, "height": H, "width": W, "tabOrder": zb},
                         "visualGroup": {"displayName": f"Tour {k} - {p['titulo']}"[:60], "groupMode": "ScaleMode",
                                         # sem fundo: um tema com fundo padrão cobriria a página inteira
                                         "objects": {"background": [{"properties": {"show": lit("false")}}]}},
                         "isHidden": True})
        x, y, w, h = p["alvo"]
        fx, fy, fw, fh = x - 4, y - 4, w + 8, h + 8
        espaco = " "
        mascara = dict(bg=INK, transp=40)
        # máscara em 4 retângulos ao redor da moldura
        for i, (mx, my, mw, mh) in enumerate([(0, 0, W, fy), (0, fy + fh, W, H - fy - fh), (0, fy, fx, fh), (fx + fw, fy, W - fx - fw, fh)]):
            if mw > 0 and mh > 0:
                escrever(pasta, textbox(f"{g}_mask{i}", mx, my, mw, mh, zb + 1, [{"textRuns": [run(espaco, 8, INK)]}], pai=g, **mascara))
        escrever(pasta, textbox(f"{g}_moldura", fx, fy, fw, fh, zb + 2, [{"textRuns": [run(espaco, 8, INK)]}], pai=g, borda=AMARELO, largura=3))

        par, alt = paragrafos_balao(k, n, p)
        bh = min(alt + 12 + 44, H - 16)
        if p["lado"] == "direita": bx, by = fx + fw + 12, fy
        elif p["lado"] == "esquerda": bx, by = fx - 12 - BAL_W, fy
        else: bx, by = min(fx + fw - BAL_W, W - BAL_W - 8), fy + fh + 12
        by = max(8, min(by, H - bh - 8))
        escrever(pasta, textbox(f"{g}_balao", bx, by, BAL_W, bh, zb + 3, par, pai=g, bg=INK, transp=0, borda="#3C3C41", largura=1, padding=14))
        yb = by + bh - 44
        if k > 1:
            escrever(pasta, botao(f"{g}_ant", bx + 14, yb, 96, 30, zb + 7, "◀ Anterior", grupos[k - 2], cor_texto=CINZA, pai=g))
        if k < n:
            escrever(pasta, botao(f"{g}_prox", bx + BAL_W - 14 - 110, yb, 110, 30, zb + 9, "Próximo ▶", grupos[k], fundo=AMARELO, pai=g))
        else:
            escrever(pasta, botao(f"{g}_fim", bx + BAL_W - 14 - 110, yb, 110, 30, zb + 9, "Concluir ✓", off, fundo=AMARELO, pai=g))
        escrever(pasta, botao(f"{g}_fechar", bx + BAL_W - 36, by + 6, 30, 28, zb + 11, "✕", off, cor_texto=CINZA, pai=g, tam=10))

    # indicadores: um por passo + desligado; só exibição (sem dados)
    nomes = []
    for k in range(0, n + 1):
        nome = off if k == 0 else grupos[k - 1]
        bm = {"$schema": SCHEMA_BM,
              "displayName": ("Tour – desligado" if k == 0 else f"Tour – passo {k}"),
              "name": nome,
              "options": {"targetVisualNames": [], "suppressData": True},
              "explorationState": {"version": "1.3", "activeSection": pg,
                                   "sections": {pg: {"visualContainers": {},
                                                     "visualContainerGroups": {gg: {"isHidden": gg != nome} for gg in grupos}}}}}
        json.dump(bm, open(os.path.join(bm_dir, f"{nome}.bookmark.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        nomes.append(nome)
    titulo_pg = json.load(open(os.path.join(pasta, "page.json"), encoding="utf-8"))["displayName"]
    grupos_bm.append({"name": f"tour_{sg}", "displayName": f"Tour – {titulo_pg}", "children": nomes})

json.dump({"$schema": SCHEMA_BMS, "items": grupos_bm}, open(os.path.join(bm_dir, "bookmarks.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("ok", sum(len(i["passos"]) for i in PAGINAS.values()), "passos")
