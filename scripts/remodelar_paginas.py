# Remodelagem do painel CortesNordeste no padrão Dome (etapa 2: páginas de análise).
# Roda depois de remodelar_painel.py. Uso: python3 remodelar_paginas.py <pasta powerbi>
import json, os, re, shutil, sys, uuid

PBI = sys.argv[1]
SM = os.path.join(PBI, "CortesNordeste.SemanticModel", "definition")
RP = os.path.join(PBI, "CortesNordeste.Report", "definition")
FATO = "Restrição diária"
DENEB = "deneb7E15AEF80B9E4D4F8E12924291ECE89A"
HTMLC = "htmlContent443BE3AD55E043BF878BED274D3A6865"
SCHEMA_VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.3.0/schema.json"
SCHEMA_PG = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.4.0/schema.json"

def uid(seed): return str(uuid.uuid5(uuid.NAMESPACE_URL, "cortesnordeste/" + seed))
def rd(p): return open(p, encoding="utf-8").read()
def wr(p, t): open(p, "w", encoding="utf-8", newline="\n").write(t)
def jload(p): return json.load(open(p, encoding="utf-8"))
def jdump(o, p): json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# =====================================================================================
# 1. MEDIDAS NOVAS
# =====================================================================================
def medida(nome, expr, fmt=None, pasta=None, desc=None, oculta=False):
    linhas = expr.strip("\n").split("\n")
    t = f"\tmeasure '{nome}' = {linhas[0]}\n" if len(linhas) == 1 else f"\tmeasure '{nome}' =\n" + "".join(f"\t\t\t{l}\n" for l in linhas)
    if desc: t = f"\t/// {desc}\n" + t
    if fmt: t += f"\t\tformatString: {fmt}\n"
    if oculta: t += "\t\tisHidden\n"
    if pasta: t += f"\t\tdisplayFolder: {pasta}\n"
    return t + f"\t\tlineageTag: {uid('m/'+nome)}\n\n"

M = []
M.append(medida("Dias com corte", f"CALCULATE(DISTINCTCOUNT('{FATO}'[dia]), '{FATO}'[nao_realizada_mwh] > 0)", "#,0", "Base", "Dias com alguma geração não realizada"))
M.append(medida("Horas por dia com corte", f"DIVIDE([Horas de restrição], CALCULATE(COUNTROWS('{FATO}'), '{FATO}'[nao_realizada_mwh] > 0))", "0.0", "Base",
                "Média de horas com restrição em cada dia de cada usina com corte"))

conc = """VAR _P = FILTER ( ADDCOLUMNS ( VALUES ( 'Usinas'[Ponto de conexão] ), "@v", [Não realizada (GWh)] ), [@v] > 0 )
VAR _PT = SUMX ( _P, [@v] )
VAR _PN = COUNTROWS ( _P )
VAR _P80 = COUNTROWS ( FILTER ( _P, VAR _x = [@v] RETURN SUMX ( FILTER ( _P, [@v] > _x ), [@v] ) < 0.8 * _PT ) )
VAR _U = FILTER ( ADDCOLUMNS ( VALUES ( 'Usinas'[ID da usina] ), "@v", [Não realizada (GWh)] ), [@v] > 0 )
VAR _UT = SUMX ( _U, [@v] )
VAR _UN = COUNTROWS ( _U )
VAR _U80 = COUNTROWS ( FILTER ( _U, VAR _x = [@v] RETURN SUMX ( FILTER ( _U, [@v] > _x ), [@v] ) < 0.8 * _UT ) )
VAR _Top = TOPN ( 1, _P, [@v], DESC )
VAR _TopNome = MAXX ( _Top, 'Usinas'[Ponto de conexão] )
VAR _TopPct = DIVIDE ( MAXX ( _Top, [@v] ), _PT )
RETURN
    IF ( ISBLANK ( _PT ), "<div class='vazio'>Sem geração não realizada nos filtros selecionados.</div>",
    "<div class='tit'>Concentração do corte</div>"
        & "<div class='st'><div class='n'>" & _P80 & "<span> de " & _PN & "</span></div><div class='d'>pontos de conexão somam 80% da energia cortada</div></div>"
        & "<div class='st'><div class='n'>" & _U80 & "<span> de " & _UN & "</span></div><div class='d'>usinas e conjuntos somam 80% da energia cortada</div></div>"
        & "<div class='top'>Maior ponto: <b>" & _TopNome & "</b>, com " & FORMAT ( _TopPct, "0%" ) & " do total.</div>" )"""
M.append(medida("html · Concentração", conc, None, "Visual", "Concentração do corte por ponto de conexão e por usina (HTML Content)", oculta=True))

# Ranking em linhas: uma linha por usina (papel Contexto do HTML Content), para o clique filtrar a página
rank_base = """VAR _v = [Não realizada (GWh)]
VAR _Tab = FILTER ( ADDCOLUMNS ( ALLSELECTED ( 'Usinas'[ID da usina] ), "@v", [Não realizada (GWh)] ), [@v] > 0 )
VAR _r = COUNTROWS ( FILTER ( _Tab, [@v] > _v ) ) + 1"""
rank_valor = rank_base + """
RETURN IF ( HASONEVALUE ( 'Usinas'[ID da usina] ) && _v > 0 && _r <= 10, _v )"""
M.append(medida("Ranking · valor", rank_valor, "#,0", "Visual", "Geração não realizada das 10 usinas com mais corte; vazio para as demais (ordena e limita o ranking)", oculta=True))
rank = rank_base + """
VAR _Max = MAXX ( _Tab, [@v] )
VAR _meta = SELECTEDVALUE ( 'Usinas'[Fonte] ) & " · " & SELECTEDVALUE ( 'Usinas'[UF] ) & " · " & SELECTEDVALUE ( 'Usinas'[Agente operador] )
VAR _cab = "<div class='lin cab'><div></div><div>Usina ou conjunto</div><div class='dir'>Não realizada</div><div class='dir'>% cortado</div><div>24 meses</div></div>"
RETURN
    IF ( HASONEVALUE ( 'Usinas'[ID da usina] ) && _v > 0 && _r <= 10,
        IF ( _r = 1, _cab, "" )
            & "<div class='lin" & IF ( _r = 1, " top", "" ) & "'><div class='r'>" & _r & "</div>"
            & "<div><div class='nm'>" & SELECTEDVALUE ( 'Usinas'[Usina] ) & "</div><div class='mt'>" & _meta & "</div></div>"
            & "<div class='dir'><div class='vl'>" & FORMAT ( _v, "#,0" ) & " GWh</div><div class='bar'><span style='width:" & FORMAT ( DIVIDE ( _v, _Max ) * 100, "0", "en-US" ) & "%'></span></div></div>"
            & "<div class='dir pc'>" & FORMAT ( [% cortado], "0.0%" ) & "</div><div class='sp'>" & [svg · sparkline não realizada] & "</div></div>" )"""
