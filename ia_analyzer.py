# ia_analyzer.py
"""
Módulo de Análise com IA - Bot Consulta Processual

Suporta:
- Google Gemini (API)
- Ollama (local)
"""

import json
import re
import requests
from typing import Optional
from abc import ABC, abstractmethod

from config import config
from api_comunica import Publicacao


# ============================================================
# PROMPTS
# ============================================================

# Prompt para Gemini (mais curto, modelo mais inteligente)
PROMPT_GEMINI = """Atue como um Analista Jurídico Sênior focado em relatórios executivos para clientes.
Sua tarefa é analisar as publicações do Diário de Justiça e extrair a informação crucial para uma planilha de acompanhamento..

PUBLICAÇÕES (Contexto da mais recente para a mais antiga):
{publicacoes}

DIRETRIZES OBRIGATÓRIAS PARA O CAMPO 'RESUMO':
1. NÃO inicie com frases genéricas ("Trata-se de...", "O processo refere-se a...", "Foi publicada decisão...").
2. Vá direto à decisão/ato: [O QUE O JUIZ DECIDIU] + [CONSEQUÊNCIA PRÁTICA].
3. SEMPRE inclua, se disponíveis:
   - Valores monetários mencionados (dívida, custas, honorários, multas)
   - Prazos específicos (X dias para fazer Y)
4. Traduza o "juridiquês" para linguagem de negócios. (Ex: Troque "Deferida a dilação de prazo" por "Juiz concedeu mais tempo").
5. Se a publicação for apenas despacho administrativo (ex: "Junte-se", "Intime-se"), consulte publicações anteriores para contextualizar SOBRE O QUÊ é a intimação.
6. NUNCA termine o resumo com "o teor não foi disponibilizado" ou similar - extraia o máximo de informação possível do que ESTÁ disponível.

RESPONDA em formato JSON:
{{
    "resumo": "Texto objetivo (máx 600 caracteres). Exemplo: 'Juiz condenou Empresa ABC a pagar R$ 15.000 + honorários de 10%. Prazo de 15 dias para pagamento voluntário sob pena de multa de 10%.'",
    "situacao": "Uma tag: PROVAS, ARQUIVADO, ACORDO, SENTENCA, RECURSAL ou NORMAL",
    "prazo": "Se houver prazo correndo, qual é (ex: '15 dias para manifestação'). Se não, null",
    "proxima_acao": "O que o advogado deve fazer, se houver (ex: 'Protocolar recurso até 02/03/2026'). Se não, null"
}}

Responda APENAS o JSON, sem explicações."""


# Prompt para Ollama (mais detalhado, modelo menos inteligente)
PROMPT_OLLAMA = """Você é um assistente jurídico especializado em análise de publicações do Diário de Justiça.

Sua tarefa é analisar as publicações de um processo judicial e fornecer um resumo objetivo.

REGRAS IMPORTANTES:
1. Seja CONCISO - máximo 3 frases no resumo
2. Identifique se há PRAZO correndo para o advogado
3. Identifique se há AUDIÊNCIA marcada
4. Classifique a situação: URGENTE, AGUARDANDO, ARQUIVADO, ACORDO, SENTENCA, ou NORMAL
5. Responda APENAS em formato JSON válido
6. NÃO invente informações que não estão nas publicações

PUBLICAÇÕES DO PROCESSO (da mais recente para a mais antiga):

{publicacoes}

---

Agora analise e responda EXATAMENTE neste formato JSON (sem texto antes ou depois):

{{
    "resumo": "Escreva aqui um resumo de 3 frases do status atual",
    "situacao": "URGENTE ou AGUARDANDO ou ARQUIVADO ou ACORDO ou SENTENCA ou NORMAL",
    "prazo": "Descreva o prazo se houver, ou null se não houver",
    "proxima_acao": "O que fazer se necessário, ou null"
}}

JSON:"""


# ============================================================
# CLASSES BASE
# ============================================================

