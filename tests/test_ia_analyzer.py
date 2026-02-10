from ia_analyzer import AnaliseIA


def test_parse_valid_json():
    raw = '{"resumo": "ok", "situacao": "URGENTE", "prazo": null, "proxima_acao": null}'
    analise = AnaliseIA(raw)
    assert analise.sucesso
    assert analise.resumo == "ok"
    assert analise.situacao == "URGENTE"


def test_parse_json_with_text():
    raw = 'Resposta:\n```json\n{"resumo": "ok", "situacao": "NORMAL"}\n```'
    analise = AnaliseIA(raw)
    assert analise.sucesso
    assert analise.resumo == "ok"
    assert analise.situacao == "NORMAL"


def test_parse_invalid_json_trailing_comma():
    raw = '{"resumo": "ok", "situacao": "NORMAL",}'
    analise = AnaliseIA(raw)
    assert analise.sucesso
    assert analise.situacao == "NORMAL"


def test_parse_plain_text_fields():
    raw = "Resumo: algo\nSituacao: urgente\nPrazo: 5 dias\nProxima acao: protocolar"
    analise = AnaliseIA(raw)
    assert analise.sucesso
    assert analise.resumo == "algo"
    assert analise.situacao == "URGENTE"
    assert analise.prazo == "5 dias"
    assert analise.proxima_acao == "protocolar"