M.append(medida("html · Linha ranking", rank, None, "Visual", "Uma linha do ranking das 10 usinas com mais corte (HTML Content com a usina no Contexto)", oculta=True))

usina = """VAR _N = DISTINCTCOUNT ( 'Usinas'[ID da usina] )
VAR _Razoes =
    { ( "Energética (ENE)", [Energética (ENE)] ), ( "Confiabilidade (CNF)", [Confiabilidade (CNF)] ),
      ( "Indisponibilidade externa (REL)", [Indisponibilidade externa (REL)] ), ( "Parecer de acesso (PAR)", [Parecer de acesso (PAR)] ) }
VAR _RTop = MAXX ( TOPN ( 1, _Razoes, [Value2], DESC ), [Value1] )
VAR _Cab =
    IF ( _N = 1,
        "<div class='k'>" & SELECTEDVALUE ( 'Usinas'[Fonte] ) & " · " & SELECTEDVALUE ( 'Usinas'[Estado] ) & IF ( SELECTEDVALUE ( 'Usinas'[Conjunto de usinas] ), " · conjunto de usinas", "" ) & "</div>"
            & "<div class='nm'>" & SELECTEDVALUE ( 'Usinas'[Usina] ) & "</div>"
            & "<div class='at'><span><b>Agente</b> " & SELECTEDVALUE ( 'Usinas'[Agente operador] ) & "</span><span><b>Ponto de conexão</b> " & SELECTEDVALUE ( 'Usinas'[Ponto de conexão] ) & "</span>"
            & "<span><b>CEG</b> " & COALESCE ( SELECTEDVALUE ( 'Usinas'[CEG] ), "—" ) & "</span><span><b>Nos dados</b> " & FORMAT ( SELECTEDVALUE ( 'Usinas'[Primeiro dia] ), "mm/yyyy" ) & " a " & FORMAT ( SELECTEDVALUE ( 'Usinas'[Último dia] ), "mm/yyyy" ) & "</span></div>",
        "<div class='k'>Nenhuma usina selecionada</div><div class='nm'>Todas as " & FORMAT ( _N, "#,0" ) & " usinas e conjuntos</div><div class='at'><span>Abra <b>Filtros</b> e escolha a usina para ver a ficha dela.</span></div>" )
RETURN
    "<div class='wrap'><div class='cab'>" & _Cab & "</div><div class='kp'>"
        & "<div class='c'><div class='r'>Não realizada</div><div class='v'>" & FORMAT ( [Não realizada (GWh)], "#,0" ) & "<small> GWh</small></div></div>"
        & "<div class='c'><div class='r'>% cortado</div><div class='v'>" & FORMAT ( [% cortado], "0.0%" ) & "</div></div>"
        & "<div class='c'><div class='r'>Dias com corte</div><div class='v'>" & FORMAT ( [Dias com corte], "#,0" ) & "</div></div>"
        & "<div class='c'><div class='r'>Horas por dia com corte</div><div class='v'>" & FORMAT ( [Horas por dia com corte], "0.0" ) & "<small> h</small></div></div>"
        & "<div class='c'><div class='r'>Razão principal</div><div class='v t'>" & COALESCE ( _RTop, "—" ) & "</div></div>"
        & "</div></div>\""""
M.append(medida("html · Usina", usina, None, "Visual", "Ficha da usina selecionada (HTML Content)", oculta=True))

fato_p = os.path.join(SM, "tables", f"{FATO}.tmdl")
fato = rd(fato_p)
def _nome(x): return re.search(r"measure '([^']+)'", x).group(1)
REMOVIDAS = ["html · Ranking usinas"]  # medidas substituídas por versões novas
for nome in [_nome(x) for x in M] + REMOVIDAS:  # substitui medidas já existentes, para que mudanças no texto sejam aplicadas
    fato = re.sub(r"(?:\t/// [^\n]*\n)?\tmeasure '" + re.escape(nome) + r"' =[^\n]*\n(?:\t\t[^\n]*\n|\n(?=\t\t))*", "", fato)
novas = "".join(M)
if novas:
    i = fato.index("\tpartition ")
    wr(fato_p, fato[:i] + novas + fato[i:])

# =====================================================================================
# 2. HELPERS DE VISUAL
# =====================================================================================
def lit(v): return {"expr": {"Literal": {"Value": v}}}
def s(v): return lit("'" + v.replace("'", "''") + "'")
def cor(c): return {"solid": {"color": s(c)}}
def proj_m(ent, nome): return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": ent}}, "Property": nome}}, "queryRef": f"{ent}.{nome}", "nativeQueryRef": nome}
def proj_c(ent, nome): return {"field": {"Column": {"Expression": {"SourceRef": {"Entity": ent}}, "Property": nome}}, "queryRef": f"{ent}.{nome}", "nativeQueryRef": nome}
def zpad(): return [{"properties": {k: lit("0D") for k in ("top", "bottom", "left", "right")}}]

def container(titulo=None, fundo=True, borda=True):
    return {"title": [{"properties": {"show": lit("true" if titulo else "false"), **({"text": s(titulo), "fontSize": lit("11D"), "fontColor": cor("#191919"), "bold": lit("true")} if titulo else {})}}],
            "background": [{"properties": {"show": lit("true" if fundo else "false"), **({"color": cor("#FFFFFF"), "transparency": lit("0D")} if fundo else {})}}],
            "border": [{"properties": {"show": lit("true" if borda else "false"), **({"color": cor("#E1DFDD"), "width": lit("1D"), "radius": lit("2D")} if borda else {})}}],
            "visualHeader": [{"properties": {"show": lit("false")}}]}