class AnaliseIA:
    """Resultado da análise de IA."""
    
    def __init__(self, raw_response: str):
        self.raw = raw_response
        self.resumo = ""
        self.situacao = "NORMAL"
        self.prazo = None
        self.proxima_acao = None
        self.erro = None
        self.aviso = None
        
        self._parse()
    
    def _parse(self):
        """Tenta extrair JSON da resposta."""
        try:
            # Remove possíveis marcadores de código
            texto = self.raw.strip()
            texto = re.sub(r"^```(?:json)?", "", texto, flags=re.IGNORECASE).strip()
            texto = texto.replace("```", "").strip()
            
            if texto.startswith("```json"):
                texto = texto[7:]
            if texto.startswith("```"):
                texto = texto[3:]
            if texto.endswith("```"):
                texto = texto[:-3]
            
            texto = texto.strip()
            
            # Tenta encontrar JSON na resposta
            json_str = self._extrair_json(texto)
            
            if json_str:
                dados = json.loads(json_str)
                
                self.resumo = dados.get("resumo", "")
                self.situacao = dados.get("situacao", "NORMAL").upper()
                self.prazo = dados.get("prazo")
                self.proxima_acao = dados.get("proxima_acao")
            else:
                # Tenta extrair campos de texto simples
                campos = self._extrair_campos_texto(texto)
                if campos:
                    self.resumo = campos.get("resumo", "")
                    self.situacao = campos.get("situacao", "NORMAL").upper()
                    self.prazo = campos.get("prazo")
                    self.proxima_acao = campos.get("proxima_acao")
                else:
                    # Se nao encontrou JSON, usa o texto como resumo
                    self.resumo = texto[:200] if texto else "Nao foi possivel analisar"
                    self.aviso = "Resposta nao contem JSON valido"
                    self.erro = None
        except json.JSONDecodeError as e:
            reparado = self._reparar_json(texto)
            if reparado:
                try:
                    dados = json.loads(reparado)
                    self.resumo = dados.get("resumo", "")
                    self.situacao = dados.get("situacao", "NORMAL").upper()
                    self.prazo = dados.get("prazo")
                    self.proxima_acao = dados.get("proxima_acao")
                    return
                except Exception:
                    pass
            
            self.resumo = self.raw[:200] if self.raw else "Erro na analise"
            self.aviso = f"JSON invalido: {e}"
            self.erro = None
        
        except Exception as e:
            self.resumo = "Erro na analise"
            self.erro = str(e)

    def _extrair_json(self, texto: str) -> Optional[str]:
        """Extrai o primeiro objeto JSON valido por balanceamento de chaves."""
        inicio = texto.find("{")
        if inicio < 0:
            return None
        
        profundidade = 0
        em_string = False
        escape = False
        
        for i in range(inicio, len(texto)):
            ch = texto[i]
            
            if em_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == "\"":
                    em_string = False
                continue
            
            if ch == "\"":
                em_string = True
            elif ch == "{":
                profundidade += 1
            elif ch == "}":
                profundidade -= 1
                if profundidade == 0:
                    return texto[inicio:i + 1]
        
        return None
    
    def _extrair_campos_texto(self, texto: str) -> Optional[dict]:
        """Extrai campos de uma resposta em texto simples."""
        if not texto:
            return None
        
        campos = {}
        padroes = {
            "resumo": r"resumo\s*[:\-]\s*(.+)",
            "situacao": r"situacao\s*[:\-]\s*(.+)",
            "prazo": r"prazo\s*[:\-]\s*(.+)",
            "proxima_acao": r"proxima[_\s]?acao\s*[:\-]\s*(.+)",
        }
        
        for chave, padrao in padroes.items():
            m = re.search(padrao, texto, flags=re.IGNORECASE)
            if m:
                valor = m.group(1).strip()
                if valor.lower() in ("null", "nenhum", "n/a", "nao"):
                    valor = None
                campos[chave] = valor
        
        return campos if campos else None

    def _reparar_json(self, texto: str) -> Optional[str]:
        """Tenta reparar JSON simples com erros comuns."""
        if not texto:
            return None
        
        reparado = texto.replace("?", "\"").replace("?", "\"").replace("?", "'").replace("?", "'")
        reparado = re.sub(r",\s*([}\]])", r"\1", reparado)
        
        json_str = self._extrair_json(reparado)
        return json_str

    @property
    def sucesso(self) -> bool:
        return self.erro is None and bool(self.resumo)


class IAProvider(ABC):
    """Interface para provedores de IA."""
    
    @abstractmethod
    def analisar(self, publicacoes: list[Publicacao]) -> AnaliseIA:
        """Analisa publicações e retorna resumo."""
        pass
    
    @abstractmethod
    def testar_conexao(self) -> tuple[bool, str]:
        """Testa se a conexão com o provedor está funcionando."""
        pass
    
    def _formatar_publicacoes(self, publicacoes: list[Publicacao]) -> str:
        """Formata publicações para o prompt."""
        partes = []
        
        for i, pub in enumerate(publicacoes, 1):
            texto_limpo = pub.texto_limpo
            if len(texto_limpo) > 1500:
                texto_limpo = texto_limpo[:1500] + "..."
            
            partes.append(f"""[{i}] Data: {pub.data_formatada}
Tipo: {pub.tipo_comunicacao}
Órgão: {pub.nome_orgao}
Teor: {texto_limpo}
""")
        
        return "\n".join(partes)


# ============================================================
# GEMINI
# ============================================================

