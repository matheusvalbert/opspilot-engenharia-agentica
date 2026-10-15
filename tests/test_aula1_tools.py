"""Testes OFFLINE das ferramentas (não chamam o LLM; rodam no CI sem chave).

Ferramentas são código comum: devem ter testes comuns. Repare que testamos
inclusive o caminho de ERRO — é ele que permite a autocorreção do agente.
"""

import json
from datetime import datetime, timedelta, timezone

from opspilot import tools


def test_consultar_metricas_servico_valido():
    saida = json.loads(tools.consultar_metricas.invoke({"servico": "pagamentos-db"}))
    assert saida["conexoes_max_pool"] == 10
    assert saida["baseline_conexoes_max_pool"] == 50


def test_consultar_metricas_erro_vira_observacao():
    saida = tools.consultar_metricas.invoke({"servico": "checkout"})
    assert saida.startswith("ERRO")
    assert "checkout-api" in saida  # lista os nomes válidos para o agente se corrigir


def test_ler_logs_com_filtro():
    saida = tools.ler_logs.invoke({"servico": "pagamentos-db", "filtro": "pool_size"})
    assert "default_pool_size=10" in saida


def test_ler_logs_limita_linhas():
    saida = tools.ler_logs.invoke({"servico": "checkout-api", "max_linhas": 3})
    assert len(saida.splitlines()) == 3


def test_listar_deploys_varre_logs_e_ordena_por_horario(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "DIR_LOGS", tmp_path)
    agora = datetime.now(timezone.utc)
    mais_antigo = (agora - timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    mais_novo = (agora - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fora_da_janela = (agora - timedelta(hours=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "auth.log").write_text(f"{mais_novo} INFO deploy auth v2\n", encoding="utf-8")
    (tmp_path / "checkout.log").write_text(
        f"{fora_da_janela} INFO deploy antigo\n{mais_antigo} INFO deploy checkout v1\n",
        encoding="utf-8",
    )

    saida = tools.listar_deploys.invoke({"horas": 6})

    assert saida.splitlines() == [
        f"{mais_antigo} INFO deploy checkout v1",
        f"{mais_novo} INFO deploy auth v2",
    ]


def test_listar_deploys_rejeita_janela_nao_positiva():
    assert tools.listar_deploys.invoke({"horas": 0}).startswith("ERRO:")


def test_buscar_runbook_encontra_pool():
    saida = tools.buscar_runbook.invoke({"consulta": "pool de conexões esgotado"})
    assert "banco-conexoes-esgotadas.md" in saida


def test_abrir_ticket_grava_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "DIR_TICKETS", tmp_path)
    saida = tools.abrir_ticket.invoke(
        {"titulo": "Teste", "servico": "pagamentos-db", "severidade": "SEV2", "resumo": "teste"}
    )
    assert "aberto" in saida
    assert len(list(tmp_path.glob("OPS-*.json"))) == 1


def test_schema_da_ferramenta_tem_descricao():
    """O LLM só usa bem o que entende: docstring e parâmetros precisam chegar no schema."""
    schema = tools.consultar_metricas.args
    assert "servico" in schema
    assert "métricas" in tools.consultar_metricas.description.lower()
    assert "horas" in tools.listar_deploys.args
    assert tools.listar_deploys in tools.TODAS_FERRAMENTAS