def vc(nome, x, y, w, h, z, visual):
    return {"$schema": SCHEMA_VC, "name": nome, "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z}, "visual": visual}

def html_visual(medida_nome, css, titulo=None, fundo=True, borda=True, escuro=False, padding=None):
    v = {"visualType": HTMLC, "query": {"queryState": {"content": {"projections": [proj_m(FATO, medida_nome)]}}},
         "objects": {"compatibility": [{"properties": {"legacyRendering": lit("false")}}], "stylesheet": [{"properties": {"stylesheet": s(css)}}]},
         "visualContainerObjects": container(titulo, fundo, borda), "drillFilterOtherVisuals": True}
    if escuro: v["visualContainerObjects"]["background"] = [{"properties": {"show": lit("true"), "color": cor("#191919"), "transparency": lit("0D")}}]
    if padding is not None: v["visualContainerObjects"]["padding"] = [{"properties": {k: lit(f"{padding}D") for k in ("top", "bottom", "left", "right")}}]
    return v

DENEB_CFG = {
  "locale": {"number": {"decimal": ",", "thousands": ".", "grouping": [3], "currency": ["R$ ", ""]},
             "time": {"dateTime": "%A, %e de %B de %Y. %X", "date": "%d/%m/%Y", "time": "%H:%M:%S", "periods": ["AM", "PM"],
                      "days": ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"],
                      "shortDays": ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"],
                      "months": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"],
                      "shortMonths": ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]}},
  "autosize": {"type": "fit", "contains": "padding"}, "background": "transparent", "font": "Segoe UI, Open Sans, sans-serif",
  "view": {"stroke": None},
  "axis": {"labelColor": "#605E5C", "titleColor": "#605E5C", "labelFontSize": 10, "titleFontSize": 10, "titleFontWeight": "normal",
           "gridColor": "#EDEBE9", "domain": False, "tickColor": "#E1DFDD"},
  "axisX": {"grid": False}, "legend": {"labelColor": "#605E5C", "titleColor": "#605E5C", "labelFontSize": 10, "symbolType": "square"},
  "bar": {"cornerRadiusEnd": 0}, "line": {"strokeWidth": 2}}

def deneb_visual(campos, spec, titulo):
    return {"visualType": DENEB, "query": {"queryState": {"dataset": {"projections": campos}}},
            "objects": {"vega": [{"properties": {"jsonSpec": s(json.dumps(spec, ensure_ascii=False, indent=2)),
                                                 "jsonConfig": s(json.dumps(DENEB_CFG, ensure_ascii=False, indent=2)),
                                                 "provider": s("vegaLite"), "renderMode": s("svg"), "enableTooltips": lit("true")}}],
                        "developer": [{"properties": {"locale": s("pt-BR")}}]},
            "visualContainerObjects": container(titulo), "drillFilterOtherVisuals": True}

def run(t, tam, c, b=False): return {"value": t, "textStyle": {"fontSize": f"{tam}pt", "fontWeight": "bold" if b else "normal", "color": c}}

MESES = "['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']"
CORES_RAZAO = {"ENE": "#252423", "CNF": "#605E5C", "REL": "#A19F9D", "PAR": "#967100", "Sem razão": "#E1DFDD"}
NR = "Não realizada (GWh)"; GER = "Geração (GWh)"

# =====================================================================================
# 3. SPECS DENEB
# =====================================================================================
def spec_participacao_razoes():
    medidas = {"Energética (ENE)": "ENE", "Confiabilidade (CNF)": "CNF", "Indisponibilidade externa (REL)": "REL", "Parecer de acesso (PAR)": "PAR", "Sem razão (GWh)": "Sem razão"}
    expr = " : ".join([f"datum.medida == '{k}' ? '{v}'" for k, v in medidas.items()]) + " : 'Outra'"
    return {
      "data": {"name": "dataset"}, "width": "container", "height": "container",
      "transform": [{"fold": list(medidas.keys()), "as": ["medida", "gwh"]},
                    {"calculate": expr, "as": "razao"},
                    {"calculate": "indexof(['ENE','CNF','REL','PAR','Sem razão'], datum.razao)", "as": "ordem"},
                    {"filter": "datum.gwh > 0"}],
      "mark": {"type": "bar", "width": {"band": 0.85}},
      "encoding": {
        "x": {"field": "Mês", "type": "temporal", "timeUnit": "yearmonth", "title": None, "axis": {"format": "%Y", "tickCount": "year", "labelAlign": "left", "labelPadding": 6}},
        "y": {"field": "gwh", "type": "quantitative", "stack": "normalize", "title": None, "axis": {"format": ".0%", "tickCount": 4}},
        "color": {"field": "razao", "type": "nominal", "scale": {"domain": list(CORES_RAZAO), "range": list(CORES_RAZAO.values())},
                  "legend": {"orient": "top", "direction": "horizontal", "title": None}},
        "order": {"field": "ordem"},
        "tooltip": [{"field": "Mês", "type": "temporal", "timeUnit": "yearmonth", "title": "Mês", "format": "%m/%Y"},
                    {"field": "razao", "title": "Razão"}, {"field": "gwh", "title": "GWh", "format": ",.0f"}]}}

def spec_heatmap_mes_ano():
    return {
      "data": {"name": "dataset"}, "width": "container", "height": "container",
      "transform": [{"filter": f"isValid(datum['{NR}'])"},
                    {"calculate": "month(datum['Mês'])", "as": "m"}, {"calculate": f"{MESES}[datum.m]", "as": "mes"},
                    {"calculate": "year(datum['Mês'])", "as": "ano"},
                    {"calculate": f"datum['{NR}'] / (datum['{GER}'] + datum['{NR}'])", "as": "pct"}],
      "encoding": {
        "x": {"field": "mes", "type": "ordinal", "sort": {"field": "m"}, "title": None, "axis": {"labelAngle": 0, "orient": "top", "ticks": False}},
        "y": {"field": "ano", "type": "ordinal", "title": None, "axis": {"ticks": False}}},
      "layer": [
        {"mark": {"type": "rect", "stroke": "#FFFFFF", "strokeWidth": 2},
         "encoding": {"color": {"field": NR, "type": "quantitative", "scale": {"type": "sqrt", "range": ["#FDF8DC", "#F2C811", "#967100", "#191919"]},
                                "legend": {"orient": "bottom", "title": "GWh", "gradientLength": 160, "format": ",.0f"}},
                      "tooltip": [{"field": "mes", "title": "Mês"}, {"field": "ano", "title": "Ano"},
                                  {"field": NR, "title": "Não realizada (GWh)", "format": ",.0f"}, {"field": "pct", "title": "% cortado", "format": ".1%"}]}},
        {"mark": {"type": "text", "fontSize": 9},
         "encoding": {"text": {"field": NR, "format": ",.0f"},
                      "color": {"condition": {"test": f"datum['{NR}'] > 1500", "value": "#FFFFFF"}, "value": "#191919"}}}]}

