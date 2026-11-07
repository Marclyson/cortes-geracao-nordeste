# Dicas de ferramenta ricas (páginas de tooltip) no padrão Dome para o CortesNordeste.
# Roda depois de remodelar_painel.py e remodelar_paginas.py. Uso: python3 gerar_dicas.py <pasta powerbi>
import json, os, re, shutil, sys, uuid

PBI = sys.argv[1]
SM = os.path.join(PBI, "CortesNordeste.SemanticModel", "definition")
RP = os.path.join(PBI, "CortesNordeste.Report", "definition")
RS = os.path.join(PBI, "CortesNordeste.Report", "StaticResources", "RegisteredResources", "DomeAnalytics.json")
FATO = "Restrição diária"
HTMLC = "htmlContent443BE3AD55E043BF878BED274D3A6865"
SCHEMA_VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.3.0/schema.json"
SCHEMA_PG = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.4.0/schema.json"
W, H = 360, 270  # tamanho das páginas de dica

def uid(seed): return str(uuid.uuid5(uuid.NAMESPACE_URL, "cortesnordeste/" + seed))
def rd(p): return open(p, encoding="utf-8").read()
def wr(p, t): open(p, "w", encoding="utf-8", newline="\n").write(t)
def jload(p): return json.load(open(p, encoding="utf-8"))
def jdump(o, p): json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
def lit(v): return {"expr": {"Literal": {"Value": v}}}
def s(v): return lit("'" + v.replace("'", "''") + "'")
def cor(c): return {"solid": {"color": s(c)}}

def medida(nome, expr, desc):
    linhas = expr.strip("\n").split("\n")
    t = f"\t/// {desc}\n\tmeasure '{nome}' =\n" + "".join(f"\t\t\t{l}\n" for l in linhas)
    return t + f"\t\tisHidden\n\t\tdisplayFolder: Dicas\n\t\tlineageTag: {uid('m/'+nome)}\n\n"

# ---------- trechos de DAX reaproveitados
BARRA_RAZOES = """VAR _T = [Não realizada (GWh)]
VAR _E = DIVIDE ( [Energética (ENE)], _T )
VAR _C = DIVIDE ( [Confiabilidade (CNF)], _T )
VAR _R = DIVIDE ( [Indisponibilidade externa (REL)], _T )
VAR _P = DIVIDE ( [Parecer de acesso (PAR)], _T )
VAR _Seg = ( VAR p = _E RETURN "<span style='width:" & FORMAT ( p * 100, "0.0", "en-US" ) & "%;background:#FFFFFF'></span>" )
    & ( VAR p = _C RETURN "<span style='width:" & FORMAT ( p * 100, "0.0", "en-US" ) & "%;background:#A19F9D'></span>" )
    & ( VAR p = _R RETURN "<span style='width:" & FORMAT ( p * 100, "0.0", "en-US" ) & "%;background:#605E5C'></span>" )
    & ( VAR p = _P RETURN "<span style='width:" & FORMAT ( p * 100, "0.0", "en-US" ) & "%;background:#F2C811'></span>" )
VAR _Leg = "ENE " & FORMAT ( _E, "0%" ) & " · CNF " & FORMAT ( _C, "0%" ) & " · REL " & FORMAT ( _R, "0%" ) & IF ( _P >= 0.005, " · PAR " & FORMAT ( _P, "0%" ) )
VAR _BlocoRazoes = "<div class='sec'>Razão do corte</div><div class='bar'>" & _Seg & "</div><div class='leg'>" & _Leg & "</div>\""""

