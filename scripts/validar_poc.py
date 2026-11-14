"""
Script de validação e geração do resumo de indicadores da Prova de Conceito (PoC).

Este script:
1. Verifica a configuração técnica do fluxo n8n, a estrutura do script SQL
   e executa varredura de segredos/tokens em todo o repositório.
2. Valida o conjunto de N = 100 chamados sintéticos (`data/chamados_sinteticos_100.json`)
   e seus gabaritos (`data/gabarito_classificacao_100.csv`).
3. Audita os 100 logs individuais exportados do n8n (`evidencias/logs_execucao_n8n_100.json`)
   com chamadas reais ao Gemini (`models/gemini-3.5-flash-lite`), saída estruturada JSON,
   respostas reais `httpbin.org/post` (HTTP 200) e gravações reais no Supabase, recalculando
   diretamente dos logs todos os indicadores (80/80, 99/100, 83/17 e latências por nó).
4. Valida a paridade 100% entre os 100 registros em `evidencias/resultados_execucao_100.json`,
   `evidencias/resultados_execucao_100.csv`, `evidencias/logs_execucao_n8n_100.json`
   e o snapshot SQL em `database/schema.sql` (executado em SQLite em memória).
5. Executa testes HTTP POST controlados via Python contra `https://httpbin.org/post`
   para Análise de Valor-Limite exata do limiar (0.84, 0.85, 0.86 e crítico 0.92),
   registrando-os separadamente em `evidencias/testes_valor_limite_httpbin.json`.
6. Regenera o relatório consolidado `evidencias/resumo_indicadores.md`.
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
import statistics
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = ROOT_DIR / "n8n-workflows" / "triagem-chamados-workflow.json"
SCHEMA_PATH = ROOT_DIR / "database" / "schema.sql"
DATA_DIR = ROOT_DIR / "data"
EVIDENCIAS_DIR = ROOT_DIR / "evidencias"

BOUNDARY_CASES = [
    (2001, "Cenário padronizado N1 (referência)", 0.95, False, "Automatico"),
    (2080, "Caso A — Acima do limiar (confianca = 0.86)", 0.86, False, "Automatico"),
    (2081, "Caso B — No limiar exato (confianca = 0.85)", 0.85, False, "Automatico"),
    (2084, "Caso C — Abaixo do limiar (confianca = 0.84)", 0.84, True, "Revisao Humana"),
    (
        2085,
        "Caso D — Crítico com confiança alta (0.92 + revisão obrigatória)",
        0.92,
        True,
        "Revisao Humana",
    ),
]


def verify_workflow_and_secrets() -> dict[str, Any]:
    wf_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    workflow = json.loads(wf_text)
    nodes = {node["name"]: node for node in workflow["nodes"]}
    settings = workflow.get("settings", {})

    gemini_node = nodes["Google Gemini Chat Model"]
    agent_node = nodes["Agente Cognitivo LLM (Parsing)"]
    if_node = nodes["Verifica Confianca (Score >= 0.85)"]
    parser_node = nodes["Structured Output Parser"]
    http_auto = nodes["Atualiza Chamado no GLPI (API)"]
    http_human = nodes["Desvio para Fila Humana (Human-in-the-Loop)"]
    supabase_node = nodes["Registra Auditoria no Supabase"]

    tempo_expr = next(
        fv["fieldValue"]
        for fv in supabase_node["parameters"]["fieldsUi"]["fieldValues"]
        if fv["fieldId"] == "tempo_processamento_ms"
    )
    assert "1900" not in wf_text, "Fallback artificial 1900 ainda presente no workflow"
    assert "timestamp_inicio_ms" in tempo_expr and "Date.now()" in tempo_expr
    assert settings.get("saveDataSuccessExecution") == "all"
    assert settings.get("saveDataErrorExecution") == "all"
    assert settings.get("saveManualExecutions") is True

    secret_patterns = [
        r"AIza[0-9A-Za-z\-_]{20,}",
        r"AQ\.Ab8[0-9A-Za-z\-_]{20,}",
        r"eyJ[A-Za-z0-9\-_]{20,}\.[A-Za-z0-9\-_]{20,}",
        r"sk-[A-Za-z0-9]{20,}",
        r"sb_secret_[0-9A-Za-z\-_]{10,}",
        r"sb_publishable_[0-9A-Za-z\-_]{10,}",
    ]
    scan_paths = [
        WORKFLOW_PATH,
        SCHEMA_PATH,
        ROOT_DIR / "README.md",
        ROOT_DIR / "database" / "README.md",
        ROOT_DIR / "prompts" / "system-prompt-ia.md",
        *DATA_DIR.glob("*"),
        *EVIDENCIAS_DIR.glob("*"),
    ]
    leaks = []
    for path in scan_paths:
        if not path.is_file():
            continue
        txt = path.read_text(encoding="utf-8", errors="ignore")
        for pat in secret_patterns:
            if re.search(pat, txt):
                leaks.append(f"{path.relative_to(ROOT_DIR)} ({pat})")
    assert not leaks, f"Possível token/chave encontrado em: {leaks}"

    sql_text = SCHEMA_PATH.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS chamados_triagem" in sql_text
    assert "CREATE INDEX IF NOT EXISTS idx_chamados_triagem_status" in sql_text

    return {
        "workflow_id": workflow.get("id"),
        "workflow_name": workflow["name"],
        "node_count": len(workflow["nodes"]),
        "gemini_model": gemini_node["parameters"]["modelName"],
        "temperature": gemini_node["parameters"]["options"]["temperature"],
        "parser_type": parser_node["type"],
        "system_message": agent_node["parameters"]["options"]["systemMessage"],
        "if_threshold": if_node["parameters"]["conditions"]["number"][0]["value2"],
        "tempo_expr": tempo_expr,
        "http_auto_url": http_auto["parameters"]["url"],
        "http_human_url": http_human["parameters"]["url"],
        "save_success": settings.get("saveDataSuccessExecution"),
        "save_error": settings.get("saveDataErrorExecution"),
        "save_manual": settings.get("saveManualExecutions"),
        "secret_scan_clean": True,
    }


def load_and_verify_dataset() -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    tickets = json.loads((DATA_DIR / "chamados_sinteticos_100.json").read_text(encoding="utf-8"))
    with (DATA_DIR / "gabarito_classificacao_100.csv").open("r", encoding="utf-8-sig") as f:
        gabarito_rows = list(csv.DictReader(f))

    assert len(tickets) == 100
    assert len(gabarito_rows) == 100

    by_id = {int(t["ticket_id"]): t for t in tickets}
    assert set(by_id.keys()) == set(range(2001, 2101))

    for g in gabarito_rows:
        tid = int(g["ticket_id"])
        t = by_id[tid]
        assert t["categoria_gabarito"] == g["categoria_gabarito"]
        assert t["intencao_gabarito"] == g["intencao_gabarito"]
        assert t["roteamento_esperado"] == g["roteamento_esperado"]
        assert t["tipo_cenario"] == g["tipo_cenario"]

    assert sum(1 for t in tickets if t["tipo_cenario"] == "Padronizado") == 80
    assert sum(1 for t in tickets if t["tipo_cenario"] == "Ambiguo_Critico") == 20
    for cat in ("Hardware", "Software", "Redes", "Acessos"):
        assert sum(1 for t in tickets if t["categoria_gabarito"] == cat) == 25
        assert (
            sum(
                1
                for t in tickets
                if t["tipo_cenario"] == "Padronizado" and t["categoria_gabarito"] == cat
            )
            == 20
        )

    return tickets, by_id


def load_and_verify_n8n_and_supabase(
    tickets_by_id: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    logs_doc = json.loads(
        (EVIDENCIAS_DIR / "logs_execucao_n8n_100.json").read_text(encoding="utf-8")
    )
    results = json.loads(
        (EVIDENCIAS_DIR / "resultados_execucao_100.json").read_text(encoding="utf-8")
    )
    with (EVIDENCIAS_DIR / "resultados_execucao_100.csv").open("r", encoding="utf-8-sig") as f:
        csv_rows = list(csv.DictReader(f))

    execucoes = logs_doc["execucoes"]
    assert len(execucoes) == 100
    assert len(results) == 100
    assert len(csv_rows) == 100

    exec_by_ticket = {int(e["glpi_ticket_id"]): e for e in execucoes}
    res_by_ticket = {int(r["glpi_ticket_id"]): r for r in results}
    csv_by_ticket = {int(c["glpi_ticket_id"]): c for c in csv_rows}
    expected_ids = set(range(2001, 2101))
    assert set(exec_by_ticket.keys()) == expected_ids
    assert set(res_by_ticket.keys()) == expected_ids
    assert set(csv_by_ticket.keys()) == expected_ids

    for tid in range(2001, 2101):
        ev = exec_by_ticket[tid]
        res = res_by_ticket[tid]
        csv_r = csv_by_ticket[tid]
        t = tickets_by_id[tid]

        assert ev["status"] == "success" and ev["finished"] is True
        traces = ev["node_traces"]
        assert traces["Webhook GLPI (Novo Chamado)"]["input_body"]["ticket_id"] == tid
        gem = traces["Google Gemini Chat Model"]
        assert gem["executionStatus"] == "success"
        assert gem["generationInfo"]["finishReason"] == "STOP"
        assert gem["tokenUsage"]["totalTokens"] > 0

        parsed = traces["Structured Output Parser"]["parsed_output"]
        assert parsed == traces["Agente Cognitivo LLM (Parsing)"]["output"]

        conf = float(parsed["confianca"])
        rev_flag = bool(parsed["requer_revisao_humana"])
        auto_expected = (conf >= 0.85) and (not rev_flag)
        expected_status = "Automatico" if auto_expected else "Revisao Humana"

        http_node_name = (
            "Atualiza Chamado no GLPI (API)"
            if auto_expected
            else "Desvio para Fila Humana (Human-in-the-Loop)"
        )
        http_trace = traces[http_node_name]
        assert http_trace["executionStatus"] == "success"
        assert http_trace["url"] == "https://httpbin.org/post"
        assert http_trace["httpbin_status"] == 200
        assert str(http_trace["httpbin_echo_json"]["ticket_id"]) == str(tid)

        sb_trace = traces["Registra Auditoria no Supabase"]
        assert sb_trace["executionStatus"] == "success"
        assert sb_trace["supabase_record_id"] == res["supabase_id"]
        assert int(sb_trace["tempo_processamento_ms"]) == int(res["tempo_processamento_ms"])
        assert int(res["n8n_execution_id"]) == int(ev["n8n_execution_id"])

        assert res["conteudo_original"] == t["conteudo_original"]
        assert res["categoria_sugerida"] == parsed["categoria_glpi"]
        assert res["intencao_classificada"] == parsed["intencao"]
        assert res["nivel_urgencia"] == parsed["urgencia"]
        assert abs(float(res["confianca_ia"]) - conf) < 1e-6
        assert res["status_processamento"] == expected_status
        assert res["requer_revisao_humana"] == (not auto_expected)
        assert res["acerto_categoria"] == (res["categoria_sugerida"] == t["categoria_gabarito"])
        assert res["acerto_intencao"] == (res["intencao_classificada"] == t["intencao_gabarito"])
        assert res["acerto_roteamento"] == (res["status_processamento"] == t["roteamento_esperado"])

        assert csv_r["supabase_id"] == res["supabase_id"]
        assert int(csv_r["n8n_execution_id"]) == int(res["n8n_execution_id"])
        assert csv_r["categoria_sugerida"] == res["categoria_sugerida"]
        assert csv_r["intencao_classificada"] == res["intencao_classificada"]
        assert csv_r["nivel_urgencia"] == res["nivel_urgencia"]
        assert abs(float(csv_r["confianca_ia"]) - float(res["confianca_ia"])) < 1e-6
        assert csv_r["status_processamento"] == res["status_processamento"]
        assert csv_r["requer_revisao_humana"] == str(res["requer_revisao_humana"])
        assert int(csv_r["tempo_processamento_ms"]) == int(res["tempo_processamento_ms"])
        assert csv_r["acerto_categoria"] == str(res["acerto_categoria"])
        assert csv_r["acerto_intencao"] == str(res["acerto_intencao"])
        assert csv_r["acerto_roteamento"] == str(res["acerto_roteamento"])

    return logs_doc, execucoes, results


def verify_sql_parity(results: list[dict[str, Any]]) -> None:
    """Valida em SQLite em memória que database/schema.sql contém os 100 registros reais."""
    sql_text = SCHEMA_PATH.read_text(encoding="utf-8")
    m = re.search(
        r"(INSERT INTO chamados_triagem\s*\(.*?\)\s*VALUES\s*.*?);",
        sql_text,
        re.S,
    )
    assert m, "Bloco INSERT INTO chamados_triagem ... VALUES não encontrado em database/schema.sql"

    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE chamados_triagem (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            glpi_ticket_id INTEGER,
            remetente_email TEXT NOT NULL,
            conteudo_original TEXT NOT NULL,
            intencao_classificada TEXT NOT NULL,
            nivel_urgencia TEXT NOT NULL,
            categoria_sugerida TEXT,
            confianca_ia REAL NOT NULL,
            status_processamento TEXT NOT NULL,
            resposta_sugerida TEXT,
            requer_revisao_humana INTEGER DEFAULT 0,
            tempo_processamento_ms INTEGER
        );
        """
    )
    conn.execute(m.group(1))
    rows = conn.execute(
        "SELECT id, created_at, glpi_ticket_id, remetente_email, conteudo_original, "
        "intencao_classificada, nivel_urgencia, categoria_sugerida, confianca_ia, "
        "status_processamento, resposta_sugerida, requer_revisao_humana, tempo_processamento_ms "
        "FROM chamados_triagem ORDER BY glpi_ticket_id"
    ).fetchall()
    conn.close()

    expected = sorted(results, key=lambda r: int(r["glpi_ticket_id"]))
    assert len(rows) == len(expected) == 100

    for row, rec in zip(rows, expected):
        assert row[0] == rec["supabase_id"]
        assert row[1] == rec["created_at"]
        assert row[2] == rec["glpi_ticket_id"]
        assert row[3] == rec["remetente_email"]
        assert row[4] == rec["conteudo_original"]
        assert row[5] == rec["intencao_classificada"]
        assert row[6] == rec["nivel_urgencia"]
        assert row[7] == rec["categoria_sugerida"]
        assert abs(float(row[8]) - float(rec["confianca_ia"])) < 1e-6
        assert row[9] == rec["status_processamento"]
        assert row[10] == rec["resposta_sugerida"]
        assert bool(row[11]) == bool(rec["requer_revisao_humana"])
        assert int(row[12]) == int(rec["tempo_processamento_ms"])


