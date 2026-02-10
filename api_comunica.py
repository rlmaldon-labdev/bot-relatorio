# api_comunica.py
"""
Módulo de Integração com API Comunica PJe (CNJ)
Diário de Justiça Eletrônico Nacional e Plataforma de Editais

API Pública - Não requer autenticação
Swagger: https://comunicaapi.pje.jus.br/swagger/index.html
"""

import re
import time
import requests
from html import unescape
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from config import config


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class Publicacao:
    """Representa uma publicação do diário."""
    id: int
    data_disponibilizacao: str
    tipo_comunicacao: str
    sigla_tribunal: str
    nome_orgao: str
    classe: str
    texto: str
    numero_processo: str
    meio: str
    hash: str
    advogados: list[dict]
    destinatarios: list[dict]
    
    @property
    def data_formatada(self) -> str:
        """Data no formato dd/mm/yyyy."""
        if self.data_disponibilizacao and len(self.data_disponibilizacao) >= 10:
            try:
                data = datetime.strptime(self.data_disponibilizacao[:10], "%Y-%m-%d")
                return data.strftime("%d/%m/%Y")
            except:
                pass
        return self.data_disponibilizacao or "???"
    
    @property
    def texto_limpo(self) -> str:
        """Texto sem HTML e formatação excessiva."""
        return limpar_html(self.texto)


@dataclass
class ResultadoConsulta:
    """Resultado de uma consulta à API."""
    sucesso: bool
    publicacoes: list[Publicacao]
    total: int
    erro: Optional[str] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_total: Optional[int] = None


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def limpar_html(texto: str) -> str:
    """Remove tags HTML e limpa o texto."""
    if not texto:
        return ""
    
    # Decodifica entidades HTML (&nbsp;, &Ccedil;, etc.)
    texto = unescape(texto)
    
    # Remove tags HTML
    texto = re.sub(r'<[^>]+>', ' ', texto)
    
    # Remove múltiplos espaços e quebras de linha
    texto = re.sub(r'\s+', ' ', texto)
    
    # Remove espaços no início e fim
    texto = texto.strip()
    
    return texto


def extrair_info_tribunal(numero_processo: str) -> dict:
    """Extrai informações do tribunal pelo número CNJ."""
    numero_limpo = re.sub(r'[.\-\s]', '', numero_processo)
    
    if len(numero_limpo) != 20:
        return {"justica": None, "tribunal": None, "sigla": None}
    
    justica = numero_limpo[13]
    tribunal = numero_limpo[14:16]
    
    siglas_estadual = {
        "01": "TJAC", "02": "TJAL", "03": "TJAP", "04": "TJAM", "05": "TJBA",
        "06": "TJCE", "07": "TJDFT", "08": "TJES", "09": "TJGO", "10": "TJMA",
        "11": "TJMT", "12": "TJMS", "13": "TJMG", "14": "TJPA", "15": "TJPB",
        "16": "TJPR", "17": "TJPE", "18": "TJPI", "19": "TJRJ", "20": "TJRN",
        "21": "TJRS", "22": "TJRO", "23": "TJRR", "24": "TJSC", "25": "TJSE",
        "26": "TJSP", "27": "TJTO",
    }
    
    sigla = None
    justica_nome = None
    
    if justica == "8":
        justica_nome = "Estadual"
        sigla = siglas_estadual.get(tribunal)
    elif justica == "5":
        justica_nome = "Trabalho"
        sigla = f"TRT{int(tribunal)}"
    elif justica == "4":
        justica_nome = "Federal"
        sigla = f"TRF{int(tribunal)}"
    
    return {
        "justica": justica_nome,
        "codigo_tribunal": tribunal,
        "sigla": sigla
    }


# ============================================================
# CLIENTE DA API
# ============================================================