def spec_perfil_horario():
    return {
      "data": {"name": "dataset"}, "width": "container", "height": "container",
      "transform": [{"filter": "isValid(datum['Não realizada no horário (GWh)'])"},
                    {"joinaggregate": [{"op": "sum", "field": "Não realizada no horário (GWh)", "as": "nr_h"},
                                       {"op": "sum", "field": "Geração no horário (GWh)", "as": "g_h"}], "groupby": ["Hora"]},
                    {"calculate": "datum.nr_h / (datum.g_h + datum.nr_h)", "as": "pct_h"}],
      "encoding": {"x": {"field": "Hora", "type": "ordinal", "title": "Hora do dia", "axis": {"labelAngle": 0, "labelExpr": "datum.value % 3 == 0 ? datum.value + 'h' : ''"}}},
      "layer": [
        {"mark": {"type": "bar", "width": {"band": 0.8}},
         "encoding": {"y": {"field": "Não realizada no horário (GWh)", "type": "quantitative", "aggregate": "sum", "title": "GWh cortados", "axis": {"format": ",.0f", "tickCount": 4}},
                      "color": {"field": "Fonte", "type": "nominal", "scale": {"domain": ["Eólica", "Solar"], "range": ["#252423", "#F2C811"]},
                                "legend": {"orient": "top", "direction": "horizontal", "title": None}},
                      "order": {"field": "Fonte"},
                      "tooltip": [{"field": "Hora", "title": "Hora"}, {"field": "Fonte"},
                                  {"field": "Não realizada no horário (GWh)", "aggregate": "sum", "title": "GWh", "format": ",.0f"}]}},
        {"transform": [{"aggregate": [{"op": "max", "field": "pct_h", "as": "pct"}], "groupby": ["Hora"]}],
         "mark": {"type": "line", "color": "#C84720", "strokeWidth": 2, "point": {"color": "#C84720", "size": 18}},
         "encoding": {"y": {"field": "pct", "type": "quantitative", "title": "% cortado (linha)", "axis": {"format": ".0%", "orient": "right", "titleColor": "#C84720", "tickCount": 4, "grid": False}},
                      "tooltip": [{"field": "Hora", "title": "Hora"}, {"field": "pct", "title": "% cortado no horário", "format": ".1%"}]}}],
      "resolve": {"scale": {"y": "independent"}}}

def spec_calendario(campo_nr=NR):
    return {
      "data": {"name": "dataset"}, "width": "container", "height": "container",
      "transform": [{"filter": f"isValid(datum['{campo_nr}'])"},
                    {"calculate": "time(datum['Data'])", "as": "t"},
                    {"joinaggregate": [{"op": "max", "field": "t", "as": "tmax"}]},
                    {"filter": "datum.t > datum.tmax - 364 * 86400000"},
                    {"joinaggregate": [{"op": "min", "field": "t", "as": "tmin"}]},
                    {"calculate": "floor((datum.t - datum.tmin + day(datum.tmin) * 86400000) / (7 * 86400000))", "as": "semana"},
                    {"calculate": "day(datum['Data'])", "as": "dia_sem"},
                    {"calculate": f"{MESES}[month(datum['Data'])]", "as": "mes"}],
      "layer": [
        {"mark": {"type": "rect", "stroke": "#FFFFFF", "strokeWidth": 1.5},
         "encoding": {
           "x": {"field": "semana", "type": "ordinal", "axis": None},
           "y": {"field": "dia_sem", "type": "ordinal", "title": None,
                 "axis": {"labelExpr": "['dom','seg','ter','qua','qui','sex','sáb'][datum.value]", "ticks": False, "labelFontSize": 9}},
           "color": {"field": campo_nr, "type": "quantitative", "scale": {"type": "sqrt", "range": ["#F6F5F3", "#F2C811", "#967100", "#191919"]},
                     "legend": {"orient": "bottom", "title": "GWh no dia", "gradientLength": 160, "format": ",.1f"}},
           "tooltip": [{"field": "Data", "type": "temporal", "title": "Dia", "format": "%d/%m/%Y"}, {"field": campo_nr, "title": "Não realizada (GWh)", "format": ",.1f"}]}},
        {"transform": [{"filter": "date(datum['Data']) <= 7 && day(datum['Data']) == 0"}],
         "mark": {"type": "text", "align": "left", "baseline": "bottom", "fontSize": 9, "color": "#605E5C", "dy": -2},
         "encoding": {"x": {"field": "semana", "type": "ordinal"}, "y": {"value": 0}, "text": {"field": "mes"}}}]}

def spec_barras_uf():
    return {
      "data": {"name": "dataset"}, "width": "container", "height": "container", "padding": {"right": 96},
      "transform": [{"filter": f"datum['{NR}'] > 0"}],
      "encoding": {"y": {"field": "Estado", "type": "nominal", "sort": {"field": "% cortado", "op": "max", "order": "descending"}, "title": None, "axis": {"ticks": False, "labelLimit": 140}}},
      "layer": [
        {"mark": {"type": "bar", "height": {"band": 0.7}},
         "encoding": {"x": {"field": "% cortado", "type": "quantitative", "title": None, "axis": {"format": ".0%", "tickCount": 4}},
                      "color": {"condition": {"test": "datum['% cortado'] >= 0.2", "value": "#F2C811"}, "value": "#252423"},
                      "tooltip": [{"field": "Estado"}, {"field": "% cortado", "format": ".1%"}, {"field": NR, "title": "Não realizada (GWh)", "format": ",.0f"}]}},
        {"mark": {"type": "text", "align": "left", "dx": 4, "fontSize": 9, "color": "#605E5C"},
         "encoding": {"x": {"field": "% cortado", "type": "quantitative"},
                      "text": {"value": {"expr": f"format(datum['% cortado'], '.1%') + ' · ' + format(datum['{NR}'], ',.0f') + ' GWh'"}}}}]}

