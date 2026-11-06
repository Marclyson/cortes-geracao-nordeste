{# Falha para cada valor fora do intervalo [minimo, maximo]. Nulos passam. #}
{% test entre(model, column_name, minimo, maximo) %}
select {{ column_name }}
from {{ model }}
where {{ column_name }} not between {{ minimo }} and {{ maximo }}
{% endtest %}
