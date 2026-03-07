# CONTEXT - bot-relatorio

## Objetivo
Monitorar processos judiciais via API Comunica PJe (CNJ), resumir publicacoes com IA e atualizar Google Sheets.

## Entrada e saida
- Entrada: numeros de processo em abas da planilha Google Sheets.
- Entrada tecnica: `config.json`/`.env` + credenciais Google.
- Saida: colunas de status, ultima verificacao, andamento atual e ultima publicacao atualizadas na planilha.

## Fluxo tecnico
1. `bot.py` valida conexoes (Sheets, IA, API Comunica).
2. `google_sheets.py` carrega processos das abas.
3. `api_comunica.py` consulta publicacoes por processo.
4. `ia_analyzer.py` gera resumo/situacao (Gemini ou Ollama).
5. `google_sheets.py` grava atualizacoes por linha.

## Arquivos-chave
- `bot.py`: entrypoint e CLI (`--aba`, `--teste`, `--sem-ia`, `--no-prompt`).
- `config.py`: loader de config com precedencia `config.json` -> `.env` -> env do sistema.
- `api_comunica.py`: cliente da API CNJ.
- `google_sheets.py`: leitura/escrita na planilha.
- `ia_analyzer.py`: provedores IA e parse JSON de resposta.
- `verificar_setup.py`: diagnostico de setup.
- `config.example.json`: template de configuracao.
- `tests/test_ia_analyzer.py`: testes de parser/IA.

## Configuracao critica
- `google_sheets.arquivo_credenciais`
- `google_sheets.nome_planilha`
- `ia.provedor` (`gemini` ou `ollama`)
- `ia.gemini.api_key` e `ia.gemini.modelo`
- `ia.ollama.url` e `ia.ollama.modelo`
- `api_comunica.url_base`, delays e timeout
- mapeamento de colunas em `planilha.*`

## Comandos rapidos
- Executar geral: `python bot.py`
- Somente uma aba: `python bot.py --aba "Nome da Aba"`
- Modo teste: `python bot.py --teste`
- Sem IA: `python bot.py --sem-ia`
- Verificar ambiente: `python verificar_setup.py`

## Riscos comuns
- Credencial Google sem permissao na planilha.
- Nome de coluna diferente do configurado.
- Chave/modelo IA invalido.
- Rate limit/API timeout na consulta CNJ.

## Retomada rapida (prompt sugerido)
"Use `bot-relatorio/CONTEXT.md` como base. Foque em [arquivos]. Objetivo: [objetivo]."

## Regra operacional
Nao commitar `config.json`, credenciais Google, `.env` com segredos.