def spec_pareto_pontos():
    x = {"field": "Ponto de conexão", "type": "nominal", "sort": {"field": "pos", "op": "min"}, "title": None,
         "axis": {"labelAngle": -40, "labelLimit": 120, "labelFontSize": 9}}
    return {
      "data": {"name": "dataset"}, "width": "container", "height": "container",
      "transform": [{"filter": f"datum['{NR}'] > 0"},
                    {"window": [{"op": "row_number", "as": "pos"}, {"op": "sum", "field": NR, "as": "acum"}], "sort": [{"field": NR, "order": "descending"}]},
                    {"joinaggregate": [{"op": "sum", "field": NR, "as": "tot"}]},
                    {"calculate": "datum.acum / datum.tot", "as": "pct_acum"},
                    {"calculate": "datum.pct_acum - datum['" + NR + "'] / datum.tot < 0.8", "as": "no80"},
                    {"filter": "datum.pos <= 25"}],
      "layer": [
        {"mark": {"type": "bar", "width": {"band": 0.75}},
         "encoding": {"x": x, "y": {"field": NR, "type": "quantitative", "title": "GWh cortados", "axis": {"format": ",.0f", "tickCount": 4}},
                      "color": {"field": "no80", "type": "nominal", "scale": {"domain": [True, False], "range": ["#F2C811", "#C8C6C4"]}, "legend": None},
                      "tooltip": [{"field": "pos", "title": "Posição"}, {"field": "Ponto de conexão"}, {"field": NR, "title": "GWh", "format": ",.0f"},
                                  {"field": "pct_acum", "title": "% acumulado", "format": ".0%"}]}},
        {"layer": [
            {"mark": {"type": "line", "color": "#191919", "strokeWidth": 2, "point": {"color": "#191919", "size": 16}},
             "encoding": {"x": x, "y": {"field": "pct_acum", "type": "quantitative", "title": "% acumulado", "scale": {"domain": [0, 1]},
                                        "axis": {"format": ".0%", "orient": "right", "grid": False, "tickCount": 5}}}},
            {"mark": {"type": "rule", "color": "#C84720", "strokeDash": [4, 3]},
             "encoding": {"y": {"datum": 0.8, "type": "quantitative"}}}]}],
      "resolve": {"scale": {"y": "independent"}}}

def spec_barras_simples(campo, top=None, cor="#252423"):
    t = [{"filter": f"datum['{NR}'] > 0"}]
    if top:
        t += [{"window": [{"op": "row_number", "as": "pos"}], "sort": [{"field": NR, "order": "descending"}]}, {"filter": f"datum.pos <= {top}"}]
    return {
      "data": {"name": "dataset"}, "width": "container", "height": "container", "transform": t, "padding": {"right": 104},
      "encoding": {"y": {"field": campo, "type": "nominal", "sort": {"field": NR, "op": "max", "order": "descending"}, "title": None, "axis": {"ticks": False, "labelLimit": 160, "labelFontSize": 9}}},
      "layer": [
        {"mark": {"type": "bar", "height": {"band": 0.7}, "color": cor},
         "encoding": {"x": {"field": NR, "type": "quantitative", "title": None, "axis": {"format": ",.0f", "tickCount": 3}},
                      "tooltip": [{"field": campo}, {"field": NR, "title": "GWh", "format": ",.0f"}, {"field": "% cortado", "format": ".1%"}]}},
        {"mark": {"type": "text", "align": "left", "dx": 4, "fontSize": 9, "color": "#605E5C"},
         "encoding": {"x": {"field": NR, "type": "quantitative"},
                      "text": {"value": {"expr": f"format(datum['{NR}'], ',.0f') + ' GWh · ' + format(datum['% cortado'], '.1%')"}}}}]}