class APIComunica:
    """Cliente para a API Comunica PJe."""
    
    def __init__(self):
        self.url_base = config.api_url_base
        self.timeout = config.api_timeout
        self.delay = config.delay_entre_consultas
        self._ultimo_request = 0
        
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "BotConsultaProcessual/1.0"
        }
    
    def _aguardar_rate_limit(self):
        """Aguarda tempo mínimo entre requisições."""
        agora = time.time()
        tempo_passado = agora - self._ultimo_request
        
        if tempo_passado < self.delay:
            time.sleep(self.delay - tempo_passado)
        
        self._ultimo_request = time.time()
    
    def _parse_publicacao(self, item: dict) -> Publicacao:
        """Converte item da API em objeto Publicacao."""
        # Extrai advogados
        advogados = []
        for adv_item in item.get("destinatarioadvogados", []):
            adv = adv_item.get("advogado", {})
            if adv:
                advogados.append({
                    "nome": adv.get("nome", ""),
                    "oab": adv.get("numero_oab", ""),
                    "uf": adv.get("uf_oab", "")
                })
        
        # Extrai destinatários
        destinatarios = []
        for dest in item.get("destinatarios", []):
            destinatarios.append({
                "nome": dest.get("nome", ""),
                "polo": dest.get("polo", "")
            })
        
        return Publicacao(
            id=item.get("id", 0),
            data_disponibilizacao=item.get("data_disponibilizacao", item.get("datadisponibilizacao", "")),
            tipo_comunicacao=item.get("tipoComunicacao", ""),
            sigla_tribunal=item.get("siglaTribunal", ""),
            nome_orgao=item.get("nomeOrgao", ""),
            classe=item.get("nomeClasse", ""),
            texto=item.get("texto", ""),
            numero_processo=item.get("numero_processo", item.get("numeroprocessocommascara", "")),
            meio=item.get("meiocompleto", item.get("meio", "")),
            hash=item.get("hash", ""),
            advogados=advogados,
            destinatarios=destinatarios
        )
    
    def consultar_processo(
        self,
        numero_processo: str,
        max_resultados: int = None
    ) -> ResultadoConsulta:
        """
        Consulta publicações de um processo.
        
        Args:
            numero_processo: Número do processo (qualquer formato)
            max_resultados: Máximo de publicações a retornar
        
        Returns:
            ResultadoConsulta com as publicações encontradas
        """
        if max_resultados is None:
            max_resultados = config.max_publicacoes
        
        # Limpa o número
        numero_limpo = re.sub(r'[.\-\s]', '', numero_processo)
        
        url = f"{self.url_base}/comunicacao"
        params = {
            "numeroProcesso": numero_limpo,
            "pagina": 1,
            "itensPorPagina": 100  # Máximo permitido pela API
        }
        
        # Aplica rate limit
        self._aguardar_rate_limit()
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=self.timeout
            )
            
            # Captura headers de rate limit
            rate_remaining = response.headers.get("x-ratelimit-remaining")
            rate_total = response.headers.get("x-ratelimit-limit")
            
            if response.status_code == 200:
                dados = response.json()
                items = dados.get("items", [])
                total = dados.get("count", len(items))
                
                # Converte para objetos Publicacao
                publicacoes = []
                for item in items[:max_resultados]:
                    publicacoes.append(self._parse_publicacao(item))
                
                return ResultadoConsulta(
                    sucesso=True,
                    publicacoes=publicacoes,
                    total=total,
                    rate_limit_remaining=int(rate_remaining) if rate_remaining else None,
                    rate_limit_total=int(rate_total) if rate_total else None
                )
            
            elif response.status_code == 429:
                return ResultadoConsulta(
                    sucesso=False,
                    publicacoes=[],
                    total=0,
                    erro="Rate limit atingido. Aguarde 1 minuto.",
                    rate_limit_remaining=0,
                    rate_limit_total=int(rate_total) if rate_total else None
                )
            
            elif response.status_code == 422:
                return ResultadoConsulta(
                    sucesso=False,
                    publicacoes=[],
                    total=0,
                    erro="Erro nos parâmetros da consulta (422)"
                )
            
            else:
                return ResultadoConsulta(
                    sucesso=False,
                    publicacoes=[],
                    total=0,
                    erro=f"HTTP {response.status_code}: {response.text[:200]}"
                )
        
        except requests.exceptions.Timeout:
            return ResultadoConsulta(
                sucesso=False,
                publicacoes=[],
                total=0,
                erro="Timeout na requisição"
            )
        
        except Exception as e:
            return ResultadoConsulta(
                sucesso=False,
                publicacoes=[],
                total=0,
                erro=str(e)
            )
    
    def listar_tribunais(self) -> dict:
        """Lista todos os tribunais disponíveis."""
        url = f"{self.url_base}/comunicacao/tribunal"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            
            if response.status_code == 200:
                return {"sucesso": True, "tribunais": response.json()}
            else:
                return {"sucesso": False, "erro": f"HTTP {response.status_code}"}
        
        except Exception as e:
            return {"sucesso": False, "erro": str(e)}


# Instância global
api = APIComunica()