M = []
M.append(medida("html · Dica mês", """VAR _Mes = MAX ( 'Calendário'[Mês] )
VAR _Ult = [Última data com dados]
VAR _Fonte = IF ( HASONEVALUE ( 'Fontes'[Fonte] ), " · " & VALUES ( 'Fontes'[Fonte] ), "" )
VAR _NR = [Não realizada (GWh)]
VAR _AA = CALCULATE ( [Não realizada (GWh)], SAMEPERIODLASTYEAR ( 'Calendário'[Data] ) )
VAR _Var = IF ( NOT ISBLANK ( _AA ) && _AA <> 0, DIVIDE ( _NR - _AA, _AA ) )
VAR _Tab =
    ADDCOLUMNS (
        CALCULATETABLE ( VALUES ( 'Calendário'[Mês] ), REMOVEFILTERS ( 'Calendário' ) ),
        "@v", VAR _m = 'Calendário'[Mês] RETURN CALCULATE ( [Não realizada (GWh)], REMOVEFILTERS ( 'Calendário' ), 'Calendário'[Mês] = _m )
    )
VAR _Rank = COUNTROWS ( FILTER ( _Tab, [@v] > _NR ) ) + 1
VAR _N = COUNTROWS ( FILTER ( _Tab, NOT ISBLANK ( [@v] ) ) )
VAR _Est = TOPN ( 1, ADDCOLUMNS ( VALUES ( 'Estados'[Estado] ), "@v", [Não realizada (GWh)] ), [@v], DESC )
VAR _Parcial = _Mes <= _Ult && EOMONTH ( _Mes, 0 ) > _Ult
""" + BARRA_RAZOES.replace('\\"', '') + """
RETURN
    IF ( ISBLANK ( _NR ) || _NR = 0, "<div class='tt'><div class='k'>Mês</div><div class='t'>" & FORMAT ( _Mes, "mmmm/yyyy" ) & _Fonte & "</div><div class='c'>Sem geração não realizada neste mês.</div></div>",
    "<div class='tt'><div class='k'>Mês</div><div class='t'>" & FORMAT ( _Mes, "mmmm/yyyy" ) & _Fonte & "</div>"
        & "<div class='g'><div><div class='v'>" & FORMAT ( _NR, "#,0" ) & "<small> GWh</small></div><div class='l'>não gerados</div></div>"
        & "<div><div class='v'>" & FORMAT ( [% cortado], "0.0%" ) & "</div><div class='l'>da geração possível</div></div></div>"
        & "<div class='c'>" & IF ( ISBLANK ( _Var ), "Sem base no mesmo mês do ano anterior", "<b class='" & IF ( _Var > 0, "ruim", "bom" ) & "'>" & IF ( _Var > 0, "▲ ", "▼ " ) & FORMAT ( ABS ( _Var ), "0%" ) & "</b> vs " & FORMAT ( EDATE ( _Mes, -12 ), "mmm/yyyy" ) )
        & " · <b>" & _Rank & "º</b> maior de " & _N & " meses</div>"
        & _BlocoRazoes
        & "<div class='f'>Mais corte: <b>" & MAXX ( _Est, 'Estados'[Estado] ) & "</b> (" & FORMAT ( DIVIDE ( MAXX ( _Est, [@v] ), _NR ), "0%" ) & " do mês)</div>"
        & IF ( _Parcial, "<div class='n'>Mês incompleto: dados até " & FORMAT ( _Ult, "dd/mm/yyyy" ) & "</div>" )
        & "</div>" )""", "Dica de ferramenta do mês (HTML Content)"))

M.append(medida("html · Dica estado", """VAR _Nome = SELECTEDVALUE ( 'Estados'[Estado] )
VAR _NR = [Não realizada (GWh)]
VAR _Pct = [% cortado]
VAR _Tot = CALCULATE ( [Não realizada (GWh)], REMOVEFILTERS ( 'Estados' ) )
VAR _Tab =
    FILTER (
        ADDCOLUMNS ( CALCULATETABLE ( VALUES ( 'Estados'[Estado] ), REMOVEFILTERS ( 'Estados' ) ),
            "@p", VAR _e = 'Estados'[Estado] RETURN CALCULATE ( [% cortado], REMOVEFILTERS ( 'Estados' ), 'Estados'[Estado] = _e ) ),
        NOT ISBLANK ( [@p] ) )
VAR _Rank = COUNTROWS ( FILTER ( _Tab, [@p] > _Pct ) ) + 1
VAR _Us = TOPN ( 1, ADDCOLUMNS ( VALUES ( 'Usinas'[Usina] ), "@v", [Não realizada (GWh)] ), [@v], DESC )
VAR _Pt = TOPN ( 1, ADDCOLUMNS ( VALUES ( 'Usinas'[Ponto de conexão] ), "@v", [Não realizada (GWh)] ), [@v], DESC )
""" + BARRA_RAZOES.replace('\\"', '') + """
RETURN
    IF ( ISBLANK ( _NR ), "<div class='tt'><div class='k'>Estado</div><div class='t'>" & _Nome & "</div><div class='c'>Sem geração não realizada nos filtros.</div></div>",
    "<div class='tt'><div class='k'>Estado</div><div class='t'>" & _Nome & "</div>"
        & "<div class='g'><div><div class='v'>" & FORMAT ( _Pct, "0.0%" ) & "</div><div class='l'>da geração possível cortada</div></div>"
        & "<div><div class='v'>" & FORMAT ( _NR, "#,0" ) & "<small> GWh</small></div><div class='l'>" & FORMAT ( DIVIDE ( _NR, _Tot ), "0%" ) & " do corte total</div></div></div>"
        & "<div class='c'><b>" & _Rank & "º</b> maior % de " & COUNTROWS ( _Tab ) & " estados · " & FORMAT ( [Usinas com corte], "#,0" ) & " usinas com corte</div>"
        & "<div class='spk'><span>% cortado, 24 meses</span>" & [svg · sparkline % cortado] & "</div>"
        & _BlocoRazoes
        & "<div class='f'>Maior usina: <b>" & MAXX ( _Us, 'Usinas'[Usina] ) & "</b> · maior ponto: <b>" & MAXX ( _Pt, 'Usinas'[Ponto de conexão] ) & "</b></div>"
        & "</div>" )""", "Dica de ferramenta do estado (HTML Content)"))