def spec_dispersao():
    GP, PC, NR_ = "Geração possível (GWh)", "% cortado", NR
    base = [{"filter": f"datum['{GP}'] > 1 && isValid(datum['{PC}'])"},
            {"joinaggregate": [{"op": "median", "field": GP, "as": "mx"}, {"op": "median", "field": PC, "as": "my"}]}]
    def quadrante(teste, rotulo, x, y, alinha, linha_base, cor="#605E5C"):
        # rótulo fixo no canto do quadrante, com a contagem de usinas (camada agregada: não recebe clique)
        t = [{"filter": teste}, {"aggregate": [{"op": "count", "as": "n"}]},
             {"calculate": f"'{rotulo} · ' + datum.n + (datum.n == 1 ? ' usina' : ' usinas')", "as": "txt"}]
        enc = {"text": {"field": "txt"}, "x": {"value": x}, "y": {"value": y}}
        marca = {"type": "text", "align": alinha, "baseline": linha_base, "fontSize": 10, "fontWeight": "bold"}
        # contorno branco por baixo, para o rótulo ficar legível sobre os pontos
        return [{"transform": t, "mark": {**marca, "color": "#FFFFFF", "stroke": "#FFFFFF", "strokeWidth": 4, "strokeJoin": "round"}, "encoding": enc},
                {"transform": t, "mark": {**marca, "color": cor}, "encoding": enc}]
    direita, baixo = {"expr": "width - 4"}, {"expr": "height - 4"}
    return {
      "data": {"name": "dataset"}, "width": "container", "height": "container",
      "transform": base,
      "layer": [
        {"mark": {"type": "rule", "color": "#A19F9D", "strokeDash": [4, 3]}, "encoding": {"x": {"aggregate": "median", "field": GP, "type": "quantitative"}}},
        {"mark": {"type": "rule", "color": "#A19F9D", "strokeDash": [4, 3]}, "encoding": {"y": {"aggregate": "median", "field": PC, "type": "quantitative"}}},
        {"mark": {"type": "circle", "opacity": 0.8, "stroke": "#FFFFFF", "strokeWidth": 0.5},
         "encoding": {
           "x": {"field": GP, "type": "quantitative", "scale": {"type": "log"}, "title": "Porte: geração possível (GWh, escala log)",
                 "axis": {"grid": False, "values": [1, 10, 100, 1000, 10000, 100000], "format": "~s", "tickColor": "#C8C6C4"}},
           "y": {"field": PC, "type": "quantitative", "title": "% cortado", "axis": {"format": ".0%", "tickCount": 4, "gridOpacity": 0.6}},
           "size": {"field": NR_, "type": "quantitative", "scale": {"range": [10, 260]}, "legend": None},
           "color": {"field": "Fonte", "type": "nominal", "scale": {"domain": ["Eólica", "Solar"], "range": ["#252423", "#E0B000"]}, "legend": {"orient": "top", "direction": "horizontal", "title": None}},
           "tooltip": [{"field": "Usina"}, {"field": "Fonte"}, {"field": GP, "title": "Geração possível (GWh)", "format": ",.0f"},
                       {"field": PC, "format": ".1%"}, {"field": NR_, "title": "Não realizada (GWh)", "format": ",.0f"}]}},
        *quadrante(f"datum['{GP}'] >= datum.mx && datum['{PC}'] >= datum.my", "Grandes e muito cortadas", direita, 4, "right", "top", "#967100"),
        *quadrante(f"datum['{GP}'] < datum.mx && datum['{PC}'] >= datum.my", "Pequenas e muito cortadas", 4, 4, "left", "top"),
        *quadrante(f"datum['{GP}'] >= datum.mx && datum['{PC}'] < datum.my", "Grandes e pouco cortadas", direita, baixo, "right", "bottom"),
        *quadrante(f"datum['{GP}'] < datum.mx && datum['{PC}'] < datum.my", "Pequenas e pouco cortadas", 4, baixo, "left", "bottom")]}

def spec_mensal_usina():
    return {
      "data": {"name": "dataset"}, "width": "container", "height": "container",
      "transform": [{"filter": f"isValid(datum['{NR}']) || isValid(datum['{GER}'])"},
                    {"calculate": f"(datum['{NR}'] || 0) / ((datum['{GER}'] || 0) + (datum['{NR}'] || 0))", "as": "pct"}],
      "encoding": {"x": {"field": "Mês", "type": "temporal", "timeUnit": "yearmonth", "title": None, "axis": {"format": "%Y", "tickCount": "year", "labelAlign": "left", "labelPadding": 6}}},
      "layer": [
        {"mark": {"type": "bar", "color": "#252423", "width": {"band": 0.75}},
         "encoding": {"y": {"field": NR, "type": "quantitative", "title": "GWh cortados (barras)", "axis": {"format": ",.0f", "tickCount": 4}},
                      "tooltip": [{"field": "Mês", "type": "temporal", "timeUnit": "yearmonth", "title": "Mês", "format": "%m/%Y"},
                                  {"field": NR, "title": "Não realizada (GWh)", "format": ",.1f"}, {"field": "pct", "title": "% cortado", "format": ".1%"}]}},
        {"mark": {"type": "line", "color": "#E0B000", "strokeWidth": 2, "interpolate": "monotone"},
         "encoding": {"y": {"field": "pct", "type": "quantitative", "title": "% cortado (linha)", "axis": {"format": ".0%", "orient": "right", "grid": False, "tickCount": 4, "titleColor": "#967100"}}}}],
      "resolve": {"scale": {"y": "independent"}}}

def spec_razao_origem_base():
    mapa = {"Energética (ENE)": "ENE", "Confiabilidade (CNF)": "CNF", "Indisponibilidade externa (REL)": "REL", "Parecer de acesso (PAR)": "PAR",
            "Sem razão (GWh)": "Sem razão", "Origem local (GWh)": "Local", "Origem sistêmica (GWh)": "Sistêmica", "Sem origem (GWh)": "Sem origem"}
    cats = list(mapa.values())
    expr = " : ".join([f"datum.medida == '{k}' ? '{v}'" for k, v in mapa.items()]) + " : ''"
    return {
      "data": {"name": "dataset"}, "width": "container", "height": "container",
      "transform": [
        {"fold": list(mapa.keys()), "as": ["medida", "gwh"]},
        {"calculate": expr, "as": "cat"},
        {"calculate": "indexof(['Local','Sistêmica','Sem origem'], datum.cat) >= 0 ? 'Origem' : 'Razão'", "as": "grupo"},
        {"calculate": f"indexof({json.dumps(cats, ensure_ascii=False)}, datum.cat)", "as": "ordem"},
        {"calculate": "datum.gwh || 0", "as": "gwh"},
        {"joinaggregate": [{"op": "sum", "field": "gwh", "as": "tot"}], "groupby": ["grupo"]},
        {"calculate": "datum.tot > 0 ? datum.gwh / datum.tot : 0", "as": "pct"},
        {"window": [{"op": "sum", "field": "pct", "as": "fim"}], "groupby": ["grupo"], "sort": [{"field": "ordem"}], "frame": [None, 0]},
        {"calculate": "datum.fim - datum.pct", "as": "ini"}, {"calculate": "datum.fim - datum.pct / 2", "as": "meio"}],
      "encoding": {"y": {"field": "grupo", "type": "nominal", "title": None, "sort": ["Razão", "Origem"], "axis": {"labelFontSize": 11, "labelColor": "#191919", "labelFontWeight": "bold", "ticks": False}}},
      "layer": [
        {"mark": {"type": "bar", "height": {"band": 0.62}},
         "encoding": {"x": {"field": "ini", "type": "quantitative", "axis": None, "scale": {"domain": [0, 1]}}, "x2": {"field": "fim"},
                      "color": {"field": "cat", "type": "nominal", "scale": {"domain": cats, "range": ["#252423", "#605E5C", "#A19F9D", "#967100", "#E1DFDD", "#F2C811", "#191919", "#E1DFDD"]},
                                "legend": {"orient": "bottom", "columns": 4, "title": None, "labelFontSize": 9, "symbolSize": 60, "columnPadding": 8}},
                      "tooltip": [{"field": "grupo", "title": "Grupo"}, {"field": "cat", "title": "Categoria"}, {"field": "gwh", "title": "GWh", "format": ",.1f"}, {"field": "pct", "title": "Participação", "format": ".1%"}]}},
        {"transform": [{"filter": "datum.pct >= 0.07"}],
         "mark": {"type": "text", "fontSize": 10, "fontWeight": "bold", "align": "center"},
         "encoding": {"x": {"field": "meio", "type": "quantitative"}, "text": {"field": "pct", "format": ".0%"},
                      "color": {"condition": {"test": "indexof(['ENE','CNF','Sistêmica','PAR'], datum.cat) >= 0", "value": "#FFFFFF"}, "value": "#191919"}}}]}