def run_httpbin_boundary_tests(
    tickets_by_id: dict[int, dict[str, Any]],
    results_by_id: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    results = []
    for tid, desc_caso, conf_teste, rev_teste, expected_status in BOUNDARY_CASES:
        t = tickets_by_id[tid]
        real_rec = results_by_id[tid]

        cond_boolean = rev_teste is False
        cond_number = conf_teste >= 0.85
        routed_auto = cond_boolean and cond_number
        status_eval = "Automatico" if routed_auto else "Revisao Humana"
        assert status_eval == expected_status

        if routed_auto:
            branch = "Atualiza Chamado no GLPI (API)"
            payload = {
                "ticket_id": str(tid),
                "status": "Triado Automaticamente",
                "categoria": real_rec["categoria_sugerida"],
                "confianca": conf_teste,
            }
        else:
            branch = "Desvio para Fila Humana (Human-in-the-Loop)"
            alerta = (
                "Score de confianca inferior ao limiar de 0.85"
                if conf_teste < 0.85
                else "Revisao humana obrigatoria por alta criticidade ou ambiguidade"
            )
            payload = {
                "ticket_id": str(tid),
                "status": "Aguardando Revisao Humana",
                "alerta": alerta,
            }

        req = urllib.request.Request(
            "https://httpbin.org/post",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "tcc-poc-validator/2.0"},
            method="POST",
        )
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
                body = json.loads(resp.read().decode("utf-8"))
                http_status = resp.status
                echoed_json = body.get("json")
                endpoint_url = body.get("url")
                erro = None
        except (urllib.error.URLError, TimeoutError, Exception) as exc:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            http_status = None
            echoed_json = None
            endpoint_url = "https://httpbin.org/post"
            erro = str(exc)

        results.append(
            {
                "glpi_ticket_id": tid,
                "caso_teste": desc_caso,
                "executor_teste": "Script Python (scripts/validar_poc.py via urllib.request)",
                "executado_no_n8n": False,
                "inferencia_gemini_real": False,
                "nota_metodologica": (
                    "Teste controlado de Análise de Valor-Limite executado diretamente via Python "
                    "contra httpbin.org/post para exercitar os exatos escores de fronteira (0.84, "
                    "0.85, 0.86 e crítico 0.92). A execução ao vivo do mesmo chamado no n8n+Gemini "
                    "consta em evidencias/logs_execucao_n8n_100.json."
                ),
                "input_ticket": {
                    "ticket_id": tid,
                    "user_email": t["user_email"],
                    "ticket_title": t["ticket_title"],
                    "ticket_description": t["ticket_description"],
                },
                "llm_output_simulado": {
                    "intencao": real_rec["intencao_classificada"],
                    "urgencia": real_rec["nivel_urgencia"],
                    "categoria_glpi": real_rec["categoria_sugerida"],
                    "confianca": conf_teste,
                    "requer_revisao_humana": rev_teste,
                },
                "execucao_real_n8n_referencia": {
                    "n8n_execution_id": real_rec["n8n_execution_id"],
                    "confianca_gemini": real_rec["confianca_ia"],
                    "requer_revisao_gemini": real_rec["requer_revisao_humana"],
                    "status_processamento": real_rec["status_processamento"],
                    "tempo_processamento_ms": real_rec["tempo_processamento_ms"],
                },
                "avaliacao_no_if": {
                    "cond_requer_revisao_false": cond_boolean,
                    "cond_confianca_maior_igual_0_85": cond_number,
                    "resultado_gateway": routed_auto,
                    "ramo_n8n": branch,
                    "status_processamento": status_eval,
                },
                "emulacao_httpbin": {
                    "endpoint": endpoint_url,
                    "http_status": http_status,
                    "latencia_http_ms": elapsed_ms,
                    "payload_enviado": payload,
                    "json_ecoado_httpbin": echoed_json,
                    "erro": erro,
                },
                "executado_em_utc": datetime.now(timezone.utc).isoformat(),
            }
        )

    (EVIDENCIAS_DIR / "testes_valor_limite_httpbin.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return results


def _compute_latency_stats(values: list[int]) -> dict[str, Any]:
    """Calcula estatísticas descritivas (soma, média, mediana, mínimo e máximo) em ms."""
    return {
        "count": len(values),
        "sum_ms": sum(values),
        "mean_ms": statistics.mean(values),
        "median_ms": statistics.median(values),
        "stdev_ms": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min_ms": min(values),
        "max_ms": max(values),
    }


def recalculate_metrics_from_n8n_logs(
    logs_doc: dict[str, Any],
    tickets_by_id: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Recalcula todos os indicadores da PoC diretamente de evidencias/logs_execucao_n8n_100.json."""
    execucoes = sorted(logs_doc["execucoes"], key=lambda e: int(e["glpi_ticket_id"]))
    assert len(execucoes) == 100

    cats = ["Hardware", "Software", "Redes", "Acessos"]
    matriz_pad = {g: {p: 0 for p in cats} for g in cats}
    matriz_tot = {g: {p: 0 for p in cats} for g in cats}

    pad_cat_ok = 0
    pad_int_ok = 0
    pad_rout_ok = 0
    tot_cat_ok = 0
    tot_int_ok = 0
    tot_rout_ok = 0
    auto_count = 0
    rev_count = 0
    rev_low = 0
    rev_crit = 0
    http_200_count = 0

    e2e_entries: list[tuple[int, int]] = []
    node_names = [
        "Webhook GLPI (Novo Chamado)",
        "Google Gemini Chat Model",
        "Structured Output Parser",
        "Agente Cognitivo LLM (Parsing)",
        "Verifica Confianca (Score >= 0.85)",
        "Atualiza Chamado no GLPI (API)",
        "Desvio para Fila Humana (Human-in-the-Loop)",
        "Registra Auditoria no Supabase",
    ]
    node_lat_lists: dict[str, list[int]] = {name: [] for name in node_names}

    prompt_tokens = 0
    comp_tokens = 0
    total_tokens = 0
    divergencias: list[dict[str, Any]] = []

    for ev in execucoes:
        tid = int(ev["glpi_ticket_id"])
        t = tickets_by_id[tid]
        traces = ev["node_traces"]

        parsed = traces["Structured Output Parser"]["parsed_output"]
        cat_pred = parsed["categoria_glpi"]
        int_pred = parsed["intencao"]
        conf = float(parsed["confianca"])
        rev_flag = bool(parsed["requer_revisao_humana"])

        branch_raw = traces["Verifica Confianca (Score >= 0.85)"]["branch_taken"]
        if branch_raw == "true (Automatico)":
            branch_taken = True
        elif branch_raw == "false (Revisao Humana)":
            branch_taken = False
        else:
            raise AssertionError(f"Valor inesperado em branch_taken: {branch_raw!r}")
        assert branch_taken == ((conf >= 0.85) and (not rev_flag))
        status_pred = "Automatico" if branch_taken else "Revisao Humana"

        http_node_name = (
            "Atualiza Chamado no GLPI (API)"
            if branch_taken
            else "Desvio para Fila Humana (Human-in-the-Loop)"
        )
        if traces[http_node_name]["httpbin_status"] == 200:
            http_200_count += 1

        if status_pred == "Automatico":
            auto_count += 1
        else:
            rev_count += 1
            if conf < 0.85:
                rev_low += 1
            else:
                rev_crit += 1

        cat_gab = t["categoria_gabarito"]
        int_gab = t["intencao_gabarito"]
        rout_gab = t["roteamento_esperado"]

        matriz_tot[cat_gab][cat_pred] += 1
        if t["tipo_cenario"] == "Padronizado":
            matriz_pad[cat_gab][cat_pred] += 1
            if cat_pred == cat_gab:
                pad_cat_ok += 1
            if int_pred == int_gab:
                pad_int_ok += 1
            if status_pred == rout_gab:
                pad_rout_ok += 1

        if cat_pred == cat_gab:
            tot_cat_ok += 1
        if int_pred == int_gab:
            tot_int_ok += 1
        if status_pred == rout_gab:
            tot_rout_ok += 1

        if cat_pred != cat_gab or int_pred != int_gab or status_pred != rout_gab:
            divergencias.append(
                {
                    "glpi_ticket_id": tid,
                    "n8n_execution_id": int(ev["n8n_execution_id"]),
                    "conteudo_original": t["conteudo_original"],
                    "gabarito": f"{cat_gab} / {int_gab} / {rout_gab}",
                    "predicao": f"{cat_pred} / {int_pred} / {status_pred}",
                    "confianca": conf,
                }
            )

        sb_trace = traces["Registra Auditoria no Supabase"]
        e2e_entries.append((int(sb_trace["tempo_processamento_ms"]), tid))

        gem = traces["Google Gemini Chat Model"]
        prompt_tokens += int(gem["tokenUsage"]["promptTokens"])
        comp_tokens += int(gem["tokenUsage"]["completionTokens"])
        total_tokens += int(gem["tokenUsage"]["totalTokens"])

        for name in node_names:
            if name in traces:
                node_lat_lists[name].append(int(traces[name]["executionTime_ms"]))

    e2e_values = [ms for ms, _ in e2e_entries]
    e2e_stats = _compute_latency_stats(e2e_values)
    min_ms, min_tid = min(e2e_entries, key=lambda x: x[0])
    max_ms, max_tid = max(e2e_entries, key=lambda x: x[0])
    e2e_stats["min_ticket_id"] = min_tid
    e2e_stats["max_ticket_id"] = max_tid

    node_latencies = {name: _compute_latency_stats(vals) for name, vals in node_lat_lists.items()}

    return {
        "total": len(execucoes),
        "pad_total": 80,
        "amb_total": 20,
        "pad_cat_acc": pad_cat_ok,
        "pad_int_acc": pad_int_ok,
        "pad_rout_acc": pad_rout_ok,
        "tot_cat_acc": tot_cat_ok,
        "tot_int_acc": tot_int_ok,
        "rout_acc": tot_rout_ok,
        "auto": auto_count,
        "rev": rev_count,
        "rev_low": rev_low,
        "rev_crit": rev_crit,
        "http_200_count": http_200_count,
        "e2e_stats": e2e_stats,
        "mean_e2e_ms": e2e_stats["mean_ms"],
        "median_e2e_ms": e2e_stats["median_ms"],
        "mean_gem_ms": node_latencies["Google Gemini Chat Model"]["mean_ms"],
        "node_latencies": node_latencies,
        "prompt_tokens": prompt_tokens,
        "comp_tokens": comp_tokens,
        "total_tokens": total_tokens,
        "retries_429": logs_doc["metadados_execucao"].get("tentativas_transientes_retry_429", 0),
        "matriz_pad": matriz_pad,
        "matriz_tot": matriz_tot,
        "divergencias": divergencias,
    }


def verify_cross_artifact_metrics_parity(
    log_metrics: dict[str, Any],
    results: list[dict[str, Any]],
) -> None:
    """Confere que os indicadores recalculados dos logs do n8n batem 100% com JSON/CSV do Supabase."""
    pad = [r for r in results if r["tipo_cenario"] == "Padronizado"]
    assert len(results) == log_metrics["total"] == 100
    assert len(pad) == log_metrics["pad_total"] == 80
    assert sum(1 for r in pad if r["acerto_categoria"]) == log_metrics["pad_cat_acc"] == 80
    assert sum(1 for r in pad if r["acerto_intencao"]) == log_metrics["pad_int_acc"] == 80
    assert sum(1 for r in pad if r["acerto_roteamento"]) == log_metrics["pad_rout_acc"] == 80
    assert sum(1 for r in results if r["acerto_categoria"]) == log_metrics["tot_cat_acc"] == 99
    assert sum(1 for r in results if r["acerto_intencao"]) == log_metrics["tot_int_acc"] == 99
    assert sum(1 for r in results if r["acerto_roteamento"]) == log_metrics["rout_acc"] == 99
    assert sum(1 for r in results if r["status_processamento"] == "Automatico") == log_metrics["auto"] == 83
    assert sum(1 for r in results if r["status_processamento"] == "Revisao Humana") == log_metrics["rev"] == 17
    assert sum(int(r["tempo_processamento_ms"]) for r in results) == log_metrics["e2e_stats"]["sum_ms"]
    assert abs(statistics.mean(int(r["tempo_processamento_ms"]) for r in results) - log_metrics["mean_e2e_ms"]) < 1e-9
    assert abs(statistics.median(int(r["tempo_processamento_ms"]) for r in results) - log_metrics["median_e2e_ms"]) < 1e-9


def generate_summary_markdown(
    tech_config: dict[str, Any],
    logs_doc: dict[str, Any],
    log_metrics: dict[str, Any],
    results: list[dict[str, Any]],
    boundary_results: list[dict[str, Any]],
) -> dict[str, Any]:
    results = sorted(results, key=lambda r: int(r["glpi_ticket_id"]))
    cats = ["Hardware", "Software", "Redes", "Acessos"]
    matriz_pad = log_metrics["matriz_pad"]
    matriz_tot = log_metrics["matriz_tot"]

    linhas_m_pad = "\n".join(
        f"| **{g}** | {matriz_pad[g]['Hardware']} | {matriz_pad[g]['Software']} | {matriz_pad[g]['Redes']} | {matriz_pad[g]['Acessos']} | {sum(matriz_pad[g].values())} |"
        for g in cats
    )
    linhas_m_tot = "\n".join(
        f"| **{g}** | {matriz_tot[g]['Hardware']} | {matriz_tot[g]['Software']} | {matriz_tot[g]['Redes']} | {matriz_tot[g]['Acessos']} | {sum(matriz_tot[g].values())} |"
        for g in cats
    )

    linhas_div = "\n".join(
        f"| {d['glpi_ticket_id']} | {d['n8n_execution_id']} | {d['conteudo_original']} | "
        f"{d['gabarito']} | {d['predicao']} | {d['confianca']:.2f} |"
        for d in log_metrics["divergencias"]
    )

    e2e = log_metrics["e2e_stats"]
    gem_stats = log_metrics["node_latencies"]["Google Gemini Chat Model"]

    node_order = [
        ("Webhook GLPI (Novo Chamado)", "Recepção HTTP POST"),
        ("Google Gemini Chat Model", "Inferência LLM (`models/gemini-3.5-flash-lite`)"),
        ("Structured Output Parser", "Validação JSON Schema"),
        ("Agente Cognitivo LLM (Parsing)", "Nó agente composto (Gemini + Parser)"),
        ("Verifica Confianca (Score >= 0.85)", "Gateway condicional (`IF`)"),
        ("Atualiza Chamado no GLPI (API)", "Ramo Automático -> `httpbin.org/post`"),
        ("Desvio para Fila Humana (Human-in-the-Loop)", "Ramo HITL -> `httpbin.org/post`"),
        ("Registra Auditoria no Supabase", "Persistência REST PostgreSQL"),
    ]
    linhas_nodes = "\n".join(
        f"| `{name}` | {desc} | {log_metrics['node_latencies'][name]['count']} | "
        f"{log_metrics['node_latencies'][name]['mean_ms']:.2f} ms | "
        f"{log_metrics['node_latencies'][name]['median_ms']:.1f} ms | "
        f"{log_metrics['node_latencies'][name]['min_ms']}–{log_metrics['node_latencies'][name]['max_ms']} ms |"
        for name, desc in node_order
    )

    by_id = {int(r["glpi_ticket_id"]): r for r in results}
    crit_ids = [2001, 2080, 2081, 2084, 2085, 2090, 2091, 2092]
    linhas_reais_lim = "\n".join(
        f"| {tid} | {by_id[tid]['n8n_execution_id']} | {by_id[tid]['categoria_sugerida']} | "
        f"{by_id[tid]['confianca_ia']:.2f} | `{str(by_id[tid]['requer_revisao_humana']).lower()}` | "
        f"{by_id[tid]['status_processamento']} | {by_id[tid]['tempo_processamento_ms']} ms | `{by_id[tid]['supabase_id'][:8]}...` |"
        for tid in crit_ids
    )

    linhas_limite = "\n".join(
        f"| {b['glpi_ticket_id']} | {b['caso_teste']} | {b['llm_output_simulado']['confianca']:.2f} | "
        f"`{str(b['llm_output_simulado']['requer_revisao_humana']).lower()}` | "
        f"{b['avaliacao_no_if']['status_processamento']} | "
        f"HTTP {b['emulacao_httpbin']['http_status']} ({b['emulacao_httpbin']['latencia_http_ms']} ms) |"
        for b in boundary_results
    )

    resumo_md = f"""# Resumo de Conferência e Recálculo Direto dos Indicadores da PoC

## 1. Origem das Evidências e Separação de Camadas (`N = 100`)
Todos os 100 chamados sintéticos foram executados ao vivo pelo fluxo no **n8n v{logs_doc['metadados_execucao']['n8n_versao']}** (`workflow_id = {tech_config['workflow_id']}`), processados individualmente pelo modelo **Google Gemini (`{tech_config['gemini_model']}`, `temperature = {tech_config['temperature']}`)** com **Structured Output Parser**, encaminhados via **`{tech_config['http_auto_url']}`** (emulando saída GLPI / fila humana sem instância produtiva) e persistidos no **Supabase (`chamados_triagem`)**:

1. **Entrada e Gabarito Sintético ([`../data/chamados_sinteticos_100.json`](../data/chamados_sinteticos_100.json), [`../data/gabarito_classificacao_100.csv`](../data/gabarito_classificacao_100.csv)):** 100 chamados fictícios anonimizados (25 Hardware, 25 Software, 25 Redes e 25 Acessos; 80 padronizados `2001..2080` e 20 ambíguos/críticos `2081..2100`).
2. **Logs Individuais das 100 Execuções no n8n ([`logs_execucao_n8n_100.json`](logs_execucao_n8n_100.json)):** rastreamento completo nó a nó de cada uma das 100 execuções (`n8n_execution_id` com `status = "success"`), comprovando entrada do Webhook, latência e consumo de tokens do `Google Gemini Chat Model`, JSON estruturado do `Structured Output Parser`, ramo do nó `IF`, eco HTTP 200 de `https://httpbin.org/post` e UUID gravado no Supabase.
3. **Registros Reais Persistidos no Supabase ([`resultados_execucao_100.json`](resultados_execucao_100.json), [`resultados_execucao_100.csv`](resultados_execucao_100.csv) e [`../database/schema.sql`](../database/schema.sql)):** espelho exato das 100 linhas gravadas no banco Supabase pelo nó `Registra Auditoria no Supabase`, preservando UUIDs, timestamps UTC, respostas sugeridas geradas pelo LLM, sinalizadores individuais de acerto (`acerto_categoria`, `acerto_intencao`, `acerto_roteamento`) e `tempo_processamento_ms` medido em tempo real.
4. **Testes Controlados de Valor-Limite via Python ([`testes_valor_limite_httpbin.json`](testes_valor_limite_httpbin.json)):** requisições `HTTP POST` disparadas diretamente por [`../scripts/validar_poc.py`](../scripts/validar_poc.py) para `https://httpbin.org/post` avaliando exatamente os escores de fronteira `0.84`, `0.85`, `0.86` e `0.92` (`executado_no_n8n = false`, `inferencia_gemini_real = false`), complementando as execuções ao vivo do Gemini (que retornou escores em múltiplos de `0.05`: `0.50`, `0.65`, `0.70`, `0.75`, `0.80`, `0.90`, `0.95`, `1.00`).

### 1.1 Distinção Metodológica: Carga SQL Sintética Inicial vs. Nova Bateria Ao Vivo no n8n
Para rastreabilidade completa da evolução do repositório e do TCC, documenta-se explicitamente a diferença entre os dados estáticos iniciais e a bateria real executada no n8n:

| Aspecto Avaliado | Carga Sintética Inicial em SQL *(superada)* | Nova Bateria Ao Vivo (`n8n + Gemini + Supabase`) *(atual)* |
| :--- | :--- | :--- |
| **Origem dos registros** | `INSERT` estático pré-preenchido em SQL, sem chamadas reais ao Gemini | 100 execuções ao vivo no `n8n` (`evidencias/logs_execucao_n8n_100.json`) persistidas no Supabase |
| **Acurácia nos 80 padronizados** | `74 / 80` (`92,5%`) predeterminada no seed | **`80 / 80` (`100,0%`)** em categoria e intenção (recalculado dos logs) |
| **Acurácia categorial global (`N = 100`)** | Derivada dos rótulos sintéticos do seed | **`99 / 100` (`99,0%`)** em categoria, intenção e roteamento |
| **Distribuição de encaminhamento** | `82` automáticos / `18` revisões humanas | **`83` automáticos (`83,0%`) / `17` revisões humanas (`17,0%`)** (`8` `< 0.85` + `9` críticos) |
| **Tempo de processamento** | `NULL` no SQL / placeholder preliminar (`1.900 ms`) no workflow | **`1.519,4 ms`** médios efetivamente medidos (`151.938 ms` no lote; mediana `1.487,0 ms`) |
| **Escopo da avaliação** | Ilustração estática sem rastreamento nó a nó | Avaliação técnica controlada da própria PoC (sem comparação empírica com atendimento humano real) |

---

## 2. Configuração Técnica Conferida
- **Orquestrador:** n8n `v{logs_doc['metadados_execucao']['n8n_versao']}` | Workflow ID `{tech_config['workflow_id']}` ({tech_config['node_count']} nós)
- **Histórico de execuções habilitado:** `saveDataSuccessExecution = "{tech_config['save_success']}"`, `saveDataErrorExecution = "{tech_config['save_error']}"`, `saveManualExecutions = {str(tech_config['save_manual']).lower()}`
- **Modelo LLM:** `{tech_config['gemini_model']}` | Temperatura: `{tech_config['temperature']}`
- **Parser JSON:** `{tech_config['parser_type']}`
- **Limiar do gateway IF:** `confianca >= {tech_config['if_threshold']}` AND `requer_revisao_humana == false`
- **Expressão `tempo_processamento_ms`:** `{tech_config['tempo_expr']}` (medição real em ms sem fallback artificial)
- **Endpoints HTTP emulados:** `{tech_config['http_auto_url']}` (automático e revisão humana; {log_metrics['http_200_count']}/100 retornaram HTTP 200)
- **Varredura de segredos/tokens:** Limpa (`secret_scan_clean = {tech_config['secret_scan_clean']}`)

---

## 3. Indicadores Recalculados Diretamente dos Logs do n8n (`N = 100`)
Todos os números abaixo foram recalculados diretamente pelo script [`../scripts/validar_poc.py`](../scripts/validar_poc.py) a partir dos `node_traces` individuais de [`logs_execucao_n8n_100.json`](logs_execucao_n8n_100.json) e conferidos com 100% de paridade contra `resultados_execucao_100.json`, `resultados_execucao_100.csv` e `database/schema.sql`:

| Indicador | Critério / Fórmula Direta sobre `logs_execucao_n8n_100.json` | Resultado Recalculado |
| :--- | :--- | :--- |
| Chamados sintéticos processados | Execuções `status = success` no n8n e linhas no Supabase | **100 de 100 (100,0%)** |
| Acurácia categorial (padronizados) | `categoria_glpi == categoria_gabarito` em `2001..2080` | **{log_metrics['pad_cat_acc']} de 80 ({log_metrics['pad_cat_acc']/80*100:.1f}%)** |
| Acurácia de intenção (padronizados) | `intencao == intencao_gabarito` em `2001..2080` | **{log_metrics['pad_int_acc']} de 80 ({log_metrics['pad_int_acc']/80*100:.1f}%)** |
| Acurácia categorial global (`N = 100`) | `categoria_glpi == categoria_gabarito` em `2001..2100` | **{log_metrics['tot_cat_acc']} de 100 ({log_metrics['tot_cat_acc']:.1f}%)** |
| Acurácia de intenção global (`N = 100`) | `intencao == intencao_gabarito` em `2001..2100` | **{log_metrics['tot_int_acc']} de 100 ({log_metrics['tot_int_acc']:.1f}%)** |
| Concordância de roteamento global | Ramo executado no nó `IF` == `roteamento_esperado` em `2001..2100` | **{log_metrics['rout_acc']} de 100 ({log_metrics['rout_acc']:.1f}%)** |
| Encaminhamento automático | Ramo `branch_taken = true` (`confianca >= 0.85` e `requer_revisao_humana = false`) | **{log_metrics['auto']} de 100 ({log_metrics['auto']:.1f}%)** |
| Encaminhamento para revisão humana | Ramo `branch_taken = false` (`{log_metrics['rev_low']}` com confiança `< 0.85` + `{log_metrics['rev_crit']}` críticos `>= 0.85`) | **{log_metrics['rev']} de 100 ({log_metrics['rev']:.1f}%)** |
| Soma e média de `tempo_processamento_ms` | Soma = `{e2e['sum_ms']:,} ms` / Média = `{e2e['sum_ms']}/100` | **{e2e['mean_ms']:.2f} ms ({e2e['mean_ms']:.1f} ms / ~{e2e['mean_ms']/1000:.2f} s)** |
| Mediana, desvio padrão e amplitude | Valores reais de `tempo_processamento_ms` no nó Supabase | Mediana **{e2e['median_ms']:.1f} ms** / DP **{e2e['stdev_ms']:.2f} ms** / **{e2e['min_ms']}** (ID `{e2e['min_ticket_id']}`)–**{e2e['max_ms']} ms** (ID `{e2e['max_ticket_id']}`) |
| Latência isolada do nó Gemini Chat Model | `executionTime_ms` acumulado = `{gem_stats['sum_ms']:,} ms` | **{gem_stats['mean_ms']:.2f} ms** / Mediana **{gem_stats['median_ms']:.1f} ms** ({gem_stats['min_ms']}–{gem_stats['max_ms']} ms) |
| Consumo total de tokens (`N = 100`) | Soma direta de `tokenUsage` (`promptTokens + completionTokens`) | **{log_metrics['total_tokens']:,}** tokens ({log_metrics['prompt_tokens']:,} prompt + {log_metrics['comp_tokens']:,} saída; média **{log_metrics['total_tokens']/100:.1f}**/chamado) |
| Retentativas transientes (`HTTP 429`) | Contagem registrada na coleta da API gratuita do Gemini | **{log_metrics['retries_429']}** retentativas transientes (100% concluídos com sucesso) |

### 3.1 Decomposição da Latência por Nó do Fluxo (`node_traces`)

| Nó do Workflow (`n8n`) | Função na Esteira | Execuções | Média | Mediana | Mín.–Máx. |
| :--- | :--- | :---: | :---: | :---: | :---: |
{linhas_nodes}
| **Total ponta a ponta medido (`tempo_processamento_ms`)** | `Date.now() - timestamp_inicio_ms` gravado no Supabase | **100** | **{e2e['mean_ms']:.2f} ms** | **{e2e['median_ms']:.1f} ms** | **{e2e['min_ms']}–{e2e['max_ms']} ms** |

---

## 4. Matrizes de Confusão Reais (`Google Gemini` vs. Gabarito)

### 4.1 Subconjunto Padronizado (`2001..2080`, `N = 80`) — {log_metrics['pad_cat_acc']}/80 ({log_metrics['pad_cat_acc']/80*100:.1f}%)

| Gabarito \\ Predição Gemini | Hardware | Software | Redes | Acessos | Total Gabarito |
| :--- | :---: | :---: | :---: | :---: | :---: |
{linhas_m_pad}

### 4.2 Amostra Completa (`2001..2100`, `N = 100`) — {log_metrics['tot_cat_acc']}/100 ({log_metrics['tot_cat_acc']:.1f}%)

| Gabarito \\ Predição Gemini | Hardware | Software | Redes | Acessos | Total Gabarito |
| :--- | :---: | :---: | :---: | :---: | :---: |
{linhas_m_tot}

### 4.3 Divergências Observadas no Subconjunto Ambíguo/Crítico (`N = 100`)

| Ticket ID | Execução n8n | Conteúdo | Gabarito (Cat / Int / Rot) | Gemini Real (Cat / Int / Rot) | Confiança |
| :---: | :---: | :--- | :---: | :---: | :---: |
{linhas_div}

> **Análise das divergências:** Nos casos `2083` e `2090`, apesar da diferença pontual de intenção (`2083`) ou categoria (`2090`) em relatos propositalmente vagos, o modelo atribuiu confiança baixa (`0,65` e `0,50`) e sinalizou `requer_revisao_humana = true`, garantindo o desvio seguro para **Revisão Humana**. No chamado `2089` (*"Aplicativo corporativo travando - O sistema financeiro fecha sozinho ao gerar relatório sem exibir código de erro"*), o modelo acertou a categoria (`Software`) e a intenção (`Incidente`), mas atribuiu `confianca = 0,90` com `requer_revisao_humana = false`, encaminhando automaticamente apesar da expectativa conservadora do gabarito.

---

## 5. Casos de Referência, Limite e Críticos Reais no n8n + Supabase

| Ticket ID | `n8n_exec_id` | Categoria Gemini | Confiança | `requer_revisao_humana` | Status Supabase | Tempo Medido | UUID Supabase |
| :---: | :---: | :---: | :---: | :---: | :--- | :---: | :--- |
{linhas_reais_lim}

---

## 6. Testes Controlados de Valor-Limite HTTP via Python (`scripts/validar_poc.py` -> `httpbin.org/post`)
*Nota: Requisições `HTTP POST` executadas diretamente pelo script Python sobre os exatos escores de fronteira (`0.84`, `0.85`, `0.86`, `0.92`) para testar a precisão matemática do gateway (`executado_no_n8n = false`, `inferencia_gemini_real = false`), em complemento às execuções reais do n8n listadas na Seção 5.*

| Ticket ID | Cenário de Teste | Confiança | `requer_revisao_humana` | Decisão Gateway | Resposta HTTP Emulada (Python) |
| :---: | :--- | :---: | :---: | :---: | :---: |
{linhas_limite}
"""
    (EVIDENCIAS_DIR / "resumo_indicadores.md").write_text(resumo_md, encoding="utf-8")
    return log_metrics


def main() -> None:
    tech_config = verify_workflow_and_secrets()
    _, tickets_by_id = load_and_verify_dataset()
    logs_doc, _, results = load_and_verify_n8n_and_supabase(tickets_by_id)
    log_metrics = recalculate_metrics_from_n8n_logs(logs_doc, tickets_by_id)
    verify_cross_artifact_metrics_parity(log_metrics, results)
    verify_sql_parity(results)
    results_by_id = {int(r["glpi_ticket_id"]): r for r in results}
    boundary_results = run_httpbin_boundary_tests(tickets_by_id, results_by_id)
    stats = generate_summary_markdown(tech_config, logs_doc, log_metrics, results, boundary_results)

    print("Validação concluída com sucesso!")
    print("Paridade completa verificada: data/ == logs_execucao_n8n_100.json == resultados_execucao_100 == database/schema.sql (SQLite)")
    print(f"Total de chamados executados no n8n + Gemini + Supabase: {stats['total']}")
    print(
        f"Padronizados (2001..2080): {stats['pad_cat_acc']}/80 acertos categoriais "
        f"({stats['pad_cat_acc']/80*100:.1f}%) | {stats['pad_int_acc']}/80 intenção"
    )
    print(
        f"Global (2001..2100): {stats['tot_cat_acc']}/100 categoria ({stats['tot_cat_acc']}%) | "
        f"{stats['tot_int_acc']}/100 intenção | {stats['rout_acc']}/100 concordância de roteamento"
    )
    print(
        f"Encaminhamentos -> Automatico: {stats['auto']} | Revisao Humana: {stats['rev']} "
        f"({stats['rev_low']} confiança < 0.85 + {stats['rev_crit']} críticos >= 0.85)"
    )
    print(
        f"Tempo médio e2e medido: {stats['mean_e2e_ms']:.2f} ms (mediana {stats['median_e2e_ms']:.1f} ms) | "
        f"Nó Gemini: {stats['mean_gem_ms']:.2f} ms | Tokens totais: {stats['total_tokens']:,}"
    )
    for b in boundary_results:
        print(
            f"Teste BVA Python ID {b['glpi_ticket_id']} | conf={b['llm_output_simulado']['confianca']:.2f} | "
            f"rev={b['llm_output_simulado']['requer_revisao_humana']} -> "
            f"{b['avaliacao_no_if']['status_processamento']} | "
            f"httpbin status={b['emulacao_httpbin']['http_status']} ({b['emulacao_httpbin']['latencia_http_ms']} ms)"
        )


if __name__ == "__main__":
    main()