M.append(medida("html · Dica usina", """VAR _N = DISTINCTCOUNT ( 'Usinas'[ID da usina] )
VAR _NR = [Não realizada (GWh)]
VAR _Tab =
    FILTER (
        ADDCOLUMNS ( CALCULATETABLE ( VALUES ( 'Usinas'[ID da usina] ), REMOVEFILTERS ( 'Usinas' ) ),
            "@v", VAR _u = 'Usinas'[ID da usina] RETURN CALCULATE ( [Não realizada (GWh)], REMOVEFILTERS ( 'Usinas' ), 'Usinas'[ID da usina] = _u ) ),
        [@v] > 0 )
VAR _Rank = COUNTROWS ( FILTER ( _Tab, [@v] > _NR ) ) + 1
""" + BARRA_RAZOES.replace('\\"', '') + """
RETURN
    IF ( _N <> 1, "<div class='tt'><div class='c'>Passe o mouse sobre uma usina.</div></div>",
    "<div class='tt'><div class='k'>" & SELECTEDVALUE ( 'Usinas'[Fonte] ) & " · " & SELECTEDVALUE ( 'Usinas'[UF] ) & "</div><div class='t'>" & SELECTEDVALUE ( 'Usinas'[Usina] ) & "</div>"
        & "<div class='m'>" & SELECTEDVALUE ( 'Usinas'[Agente operador] ) & " · " & SELECTEDVALUE ( 'Usinas'[Ponto de conexão] ) & "</div>"
        & "<div class='g'><div><div class='v'>" & FORMAT ( _NR, "#,0" ) & "<small> GWh</small></div><div class='l'>não gerados</div></div>"
        & "<div><div class='v'>" & FORMAT ( [% cortado], "0.0%" ) & "</div><div class='l'>de " & FORMAT ( [Geração possível (GWh)], "#,0" ) & " GWh possíveis</div></div></div>"
        & "<div class='c'><b>" & _Rank & "º</b> maior corte de " & COUNTROWS ( _Tab ) & " usinas · " & FORMAT ( [Dias com corte], "#,0" ) & " dias com corte</div>"
        & "<div class='spk'><span>Corte mensal, 24 meses</span>" & [svg · sparkline não realizada] & "</div>"
        & _BlocoRazoes
        & "</div>" )""", "Dica de ferramenta da usina (HTML Content)"))

fato_p = os.path.join(SM, "tables", f"{FATO}.tmdl"); fato = rd(fato_p)
def _nome(x): return re.search(r"measure '([^']+)'", x).group(1)
for x in M:  # substitui se já existir (permite iterar no texto das dicas)
    n = _nome(x)
    fato = re.sub(r"\t/// [^\n]*\n\tmeasure '" + re.escape(n) + r"' =\n(?:\t\t[^\n]*\n|\n(?=\t\t))*", "", fato)
i = fato.index("\tpartition ")
wr(fato_p, fato[:i] + "".join(M) + fato[i:])

# ---------- páginas de dica
CSS = """*{font-family:'Segoe UI',sans-serif;box-sizing:border-box}
.tt{background:#191919;color:#FFFFFF;padding:12px 14px;border-top:3px solid #F2C811;min-height:100%}
.k{font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:#F2C811;font-weight:700}
.t{font-size:15px;font-weight:600;margin:2px 0 6px 0;line-height:1.2}
.m{font-size:10px;color:#C8C6C4;margin:-4px 0 6px 0}
.g{display:flex;gap:16px;margin-bottom:6px}.g>div{flex:1}
.v{font-size:20px;font-weight:600;line-height:1.1}.v small{font-size:11px;font-weight:400;color:#C8C6C4}
.l{font-size:10px;color:#C8C6C4}
.c{font-size:11px;color:#E1DFDD;margin-bottom:7px}.c b{color:#FFFFFF}.ruim{color:#FF8A65 !important}.bom{color:#7FD17F !important}
.sec{font-size:9px;letter-spacing:.06em;text-transform:uppercase;color:#A19F9D;margin-bottom:3px}
.bar{display:flex;height:8px;background:#3C3C41;margin-bottom:3px}.bar span{display:block;height:8px}
.leg{font-size:10px;color:#C8C6C4;margin-bottom:6px}
.spk{display:flex;align-items:center;justify-content:space-between;font-size:10px;color:#A19F9D;margin-bottom:6px}
.spk svg polyline{stroke:#C8C6C4}
.f{font-size:10px;color:#C8C6C4;border-top:1px solid #3C3C41;padding-top:6px}.f b{color:#FFFFFF}
.n{font-size:10px;color:#F2C811;margin-top:4px}"""

