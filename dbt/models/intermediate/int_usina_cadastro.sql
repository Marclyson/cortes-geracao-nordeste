-- Cadastro atual de cada usina: os atributos do registro mais recente. Alimenta o snapshot
-- snap_usina, que guarda o histórico das mudanças a cada execução.
select distinct on (usina_id)
    usina_id,
    fonte,
    usina_nome,
    ceg,
    uf,
    estado,
    subsistema_id,
    subsistema,
    ponto_conexao_id,
    ponto_conexao,
    agente_operador
from {{ ref('int_restricao_semihoraria') }}
order by usina_id, instante desc
