# Bot Consulta Processual

Bot para monitoramento automatizado de processos judiciais brasileiros.

Consulta a **API Comunica PJe** (CNJ) para obter publicações do Diário de Justiça Eletrônico Nacional e atualiza uma planilha Google Sheets com resumos gerados por IA.

## ✨ Funcionalidades

- 📋 Lê processos de uma planilha Google Sheets (múltiplas abas/clientes)
- 🔍 Consulta publicações na API pública do CNJ (sem CAPTCHA!)
- 🤖 Gera resumos com IA (Gemini ou Ollama)
- 📊 Atualiza a planilha com status e resumos
- ⚡ Rate limiting automático para evitar bloqueios

## 📦 Cobertura

A API Comunica PJe cobre publicações de:

| Sistema | Cobertura |
|---------|-----------|
| PJe | ✅ Total |
| e-Proc | ✅ Total |
| eSAJ | ✅ Total |
| Outros | Variável |

## 🚀 Instalação

Requisitos: Python 3.10+


### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/botconsulta.git
cd botconsulta
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Configure as credenciais do Google

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um projeto (ou use um existente)
3. Ative a API do Google Sheets e Google Drive
4. Crie uma Service Account
5. Baixe o JSON das credenciais como `credenciais.json`
6. Compartilhe sua planilha com o email da Service Account

### 4. Configure o bot

```bash
cp config.example.json config.json
```

Edite `config.json` e preencha:

```json
{
    "google_sheets": {
        "arquivo_credenciais": "credenciais.json",
        "nome_planilha": "Controle Processual"
    },
    "ia": {
        "provedor": "gemini",
        "gemini": {
            "api_key": "SUA_CHAVE_AQUI"
        }
    }
}
```

### 5. Verifique o setup

```bash
python verificar_setup.py
```

## 📊 Estrutura da Planilha

A planilha deve ter as seguintes colunas (nomes podem variar):

| Coluna | Descrição |
|--------|-----------|
| `Processo` | Número do processo (formato CNJ) |
| `Status_Atual` | Preenchido pelo bot |
| `Ultima_Verificacao` | Preenchido pelo bot |
| `Resumo_IA` | Preenchido pelo bot |
| `Ultima_Publicacao` | Preenchido pelo bot |
| `Tipo_Ultima_Publicacao` | Preenchido pelo bot |

**Dica:** Crie uma aba para cada cliente (CPF/CNPJ).

## 🎮 Uso

### Execução normal

```bash
python bot.py
```

### Apenas uma aba específica

```bash
python bot.py --aba "Cliente ABC"
```

### Modo teste (não altera planilha)

```bash
python bot.py --teste
```

### Sem análise de IA

```bash
python bot.py --sem-ia
```

## 🔄 Usando com Outra Planilha

Para usar o bot com uma planilha diferente (outro cliente):

### 1. Altere o nome da planilha

Edite `config.json`, linha `nome_planilha`:

```json
{
    "google_sheets": {
        "arquivo_credenciais": "credenciais.json",
        "nome_planilha": "Nome da Nova Planilha"
    }
}
```

### 2. Compartilhe a nova planilha com o bot

A nova planilha precisa ser compartilhada com o email da Service Account.  
Você encontra esse email no arquivo `credenciais.json`, campo `client_email`.

### 3. Garanta a mesma estrutura de colunas

A nova planilha deve ter as mesmas colunas (ou configure nomes diferentes em `config.json` → seção `planilha`):

| Coluna padrão | Configurável em |
|---------------|-----------------|
| `Processo` | `coluna_processo` |
| `Status_Atual` | `coluna_status` |
| `Ultima_Verificacao` | `coluna_ultima_verificacao` |
| `Resumo_IA` | `coluna_resumo_ia` |
| `Ultima_Publicacao` | `coluna_ultima_publicacao` |
| `Tipo_Ultima_Publicacao` | `coluna_tipo_ultima` |

## 🤖 Provedores de IA

### Google Gemini (recomendado)

```json
{
    "ia": {
        "provedor": "gemini",
        "gemini": {
            "api_key": "sua-chave",
            "modelo": "gemini-2.5-flash"
        }
    }
}
```

Obtenha a chave em: https://aistudio.google.com/apikey

### Ollama (local)

```json
{
    "ia": {
        "provedor": "ollama",
        "ollama": {
            "url": "http://localhost:11434",
            "modelo": "llama3.1:8b-instruct-q4_K_M"
        }
    }
}
```

## 🔒 Segurança

**NUNCA commite:**
- `credenciais.json`
- `config.json` com chaves de API
- `.env` com segredos

Estes arquivos já estão no `.gitignore`.

## 📝 Licença

MIT

## 🤝 Contribuições

Contribuições são bem-vindas! Abra uma issue ou pull request.
