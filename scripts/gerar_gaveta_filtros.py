#!/usr/bin/env python3
"""Gaveta de filtros com ícone, gerada nos arquivos PBIR (padrão Dome: ver a skill dome-powerbi-architect, references/filtros-menus.md).

EXEMPLO do projeto CortesNordeste: adapte a seção CONFIGURAÇÃO (tabelas, colunas, segmentações,
posições) ao seu relatório. Uso:
    python3 gerar_gaveta_filtros_exemplo.py <pasta powerbi>

Rode DEPOIS do gerador do tour (que recria a pasta bookmarks) e antes do script de acessibilidade.
Idempotente: recria a gaveta, os botões e os indicadores a cada execução.

O que faz, em cada página:
  - move as segmentações listadas para dentro do grupo 'filtros_gaveta' (painel à direita) e as
    sincroniza entre páginas (syncGroup);
  - cria no cabeçalho o resumo dos filtros ativos (HTML Content) e o botão de filtro com contador;
  - cria os indicadores filtros_<sigla>_abrir/fechar, só de exibição (suppressData), e os acrescenta
    ao bookmarks.json;
  - cria as medidas do resumo e do botão no modelo (TMDL), substituindo versões anteriores.
"""
import json, os, re, shutil, sys, uuid

# ----------------------------------------------------------------------------- CONFIGURAÇÃO
PBI = sys.argv[1]
SM = os.path.join(PBI, "CortesNordeste.SemanticModel", "definition")
DEF = os.path.join(PBI, "CortesNordeste.Report", "definition")
FATO = "Restrição diária"                      # tabela que recebe as medidas
PAGINAS = {"visao_geral": "vg", "razoes_sazonalidade": "rs", "estados_usinas": "eu",
           "usinas_agentes": "ua", "detalhe_usina": "du"}
GAVETA = ["filtro_ano", "filtro_fonte", "filtro_uf"]       # segmentações que vão para a gaveta, nesta ordem
GAVETA_PAGINA = {"detalhe_usina": ["filtro_usina", "filtro_ano", "filtro_fonte", "filtro_uf"]}  # páginas com filtros a mais (o principal primeiro)
SYNC = {"filtro_ano": "Ano", "filtro_fonte": "Fonte", "filtro_uf": "UF", "filtro_usina": "Usina"}
W, H = 1280, 720
PAINEL_X, PAINEL_W = 920, 360
RESUMO = (640, 20, 356, 44)     # x, y, w, h do resumo no cabeçalho
BOTAO = (1136, 26, 120, 32)     # botão de filtro
INK, AMARELO, MUTED, BRANCO = "#191919", "#F2C811", "#605E5C", "#FFFFFF"
SCHEMA_VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.3.0/schema.json"
SCHEMA_BM = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/bookmark/1.4.0/schema.json"
HTMLC = "htmlContent443BE3AD55E043BF878BED274D3A6865"

# Medidas (DAX). ISFILTERED nas colunas das segmentações; o resumo lista até 3 valores por filtro.
def lista(col, rotulo_varios, sufixo, max_itens=3):
    n = f"_n{sufixo}"  # nomes de VAR únicos na medida inteira
    return f"""IF ( ISFILTERED ( {col} ),
        VAR {n} = COUNTROWS ( VALUES ( {col} ) )
        RETURN IF ( {n} <= {max_itens}, CONCATENATEX ( VALUES ( {col} ), {col}, ", ", {col}, ASC ), {n} & " {rotulo_varios}" ) )"""