# =====================================================================================
# 4. PÁGINAS
# =====================================================================================
CSS_BASE = "*{font-family:'Segoe UI',sans-serif}.vazio{font-size:13px;color:#8A8886}"
CSS_CONC = CSS_BASE + """.tit{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#F2C811;font-weight:700;margin-bottom:10px}
.st{display:flex;align-items:baseline;gap:10px;margin-bottom:10px}
.n{font-size:30px;font-weight:600;color:#FFFFFF;line-height:1;min-width:92px}.n span{font-size:13px;font-weight:400;color:#C8C6C4}
.d{font-size:12px;color:#E1DFDD;line-height:1.3}
.top{font-size:12px;color:#C8C6C4;border-top:1px solid #3C3C41;padding-top:8px}.top b{color:#FFFFFF}"""
CSS_RANK = CSS_BASE + """.lin{display:grid;grid-template-columns:26px 1fr 130px 70px 124px;gap:8px;align-items:center;padding:5px 6px;border-bottom:1px solid #EDEBE9;cursor:pointer}
.lin:hover{background:#F6F5F3}
.cab{cursor:default;font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:#8A8886;font-weight:600;padding-top:0;border-bottom:1px solid #E1DFDD}
.cab:hover{background:none}
.dir{text-align:right}.r{font-size:16px;font-weight:600;color:#C8C6C4}
.top .r{color:#967100}
.nm{font-size:12px;font-weight:600;color:#191919}.mt{font-size:10px;color:#8A8886;margin-top:1px}
.vl{font-size:12px;font-weight:600;color:#191919}.pc{font-size:12px;color:#605E5C}
.bar{height:4px;background:#EDEBE9;margin-top:4px;width:110px;margin-left:auto}.bar span{display:block;height:4px;background:#F2C811}"""
CSS_USINA = CSS_BASE + """.wrap{display:flex;gap:16px;align-items:stretch}
.cab{flex:1.25;background:#191919;padding:14px 18px;border-top:3px solid #F2C811}
.k{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:#F2C811;font-weight:700}
.nm{font-size:22px;font-weight:600;color:#FFFFFF;margin:4px 0 8px 0}
.at{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:11px;color:#C8C6C4}.at b{color:#FFFFFF;font-weight:600;margin-right:4px}
.kp{flex:2;display:flex;gap:10px}
.c{flex:1;background:#FFFFFF;border:1px solid #E1DFDD;border-top:3px solid #191919;padding:10px 12px}
.r{font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#605E5C}
.v{font-size:24px;font-weight:600;color:#191919;margin-top:6px}.v small{font-size:12px;color:#605E5C;font-weight:400}.v.t{font-size:14px;line-height:1.25}"""

def titulo_textbox(kicker, titulo, sub, largura=600):
    return vc("titulo", 24, 8, largura, 70, 1000, {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": [
        {"textRuns": [run(kicker, 9, "#967100", True)]}, {"textRuns": [run(titulo, 16, "#191919", True)]}, {"textRuns": [run(sub, 9, "#605E5C")]}]}}]},
        "visualContainerObjects": {**container(None, False, False), "padding": zpad()}, "drillFilterOtherVisuals": True})

def ranking_visual():
    """HTML Content com uma linha por usina: a usina no papel Contexto (sampling) permite o filtro cruzado."""
    v = html_visual("html · Linha ranking", CSS_RANK, "As 10 usinas e conjuntos com mais geração não realizada · clique para filtrar", padding=12)
    valor = proj_m(FATO, "Ranking · valor")
    v["query"]["queryState"]["sampling"] = {"projections": [proj_c("Usinas", "ID da usina")]}
    v["query"]["queryState"]["tooltips"] = {"projections": [valor]}
    v["query"]["sortDefinition"] = {"sort": [{"field": valor["field"], "direction": "Descending"}], "isDefaultSort": True}
    v["objects"]["crossFilter"] = [{"properties": {"enabled": lit("true")}}]
    v["objects"]["contentFormatting"] = [{"properties": {"noDataMessage": s("Sem geração não realizada nos filtros selecionados.")}}]
    return v

FILTROS = {n: jload(os.path.join(RP, "pages", "visao_geral", "visuals", n, "visual.json")) for n in ("filtro_fonte", "filtro_uf", "filtro_ano")}
for _f in FILTROS.values():  # a gaveta move os filtros para um grupo; a cópia começa sem grupo e na posição do cabeçalho
    _f.pop("parentGroupName", None); _f["visual"].pop("syncGroup", None)

def nova_pagina(nome, exibicao, visuais, filtros_extra=None):
    pg = os.path.join(RP, "pages", nome)
    vis = os.path.join(pg, "visuals")
    os.makedirs(vis, exist_ok=True)
    for n in os.listdir(vis):  # recria tudo, menos o tour (regerado pelo script do tour)
        if not n.startswith("tour_"): shutil.rmtree(os.path.join(vis, n))
    jdump({"$schema": SCHEMA_PG, "name": nome, "displayName": exibicao, "displayOption": "FitToPage", "height": 720, "width": 1280}, os.path.join(pg, "page.json"))
    for n, f in FILTROS.items():
        f = json.loads(json.dumps(f)); f["name"] = n
        os.makedirs(os.path.join(vis, n), exist_ok=True); jdump(f, os.path.join(vis, n, "visual.json"))
    for v in visuais + (filtros_extra or []):
        os.makedirs(os.path.join(vis, v["name"]), exist_ok=True); jdump(v, os.path.join(vis, v["name"], "visual.json"))