class GeminiProvider(IAProvider):
    """Provedor Google Gemini."""
    
    def __init__(self):
        self.api_key = config.gemini_api_key
        self.model = config.gemini_model
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    def _extrair_texto(self, dados: dict) -> Optional[str]:
        """Extrai texto da resposta do Gemini de forma defensiva."""
        try:
            candidatos = dados.get("candidates") or []
            if not candidatos:
                return None
            
            content = candidatos[0].get("content") or {}
            parts = content.get("parts") or []
            if parts and isinstance(parts[0], dict) and "text" in parts[0]:
                return parts[0]["text"]
            
            if "text" in content:
                return content["text"]
        except Exception:
            return None
        
        return None
    
    def testar_conexao(self) -> tuple[bool, str]:
        """Testa conexão com a API do Gemini."""
        if not self.api_key or self.api_key == "SUA_CHAVE_GEMINI_AQUI":
            return False, "Chave da API não configurada"
        
        try:
            response = requests.post(
                self.url,
                headers={"Content-Type": "application/json"},
                params={"key": self.api_key},
                json={
                    "contents": [{"parts": [{"text": "Responda apenas: OK"}]}],
                    "generationConfig": {"maxOutputTokens": 10}
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return True, f"Conectado ao modelo {self.model}"
            else:
                erro = response.json().get("error", {}).get("message", response.text)
                return False, f"Erro {response.status_code}: {erro}"
        
        except Exception as e:
            return False, str(e)
    
    def analisar(self, publicacoes: list[Publicacao]) -> AnaliseIA:
        """Analisa publicações usando Gemini."""
        if not publicacoes:
            return AnaliseIA('{"resumo": "Sem publicações para analisar", "situacao": "NORMAL"}')
        
        prompt = PROMPT_GEMINI.format(
            publicacoes=self._formatar_publicacoes(publicacoes)
        )
        
        try:
            response = requests.post(
                self.url,
                headers={"Content-Type": "application/json"},
                params={"key": self.api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": 2000,
                        "temperature": 0.1,  # Mais determinístico
                        "responseMimeType": "application/json"
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                dados = response.json()
                texto = self._extrair_texto(dados)
                if not texto:
                    analise = AnaliseIA("")
                    analise.erro = "Resposta da IA sem texto"
                    analise.resumo = "Erro ao consultar IA"
                    return analise
                
                return AnaliseIA(texto)
            else:
                erro = response.json().get("error", {}).get("message", "Erro desconhecido")
                analise = AnaliseIA("")
                analise.erro = f"API Gemini: {erro}"
                analise.resumo = "Erro ao consultar IA"
                return analise
        
        except Exception as e:
            analise = AnaliseIA("")
            analise.erro = str(e)
            analise.resumo = "Erro ao consultar IA"
            return analise


# ============================================================
# OLLAMA
# ============================================================

class OllamaProvider(IAProvider):
    """Provedor Ollama (local)."""
    
    def __init__(self):
        self.url = config.ollama_url
        self.model = config.ollama_model
    
    def testar_conexao(self) -> tuple[bool, str]:
        """Testa conexão com o Ollama local."""
        try:
            # Verifica se o servidor está rodando
            response = requests.get(f"{self.url}/api/tags", timeout=5)
            
            if response.status_code != 200:
                return False, f"Servidor não respondeu (HTTP {response.status_code})"
            
            # Verifica se o modelo está disponível
            modelos = response.json().get("models", [])
            nomes = [m.get("name", "") for m in modelos]
            
            # Verifica match exato ou parcial
            modelo_encontrado = False
            for nome in nomes:
                if self.model in nome or nome in self.model:
                    modelo_encontrado = True
                    break
            
            if not modelo_encontrado:
                return False, f"Modelo '{self.model}' não encontrado. Disponíveis: {', '.join(nomes)}"
            
            return True, f"Conectado ao Ollama com modelo {self.model}"
        
        except requests.exceptions.ConnectionError:
            return False, f"Não foi possível conectar ao Ollama em {self.url}"
        except Exception as e:
            return False, str(e)
    
    def analisar(self, publicacoes: list[Publicacao]) -> AnaliseIA:
        """Analisa publicações usando Ollama."""
        if not publicacoes:
            return AnaliseIA('{"resumo": "Sem publicações para analisar", "situacao": "NORMAL"}')
        
        prompt = PROMPT_OLLAMA.format(
            publicacoes=self._formatar_publicacoes(publicacoes)
        )
        
        try:
            response = requests.post(
                f"{self.url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 500
                    }
                },
                timeout=60  # Ollama pode ser mais lento
            )
            
            if response.status_code == 200:
                texto = response.json().get("response", "")
                return AnaliseIA(texto)
            else:
                analise = AnaliseIA("")
                analise.erro = f"Ollama retornou HTTP {response.status_code}"
                analise.resumo = "Erro ao consultar IA"
                return analise
        
        except Exception as e:
            analise = AnaliseIA("")
            analise.erro = str(e)
            analise.resumo = "Erro ao consultar IA"
            return analise


# ============================================================
# FACTORY
# ============================================================

def get_ia_provider() -> IAProvider:
    """Retorna o provedor de IA configurado."""
    provider = config.ia_provider
    
    if provider == "gemini":
        return GeminiProvider()
    elif provider == "ollama":
        return OllamaProvider()
    else:
        raise ValueError(f"Provedor de IA desconhecido: {provider}")


# Instância global (lazy)
_provider: Optional[IAProvider] = None

def get_analyzer() -> IAProvider:
    """Retorna instância do analisador de IA."""
    global _provider
    if _provider is None:
        _provider = get_ia_provider()
    return _provider