MEDIDAS = {
    "Filtros · contagem": ("""INT ( ISFILTERED ( 'Calendário'[Ano] ) ) + INT ( ISFILTERED ( 'Fontes'[Fonte] ) ) + INT ( ISFILTERED ( 'Estados'[UF] ) ) + INT ( ISFILTERED ( 'Usinas'[Usina] ) )""",
                           "0", "Quantos filtros da gaveta estão em uso (contador do botão)"),
    "Filtros · botão": ("""VAR _n = [Filtros · contagem]
RETURN "⏷  Filtros" & IF ( _n > 0, "  ·  " & _n )""", None, "Texto do botão que abre a gaveta de filtros"),
    "Filtros ativos (texto)": (f"""VAR _Ano = {lista("'Calendário'[Ano]", "anos", "Ano")}
VAR _Fonte = {lista("'Fontes'[Fonte]", "fontes", "Fonte")}
VAR _UF = {lista("'Estados'[UF]", "estados", "UF")}
VAR _Mes = IF ( ISFILTERED ( 'Calendário'[Mês] ), VAR _nMes = COUNTROWS ( VALUES ( 'Calendário'[Mês] ) )
        RETURN IF ( _nMes = 1, FORMAT ( MAX ( 'Calendário'[Mês] ), "mmm/yyyy" ), _nMes & " meses" ) )
VAR _Usina = IF ( ISFILTERED ( 'Usinas'[Usina] ), IF ( HASONEVALUE ( 'Usinas'[Usina] ), VALUES ( 'Usinas'[Usina] ), COUNTROWS ( VALUES ( 'Usinas'[Usina] ) ) & " usinas" ) )
VAR _Itens = FILTER ( {{ COALESCE ( _Mes, _Ano, "Todo o período" ), _Fonte, _UF, _Usina }}, NOT ISBLANK ( [Value] ) && [Value] <> "" )
RETURN CONCATENATEX ( _Itens, [Value], "  ·  " )""", None, "Resumo dos filtros em uso, para o cabeçalho"),
    "html · Filtros ativos": ("""VAR _n = [Filtros · contagem]
RETURN "<div class='f'><span class='k'>" & IF ( _n > 0, "Filtros", "Sem filtros" ) & "</span>" & [Filtros ativos (texto)] & "</div>\"""",
                              None, "Resumo dos filtros em uso (HTML Content do cabeçalho)"),
}
CSS_RESUMO = """*{font-family:'Segoe UI',sans-serif}
.f{text-align:right;font-size:12px;color:#191919;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-top:12px}
.k{font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:#8A8886;font-weight:600;margin-right:8px}"""
NOTA = "Os gráficos também filtram: clique numa barra, num estado ou numa usina. Ctrl+clique soma pontos; clique num espaço vazio para limpar."