def pagina_dica(nome, exibicao, medida_nome):
    pg = os.path.join(RP, "pages", nome)
    if os.path.isdir(pg): shutil.rmtree(pg)
    os.makedirs(os.path.join(pg, "visuals", "conteudo"))
    jdump({"$schema": SCHEMA_PG, "name": nome, "displayName": exibicao, "displayOption": "ActualSize",
           "height": H, "width": W, "type": "Tooltip", "visibility": "HiddenInViewMode"}, os.path.join(pg, "page.json"))
    jdump({"$schema": SCHEMA_VC, "name": "conteudo", "position": {"x": 0, "y": 0, "z": 1000, "height": H, "width": W, "tabOrder": 1000},
           "visual": {"visualType": HTMLC,
                      "query": {"queryState": {"content": {"projections": [{"field": {"Measure": {"Expression": {"SourceRef": {"Entity": FATO}}, "Property": medida_nome}},
                                                                            "queryRef": f"{FATO}.{medida_nome}", "nativeQueryRef": medida_nome}]}}},
                      "objects": {"compatibility": [{"properties": {"legacyRendering": lit("false")}}], "stylesheet": [{"properties": {"stylesheet": s(CSS)}}]},
                      "visualContainerObjects": {
                          "title": [{"properties": {"show": lit("false")}}], "visualHeader": [{"properties": {"show": lit("false")}}],
                          "background": [{"properties": {"show": lit("true"), "color": cor("#191919"), "transparency": lit("0D")}}],
                          "border": [{"properties": {"show": lit("false")}}],
                          "padding": [{"properties": {k: lit("0D") for k in ("top", "bottom", "left", "right")}}]},
                      "drillFilterOtherVisuals": True}}, os.path.join(pg, "visuals", "conteudo", "visual.json"))

pagina_dica("dica_mes", "Dica · mês", "html · Dica mês")
pagina_dica("dica_estado", "Dica · estado", "html · Dica estado")
pagina_dica("dica_usina", "Dica · usina", "html · Dica usina")

pj = os.path.join(RP, "pages", "pages.json"); pages = jload(pj)
for n in list(pages["pageOrder"]):  # remove páginas de dica antigas/de teste
    pjson = os.path.join(RP, "pages", n, "page.json")
    if not os.path.exists(pjson) or (jload(pjson).get("type") == "Tooltip" and n not in ("dica_mes", "dica_estado", "dica_usina")):
        pages["pageOrder"].remove(n)
        if os.path.isdir(os.path.join(RP, "pages", n)): shutil.rmtree(os.path.join(RP, "pages", n))
for n in ("dica_mes", "dica_estado", "dica_usina"):
    if n not in pages["pageOrder"]: pages["pageOrder"].append(n)
pages["activePageName"] = "visao_geral"
jdump(pages, pj)

# ---------- liga os visuais às páginas de dica
LIGACOES = {
    ("visao_geral", "hero_barras"): "dica_mes", ("visao_geral", "hero_pct"): "dica_mes",
    ("razoes_sazonalidade", "participacao"): "dica_mes", ("razoes_sazonalidade", "heatmap"): "dica_mes",
    ("estados_usinas", "uf"): "dica_estado",
    ("usinas_agentes", "dispersao"): "dica_usina",
}
for (pg, vis), dica in LIGACOES.items():
    p = os.path.join(RP, "pages", pg, "visuals", vis, "visual.json"); v = jload(p)
    v["visual"].setdefault("visualContainerObjects", {})["visualTooltip"] = [{"properties": {"show": lit("true"), "section": s(dica)}}]
    jdump(v, p)

# ---------- dica padrão no estilo Dome (tema), para os visuais sem página de dica
tema = jload(RS)
tema["visualStyles"]["*"]["*"]["visualTooltip"] = [{"background": {"solid": {"color": "#191919"}}, "titleFontColor": {"solid": {"color": "#F2C811"}},
                                                    "valueFontColor": {"solid": {"color": "#FFFFFF"}}, "fontSize": 10, "transparency": 0}]
jdump(tema, RS)
print("ok: 3 páginas de dica,", len(LIGACOES), "visuais ligados")
