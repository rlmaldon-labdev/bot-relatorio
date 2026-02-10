# config.py
"""
Módulo de Configuração - Bot Consulta Processual

Carrega configurações de:
1. config.json (principal)
2. .env (variáveis de ambiente, sobrescreve config.json)
3. Variáveis de ambiente do sistema (sobrescreve tudo)
"""

import os
import json
from pathlib import Path
from typing import Any, Optional

# Diretório base do projeto
BASE_DIR = Path(__file__).parent


def carregar_env():
    """Carrega variáveis do arquivo .env se existir."""
    env_file = BASE_DIR / ".env"
    
    if not env_file.exists():
        return
    
    with open(env_file, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            
            # Ignora comentários e linhas vazias
            if not linha or linha.startswith("#"):
                continue
            
            # Parse KEY=VALUE
            if "=" in linha:
                chave, _, valor = linha.partition("=")
                chave = chave.strip()
                valor = valor.strip()
                
                # Remove aspas se houver
                if (valor.startswith('"') and valor.endswith('"')) or \
                   (valor.startswith("'") and valor.endswith("'")):
                    valor = valor[1:-1]
                
                # Só define se não existir no ambiente
                if chave not in os.environ:
                    os.environ[chave] = valor


def carregar_config_json() -> dict:
    """Carrega configurações do config.json."""
    config_file = BASE_DIR / "config.json"
    
    if not config_file.exists():
        # Tenta config.example.json como fallback
        example_file = BASE_DIR / "config.example.json"
        if example_file.exists():
            print("⚠️  config.json não encontrado. Usando config.example.json como base.")
            print("   Copie e configure: cp config.example.json config.json")
            config_file = example_file
        else:
            return {}
    
    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


class Config:
    """Classe de configuração com acesso simplificado."""
    
    def __init__(self):
        # Carrega .env primeiro
        carregar_env()
        
        # Carrega config.json
        self._config = carregar_config_json()
    
    def get(self, *keys, default=None) -> Any:
        """
        Obtém valor da configuração com suporte a chaves aninhadas.
        
        Exemplo:
            config.get("ia", "gemini", "api_key")
            config.get("google_sheets", "nome_planilha", default="Processos")
        """
        valor = self._config
        
        for key in keys:
            if isinstance(valor, dict) and key in valor:
                valor = valor[key]
            else:
                return default
        
        return valor
    
    @property
    def debug(self) -> bool:
        """Modo debug ativo."""
        return os.getenv("DEBUG", str(self.get("debug", default=False))).lower() == "true"
    
    # ==========================================
    # Google Sheets
    # ==========================================
    
    @property
    def google_credentials_file(self) -> str:
        """Caminho do arquivo de credenciais do Google."""
        return os.getenv(
            "GOOGLE_CREDENTIALS_FILE",
            self.get("google_sheets", "arquivo_credenciais", default="credenciais.json")
        )
    
    @property
    def google_credentials_path(self) -> Path:
        """Caminho completo do arquivo de credenciais."""
        return BASE_DIR / self.google_credentials_file
    
    @property
    def google_sheet_name(self) -> str:
        """Nome da planilha no Google Sheets."""
        return os.getenv(
            "GOOGLE_SHEET_NAME",
            self.get("google_sheets", "nome_planilha", default="Controle Processual")
        )
    
    # ==========================================
    # Inteligência Artificial
    # ==========================================
    
    @property
    def ia_provider(self) -> str:
        """Provedor de IA: 'gemini' ou 'ollama'."""
        return os.getenv(
            "IA_PROVIDER",
            self.get("ia", "provedor", default="gemini")
        ).lower()
    
    @property
    def gemini_api_key(self) -> Optional[str]:
        """Chave da API do Gemini."""
        return os.getenv(
            "GEMINI_API_KEY",
            self.get("ia", "gemini", "api_key")
        )
    
    @property
    def gemini_model(self) -> str:
        """Modelo do Gemini a usar."""
        return os.getenv(
            "GEMINI_MODEL",
            self.get("ia", "gemini", "modelo", default="gemini-2.0-flash")
        )
    
    @property
    def ollama_url(self) -> str:
        """URL do servidor Ollama."""
        return os.getenv(
            "OLLAMA_URL",
            self.get("ia", "ollama", "url", default="http://localhost:11434")
        )
    
    @property
    def ollama_model(self) -> str:
        """Modelo do Ollama a usar."""
        return os.getenv(
            "OLLAMA_MODEL",
            self.get("ia", "ollama", "modelo", default="llama3.1:8b-instruct-q4_K_M")
        )
    
    # ==========================================
    # API Comunica PJe
    # ==========================================
    
    @property
    def api_url_base(self) -> str:
        """URL base da API Comunica PJe."""
        return self.get("api_comunica", "url_base", default="https://comunicaapi.pje.jus.br/api/v1")
    
    @property
    def delay_entre_consultas(self) -> int:
        """Delay em segundos entre consultas à API."""
        return int(os.getenv(
            "DELAY_ENTRE_CONSULTAS",
            self.get("api_comunica", "delay_entre_consultas", default=2)
        ))
    
    @property
    def max_publicacoes(self) -> int:
        """Máximo de publicações a analisar por processo."""
        return int(os.getenv(
            "MAX_PUBLICACOES",
            self.get("api_comunica", "max_publicacoes_analisar", default=3)
        ))
    
    @property
    def api_timeout(self) -> int:
        """Timeout para requisições à API."""
        return int(self.get("api_comunica", "timeout", default=30))
    
    # ==========================================
    # Colunas da Planilha
    # ==========================================
    
    @property
    def col_processo(self) -> str:
        return self.get("planilha", "coluna_processo", default="Processo")
    
    @property
    def col_status(self) -> str:
        return self.get("planilha", "coluna_status", default="Status_Atual")
    
    @property
    def col_ultima_verificacao(self) -> str:
        return self.get("planilha", "coluna_ultima_verificacao", default="Ultima_Verificacao")
    
    @property
    def col_resumo_ia(self) -> str:
        return self.get("planilha", "coluna_resumo_ia", default="Resumo_IA")
    
    @property
    def col_ultima_publicacao(self) -> str:
        return self.get("planilha", "coluna_ultima_publicacao", default="Ultima_Publicacao")
    
    @property
    def col_tipo_ultima(self) -> str:
        return self.get("planilha", "coluna_tipo_ultima", default="Tipo_Ultima_Publicacao")
    
    # ==========================================
    # Validação
    # ==========================================
    
    def validar(self) -> tuple[bool, list[str]]:
        """
        Valida se todas as configurações necessárias estão presentes.
        
        Returns:
            tuple: (sucesso: bool, erros: list[str])
        """
        erros = []
        
        # Verifica credenciais do Google
        if not self.google_credentials_path.exists():
            erros.append(f"Arquivo de credenciais não encontrado: {self.google_credentials_path}")
        
        # Verifica configuração de IA
        if self.ia_provider == "gemini":
            if not self.gemini_api_key or self.gemini_api_key == "SUA_CHAVE_GEMINI_AQUI":
                erros.append("Chave da API do Gemini não configurada")
        
        elif self.ia_provider == "ollama":
            # Ollama não precisa de chave, mas podemos verificar se está acessível
            pass
        
        else:
            erros.append(f"Provedor de IA inválido: {self.ia_provider}")
        
        return len(erros) == 0, erros


# Instância global
config = Config()