# ----------------------------------------------------------------------------- HELPERS
def lit(v): return {"expr": {"Literal": {"Value": v}}}
def s(v): return lit("'" + v.replace("'", "''") + "'")
def cor(c): return {"solid": {"color": s(c)}}
def medida_ref(nome): return {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": FATO}}, "Property": nome}}}
def jload(p): return json.load(open(p, encoding="utf-8"))
def jdump(o, p): json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def chrome(bg=None, transp=0, padding=0, borda=None):
    o = {"visualHeader": [{"properties": {"show": lit("false")}}], "title": [{"properties": {"show": lit("false")}}],
         "background": [{"properties": {"show": lit("true" if bg else "false"), **({"color": cor(bg), "transparency": lit(f"{transp}D")} if bg else {})}}],
         "border": [{"properties": {"show": lit("true" if borda else "false"), **({"color": cor(borda), "width": lit("1D"), "radius": lit("0D")} if borda else {})}}],
         "padding": [{"properties": {k: lit(f"{padding}D") for k in ("top", "bottom", "left", "right")}}]}
    return o

def vc(nome, x, y, w, h, z, visual, pai=None):
    v = {"$schema": SCHEMA_VC, "name": nome, "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z}, "visual": visual}
    if pai: v["parentGroupName"] = pai
    return v

def botao(nome, x, y, w, h, z, texto, acao, fundo=None, cor_texto=INK, pai=None, tam=10, transp=0, texto_medida=None):
    """acao: ('Bookmark', nome) ou ('ClearAllSlicers', None) ou None."""
    t = {"text": medida_ref(texto_medida) if texto_medida else s(texto or ""), "fontColor": cor(cor_texto), "fontSize": lit(f"{tam}D"), "bold": lit("true")}
    vis = {"visualType": "actionButton",
           "objects": {"icon": [{"properties": {"shapeType": s("blank")}, "selector": {"id": "default"}}],
                       "text": [{"properties": {"show": lit("true" if (texto or texto_medida) else "false")}}, {"properties": t, "selector": {"id": "default"}}],
                       "outline": [{"properties": {"show": lit("false")}}],
                       "fill": [{"properties": {"show": lit("true" if fundo else "false")}}]
                               + ([{"properties": {"fillColor": cor(fundo), "transparency": lit(f"{transp}D")}, "selector": {"id": "default"}}] if fundo else [])},
           "visualContainerObjects": chrome(), "drillFilterOtherVisuals": True}
    if acao:
        tipo, destino = acao
        link = {"show": lit("true"), "type": s(tipo)}
        if destino: link["bookmark"] = s(destino)
        vis["visualContainerObjects"]["visualLink"] = [{"properties": link}]
    return vc(nome, x, y, w, h, z, vis, pai)

def caixa(nome, x, y, w, h, z, paragrafos, pai=None, bg=None, transp=0, padding=0):
    return vc(nome, x, y, w, h, z, {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": paragrafos}}]},
                                    "visualContainerObjects": chrome(bg, transp, padding), "drillFilterOtherVisuals": True}, pai)

def run(t, tam, c, b=False): return {"value": t, "textStyle": {"fontSize": f"{tam}pt", "fontWeight": "bold" if b else "normal", "color": c}}

# ----------------------------------------------------------------------------- MEDIDAS NO TMDL
fato_p = os.path.join(SM, "tables", f"{FATO}.tmdl")
fato = open(fato_p, encoding="utf-8").read()
blocos = []
for nome, (expr, fmt, desc) in MEDIDAS.items():
    fato = re.sub(r"(?:\t/// [^\n]*\n)?\tmeasure '" + re.escape(nome) + r"' =[^\n]*\n(?:\t\t[^\n]*\n|\n(?=\t\t))*", "", fato)
    linhas = "\n".join("\t\t\t" + l for l in expr.splitlines())
    b = f"\t/// {desc}\n\tmeasure '{nome}' =\n{linhas}\n"
    if fmt: b += f"\t\tformatString: {fmt}\n"
    b += f"\t\tisHidden\n\t\tdisplayFolder: Visual\n\t\tlineageTag: {uuid.uuid5(uuid.NAMESPACE_URL, 'gaveta/' + nome)}\n\n"
    blocos.append(b)
i = fato.index("\tpartition ")
open(fato_p, "w", encoding="utf-8", newline="\n").write(fato[:i] + "".join(blocos) + fato[i:])

# ----------------------------------------------------------------------------- PÁGINAS
bm_dir = os.path.join(DEF, "bookmarks"); os.makedirs(bm_dir, exist_ok=True)
bms_p = os.path.join(bm_dir, "bookmarks.json")
bms = jload(bms_p) if os.path.exists(bms_p) else {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/bookmarksMetadata/1.0.0/schema.json", "items": []}
bms["items"] = [it for it in bms["items"] if not it.get("name", "").startswith("filtros_")]

for pg, sg in PAGINAS.items():
    pasta = os.path.join(DEF, "pages", pg, "visuals")
    for n in os.listdir(pasta):
        if n.startswith("filtros_"): shutil.rmtree(os.path.join(pasta, n))
    g, abrir, fechar = "filtros_gaveta", f"filtros_{sg}_abrir", f"filtros_{sg}_fechar"
    def escrever(v):
        os.makedirs(os.path.join(pasta, v["name"]), exist_ok=True); jdump(v, os.path.join(pasta, v["name"], "visual.json"))

    # cabeçalho: resumo + botão
    x, y, w, h = RESUMO
    escrever(vc("filtros_resumo", x, y, w, h, 1500, {"visualType": HTMLC,
        "query": {"queryState": {"content": {"projections": [{"field": {"Measure": {"Expression": {"SourceRef": {"Entity": FATO}}, "Property": "html · Filtros ativos"}},
                                                               "queryRef": f"{FATO}.html · Filtros ativos", "nativeQueryRef": "html · Filtros ativos"}]}}},
        "objects": {"compatibility": [{"properties": {"legacyRendering": lit("false")}}], "stylesheet": [{"properties": {"stylesheet": s(CSS_RESUMO)}}]},
        "visualContainerObjects": chrome(), "drillFilterOtherVisuals": True}))
    x, y, w, h = BOTAO
    escrever(botao("filtros_botao", x, y, w, h, 1600, None, ("Bookmark", abrir), fundo=INK, cor_texto=BRANCO, texto_medida="Filtros · botão"))

    # gaveta
    escrever({"$schema": SCHEMA_VC, "name": g, "position": {"x": 0, "y": 0, "z": 40000, "height": H, "width": W, "tabOrder": 40000},
              "visualGroup": {"displayName": "Gaveta de filtros", "groupMode": "ScaleMode",
                              "objects": {"background": [{"properties": {"show": lit("false")}}]}},
              "isHidden": True})
    escrever(botao("filtros_veu", 0, 0, PAINEL_X, H, 40001, None, ("Bookmark", fechar), fundo=INK, transp=45, pai=g))
    escrever(caixa("filtros_painel", PAINEL_X, 0, PAINEL_W, H, 40002, [{"textRuns": [run(" ", 8, INK)]}], pai=g, bg=BRANCO))
    escrever(caixa("filtros_filete", PAINEL_X, 0, PAINEL_W, 4, 40003, [{"textRuns": [run(" ", 2, AMARELO)]}], pai=g, bg=AMARELO))
    px = PAINEL_X + 24; pw = PAINEL_W - 48
    escrever(caixa("filtros_titulo", px, 24, pw - 40, 48, 40004, [{"textRuns": [run("FILTROS", 9, "#967100", True)]},
                                                                  {"textRuns": [run("Valem para todas as páginas", 10, MUTED)]}], pai=g))
    escrever(botao("filtros_fechar", PAINEL_X + PAINEL_W - 56, 24, 32, 32, 40010, "✕", ("Bookmark", fechar), cor_texto=MUTED, pai=g, tam=11))
    yy = 88
    gaveta = GAVETA_PAGINA.get(pg, GAVETA)
    for k, nome in enumerate(gaveta):
        p = os.path.join(pasta, nome, "visual.json")
        f = jload(p)
        f["position"].update({"x": px, "y": yy, "width": pw, "height": 68, "z": 40005 + k})
        # padding explícito: o do tema ("*", 10/12 px) corta a borda inferior da caixa da lista suspensa
        f["visual"].setdefault("visualContainerObjects", {})["padding"] = [{"properties": {"top": {"expr": {"Literal": {"Value": "0D"}}}, "bottom": {"expr": {"Literal": {"Value": "4D"}}},
                                                                                          "left": {"expr": {"Literal": {"Value": "0D"}}}, "right": {"expr": {"Literal": {"Value": "0D"}}}}}]
        f["parentGroupName"] = g
        f["visual"]["syncGroup"] = {"groupName": SYNC[nome], "fieldChanges": True, "filterChanges": True}
        jdump(f, p)
        yy += 80
    for nome in os.listdir(pasta):  # segmentações que ficam fora da gaveta também sincronizam
        if nome in SYNC and nome not in gaveta:
            p = os.path.join(pasta, nome, "visual.json"); f = jload(p)
            f["visual"]["syncGroup"] = {"groupName": SYNC[nome], "fieldChanges": True, "filterChanges": True}
            jdump(f, p)
    yy += 8
    escrever(botao("filtros_limpar", px, yy, 150, 34, 40011, "Limpar filtros", ("ClearAllSlicers", None), cor_texto=INK, pai=g))
    escrever(botao("filtros_ok", px + pw - 150, yy, 150, 34, 40012, "Ver resultado", ("Bookmark", fechar), fundo=AMARELO, pai=g))
    escrever(caixa("filtros_nota", px, yy + 56, pw, 80, 40013, [{"textRuns": [run(NOTA, 9, MUTED)]}], pai=g))

    # indicadores só de exibição
    for nome, oculto, rotulo in ((abrir, False, "abrir"), (fechar, True, "fechar")):
        jdump({"$schema": SCHEMA_BM, "displayName": f"Filtros – {rotulo}", "name": nome,
               "options": {"targetVisualNames": [], "suppressData": True},
               "explorationState": {"version": "1.3", "activeSection": pg,
                                    "sections": {pg: {"visualContainers": {}, "visualContainerGroups": {g: {"isHidden": oculto}}}}}},
              os.path.join(bm_dir, f"{nome}.bookmark.json"))
    titulo = jload(os.path.join(DEF, "pages", pg, "page.json"))["displayName"]
    bms["items"].append({"name": f"filtros_{sg}", "displayName": f"Filtros – {titulo}", "children": [abrir, fechar]})

jdump(bms, bms_p)
print("ok: gaveta de filtros em", len(PAGINAS), "páginas")
