# google_sheets.py
"""
Módulo de Integração com Google Sheets - Bot Consulta Processual

Utiliza a API do Google Sheets via Service Account.
"""

import re
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

import gspread
from google.oauth2.service_account import Credentials

from config import config


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class ProcessoPlanilha:
    """Representa um processo na planilha."""
    numero: str
    linha: int  # Linha na planilha (1-indexed)
    aba: str    # Nome da aba/worksheet
    status_atual: Optional[str] = None
    ultima_verificacao: Optional[str] = None
    resumo_ia: Optional[str] = None


@dataclass
class AtualizacaoProcesso:
    """Dados para atualizar um processo na planilha."""
    status: str
    ultima_verificacao: str
    resumo_ia: Optional[str] = None
    ultima_publicacao: Optional[str] = None
    tipo_ultima_publicacao: Optional[str] = None


# ============================================================
# CLIENTE GOOGLE SHEETS
# ============================================================

class GoogleSheetsClient:
    """Cliente para operações no Google Sheets."""
    
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    def __init__(self):
        self._client: Optional[gspread.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None
    
    def _conectar(self):
        """Estabelece conexão com o Google Sheets."""
        if self._client is not None:
            return
        
        creds_path = config.google_credentials_path
        
        if not creds_path.exists():
            raise FileNotFoundError(
                f"Arquivo de credenciais não encontrado: {creds_path}\n"
                f"Baixe o JSON da Service Account em:\n"
                f"https://console.cloud.google.com/iam-admin/serviceaccounts"
            )
        
        creds = Credentials.from_service_account_file(
            str(creds_path),
            scopes=self.SCOPES
        )
        
        self._client = gspread.authorize(creds)
    
    def _abrir_planilha(self):
        """Abre a planilha configurada."""
        if self._spreadsheet is not None:
            return
        
        self._conectar()
        
        nome_planilha = config.google_sheet_name
        
        try:
            self._spreadsheet = self._client.open(nome_planilha)
        except gspread.SpreadsheetNotFound:
            raise ValueError(
                f"Planilha '{nome_planilha}' não encontrada.\n"
                f"Verifique se:\n"
                f"1. O nome está correto no config.json\n"
                f"2. A planilha foi compartilhada com o email da Service Account"
            )
    
    def testar_conexao(self) -> tuple[bool, str]:
        """Testa a conexão com o Google Sheets."""
        try:
            self._conectar()
            self._abrir_planilha()
            
            # Tenta listar as abas
            abas = [ws.title for ws in self._spreadsheet.worksheets()]
            
            return True, f"Conectado! Abas encontradas: {', '.join(abas)}"
        
        except FileNotFoundError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Erro ao conectar: {str(e)}"
    
    def listar_abas(self) -> list[str]:
        """Lista todas as abas da planilha."""
        self._abrir_planilha()
        return [ws.title for ws in self._spreadsheet.worksheets()]
    
    def _encontrar_coluna(self, headers: list[str], nome_coluna: str) -> Optional[int]:
        """Encontra o índice de uma coluna pelo nome (case-insensitive)."""
        nome_lower = nome_coluna.lower().replace("_", "").replace(" ", "")
        
        for i, header in enumerate(headers):
            header_lower = header.lower().replace("_", "").replace(" ", "")
            if header_lower == nome_lower:
                return i
        
        return None
    
    def _normalizar_numero_processo(self, numero: str) -> str:
        """Remove formatação do número do processo."""
        return re.sub(r'[.\-\s]', '', str(numero))
    
    def listar_processos(self, aba: str = None) -> list[ProcessoPlanilha]:
        """
        Lista todos os processos de uma aba ou de todas as abas.
        
        Args:
            aba: Nome da aba específica. Se None, lista de todas as abas.
        
        Returns:
            Lista de ProcessoPlanilha
        """
        self._abrir_planilha()
        
        processos = []
        
        if aba:
            abas = [aba]
        else:
            abas = self.listar_abas()
        
        for nome_aba in abas:
            try:
                worksheet = self._spreadsheet.worksheet(nome_aba)
                dados = worksheet.get_all_values()
                
                if not dados or len(dados) < 2:
                    continue  # Aba vazia ou só com header
                
                headers = dados[0]
                
                # Encontra índices das colunas
                col_processo = self._encontrar_coluna(headers, config.col_processo)
                col_status = self._encontrar_coluna(headers, config.col_status)
                col_verificacao = self._encontrar_coluna(headers, config.col_ultima_verificacao)
                col_resumo = self._encontrar_coluna(headers, config.col_resumo_ia)
                
                if col_processo is None:
                    if config.debug:
                        print(f"   ⚠️ Aba '{nome_aba}': coluna '{config.col_processo}' não encontrada")
                    continue
                
                # Itera pelas linhas (começando após o header)
                for i, linha in enumerate(dados[1:], start=2):
                    if col_processo >= len(linha):
                        continue
                    
                    numero = linha[col_processo].strip()
                    
                    if not numero:
                        continue
                    
                    # Ignora se não parece um número de processo
                    numero_limpo = self._normalizar_numero_processo(numero)
                    if len(numero_limpo) < 15:
                        continue
                    
                    processo = ProcessoPlanilha(
                        numero=numero,
                        linha=i,
                        aba=nome_aba,
                        status_atual=linha[col_status] if col_status is not None and col_status < len(linha) else None,
                        ultima_verificacao=linha[col_verificacao] if col_verificacao is not None and col_verificacao < len(linha) else None,
                        resumo_ia=linha[col_resumo] if col_resumo is not None and col_resumo < len(linha) else None
                    )
                    
                    processos.append(processo)
            
            except gspread.WorksheetNotFound:
                if config.debug:
                    print(f"   ⚠️ Aba '{nome_aba}' não encontrada")
            except Exception as e:
                if config.debug:
                    print(f"   ⚠️ Erro ao ler aba '{nome_aba}': {e}")
        
        return processos
    
    def atualizar_processo(
        self,
        processo: ProcessoPlanilha,
        atualizacao: AtualizacaoProcesso
    ) -> bool:
        """
        Atualiza os dados de um processo na planilha.
        
        Args:
            processo: Processo a atualizar (com linha e aba)
            atualizacao: Dados da atualização
        
        Returns:
            True se atualizou com sucesso
        """
        self._abrir_planilha()
        
        try:
            worksheet = self._spreadsheet.worksheet(processo.aba)
            headers = worksheet.row_values(1)
            
            # Encontra índices das colunas
            col_status = self._encontrar_coluna(headers, config.col_status)
            col_verificacao = self._encontrar_coluna(headers, config.col_ultima_verificacao)
            col_resumo = self._encontrar_coluna(headers, config.col_resumo_ia)
            col_ultima_pub = self._encontrar_coluna(headers, config.col_ultima_publicacao)
            col_tipo_pub = self._encontrar_coluna(headers, config.col_tipo_ultima)
            
            # Prepara as atualizações
            atualizacoes = []
            
            if col_status is not None:
                atualizacoes.append({
                    "range": gspread.utils.rowcol_to_a1(processo.linha, col_status + 1),
                    "values": [[atualizacao.status]]
                })
            
            if col_verificacao is not None:
                atualizacoes.append({
                    "range": gspread.utils.rowcol_to_a1(processo.linha, col_verificacao + 1),
                    "values": [[atualizacao.ultima_verificacao]]
                })
            
            if col_resumo is not None and atualizacao.resumo_ia is not None:
                atualizacoes.append({
                    "range": gspread.utils.rowcol_to_a1(processo.linha, col_resumo + 1),
                    "values": [[atualizacao.resumo_ia]]
                })
            
            if col_ultima_pub is not None and atualizacao.ultima_publicacao:
                atualizacoes.append({
                    "range": gspread.utils.rowcol_to_a1(processo.linha, col_ultima_pub + 1),
                    "values": [[atualizacao.ultima_publicacao]]
                })
            
            if col_tipo_pub is not None and atualizacao.tipo_ultima_publicacao:
                atualizacoes.append({
                    "range": gspread.utils.rowcol_to_a1(processo.linha, col_tipo_pub + 1),
                    "values": [[atualizacao.tipo_ultima_publicacao]]
                })
            
            # Executa atualizações em batch
            if atualizacoes:
                worksheet.batch_update(atualizacoes)
            
            return True
        
        except Exception as e:
            if config.debug:
                print(f"   ❌ Erro ao atualizar processo: {e}")
            return False


# Instância global
sheets = GoogleSheetsClient()