F = lambda e, n: proj_c(e, n)
Mf = lambda n: proj_m(FATO, n)

# --- Razões e sazonalidade
nova_pagina("razoes_sazonalidade", "Razões e sazonalidade", [
    titulo_textbox("RAZÕES E SAZONALIDADE", "Por que e quando o corte acontece", "Razão informada pelo ONS, meses do ano, horas do dia e dias recentes"),
    vc("participacao", 24, 84, 620, 300, 2000, deneb_visual([F("Calendário", "Mês")] + [Mf(x) for x in ("Energética (ENE)", "Confiabilidade (CNF)", "Indisponibilidade externa (REL)", "Parecer de acesso (PAR)", "Sem razão (GWh)")],
                                                         spec_participacao_razoes(), "Participação de cada razão no corte, por mês")),
    vc("heatmap", 656, 84, 600, 300, 3000, deneb_visual([F("Calendário", "Mês"), Mf(NR), Mf(GER)], spec_heatmap_mes_ano(), "Geração não realizada por mês do ano (GWh)")),
    vc("perfil", 24, 396, 620, 304, 4000, deneb_visual([F("Perfil horário", "Hora"), F("Fontes", "Fonte"), proj_m("Perfil horário", "Não realizada no horário (GWh)"), proj_m("Perfil horário", "Geração no horário (GWh)")],
                                                    spec_perfil_horario(), "Em que hora do dia o corte acontece")),
    vc("calendario", 656, 396, 600, 304, 5000, deneb_visual([F("Calendário", "Data"), Mf(NR)], spec_calendario(), "Corte dia a dia nos últimos 12 meses com dados")),
])

# --- Rede e território (reaproveita a página estados_usinas)
nova_pagina("estados_usinas", "Rede e território", [
    titulo_textbox("REDE E TERRITÓRIO", "Onde o corte se concentra", "Estados, pontos de conexão à rede e subsistemas"),
    vc("uf", 24, 84, 440, 616, 2000, deneb_visual([F("Estados", "Estado"), Mf("% cortado"), Mf(NR)], spec_barras_uf(), "% da geração possível cortada, por estado")),
    vc("pareto", 476, 84, 780, 400, 3000, deneb_visual([F("Usinas", "Ponto de conexão"), Mf(NR)], spec_pareto_pontos(), "Pontos de conexão com mais corte (Pareto, 25 maiores)")),
    vc("concentracao", 476, 496, 380, 204, 4000, html_visual("html · Concentração", CSS_CONC, fundo=False, borda=False, escuro=True, padding=16)),
    vc("subsistema", 868, 496, 388, 204, 5000, deneb_visual([F("Usinas", "Subsistema"), Mf(NR), Mf("% cortado")], spec_barras_simples("Subsistema"), "Corte por subsistema")),
])

# --- Usinas e agentes
nova_pagina("usinas_agentes", "Usinas e agentes", [
    titulo_textbox("USINAS E AGENTES", "Quem mais perde geração", "Ranking, porte das usinas e agentes operadores"),
    vc("ranking", 24, 84, 700, 616, 2000, ranking_visual()),
    vc("dispersao", 736, 84, 520, 360, 3000, deneb_visual([F("Usinas", "ID da usina"), F("Usinas", "Usina"), F("Usinas", "Fonte"), Mf("Geração possível (GWh)"), Mf("% cortado"), Mf(NR)],
                                                       spec_dispersao(), "Porte x % cortado, por usina")),
    vc("agentes", 736, 456, 520, 244, 4000, deneb_visual([F("Usinas", "Agente operador"), Mf(NR), Mf("% cortado")], spec_barras_simples("Agente operador", top=10), "Agentes operadores com mais corte (10 maiores)")),
])

# --- Detalhe da usina
filtro_usina = json.loads(json.dumps(FILTROS["filtro_uf"]))
filtro_usina["name"] = "filtro_usina"
filtro_usina["position"].update({"x": 476, "y": 12, "width": 150, "height": 60, "z": 1400, "tabOrder": 1400})
q = filtro_usina["visual"]["query"]["queryState"]["Values"]["projections"][0]
q["field"]["Column"]["Expression"]["SourceRef"]["Entity"] = "Usinas"; q["field"]["Column"]["Property"] = "Usina"
q["queryRef"] = "Usinas.Usina"; q["nativeQueryRef"] = "Usina"
filtro_usina["visual"]["objects"]["header"] = [{"properties": {"text": s("Usina")}}]
nova_pagina("detalhe_usina", "Detalhe da usina", [
    titulo_textbox("DETALHE DA USINA", "Ficha de uma usina ou conjunto", "Escolha a usina em Filtros · cadastro atual do ONS", largura=440),
    vc("ficha", 24, 84, 1232, 104, 2000, html_visual("html · Usina", CSS_USINA, fundo=False, borda=False, padding=0)),
    vc("mensal", 24, 200, 760, 500, 3000, deneb_visual([F("Calendário", "Mês"), Mf(NR), Mf(GER)], spec_mensal_usina(), "Geração não realizada e % cortado por mês")),
    vc("razao_origem", 796, 200, 460, 212, 4000, deneb_visual([Mf(x) for x in ("Energética (ENE)", "Confiabilidade (CNF)", "Indisponibilidade externa (REL)", "Parecer de acesso (PAR)",
                                                                                "Sem razão (GWh)", "Origem local (GWh)", "Origem sistêmica (GWh)", "Sem origem (GWh)")],
                                                                spec_razao_origem_base(), "Razão e origem do corte")),
    vc("calendario", 796, 424, 460, 276, 5000, deneb_visual([F("Calendário", "Data"), Mf(NR)], spec_calendario(), "Corte dia a dia nos últimos 12 meses com dados")),
], filtros_extra=[filtro_usina])

# ordem das páginas
pj = os.path.join(RP, "pages", "pages.json"); pages = jload(pj)
pages["pageOrder"] = ["visao_geral", "razoes_sazonalidade", "estados_usinas", "usinas_agentes", "detalhe_usina"]
pages["activePageName"] = "visao_geral"
jdump(pages, pj)
print("ok: 4 páginas de análise")
