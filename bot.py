#!/usr/bin/env python3
# bot.py
"""
Bot Consulta Processual - Script Principal

Consulta processos judiciais na API Comunica PJe (CNJ) e atualiza
planilha Google Sheets com resumo gerado por IA.

Uso:
    python bot.py                    # Executa consulta em todos os processos
    python bot.py --aba "Cliente X"  # Executa apenas na aba especificada
    python bot.py --teste            # Modo teste (não atualiza planilha)
    python bot.py --sem-ia           # Sem análise de IA
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime

from config import config
from api_comunica import api, ResultadoConsulta
from google_sheets import sheets, ProcessoPlanilha, AtualizacaoProcesso
from ia_analyzer import get_analyzer, AnaliseIA


def _configurar_saida_utf8():
    """Tenta configurar stdout/stderr para UTF-8 no Windows."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


_configurar_saida_utf8()


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def log(mensagem: str, nivel: str = "info"):
    """Log com timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    prefixos = {
        "info": "ℹ️",
        "ok": "✅",
        "erro": "❌",
        "aviso": "⚠️",
        "processo": "📄",
        "ia": "🤖"
    }
    
    prefixo = prefixos.get(nivel, "")
    try:
        print(f"[{timestamp}] {prefixo} {mensagem}")
    except UnicodeEncodeError:
        seguro = f"[{timestamp}] {prefixo} {mensagem}".encode("utf-8", errors="replace").decode("utf-8")
        print(seguro)


def limpar_resumo_planilha(resumo: str) -> str:
    """Gera um resumo limpo para a planilha."""
    if not resumo:
        return ""
    
    texto = resumo.strip()
    texto_lower = texto.lower()
    
    if texto.startswith("{") or "resumo" in texto_lower:
        try:
            dados = json.loads(texto)
            if isinstance(dados, dict) and "resumo" in dados:
                return str(dados["resumo"]).strip()
        except Exception:
            pass
        
        texto = re.sub(r'^[{\s]*', '', texto)
        texto = re.sub(r'}\s*$', '', texto)
        texto = re.sub(r'"?resumo"?\s*[:\-]?\s*', '', texto, flags=re.IGNORECASE)
        
        for chave in ("situacao", "prazo", "proxima_acao", "proxima acao"):
            idx = texto.lower().find(chave)
            if idx > 0:
                texto = texto[:idx].strip().rstrip(",")
                break
        
        texto = texto.strip().strip('"').strip("'")
    
    return texto


def formatar_status(resultado: ResultadoConsulta) -> str:
    """Formata status baseado no resultado da consulta."""
    if not resultado.sucesso:
        return "ERRO_CONSULTA"
    
    if resultado.total == 0:
        return "SEM_PUBLICACOES"
    
    return "ATUALIZADO"


# ============================================================
# BOT PRINCIPAL
# ============================================================

class BotConsulta:
    """Bot de consulta processual."""
    
    def __init__(self, usar_ia: bool = True, modo_teste: bool = False):
        self.usar_ia = usar_ia
        self.modo_teste = modo_teste
        self.analyzer = None
        
        if usar_ia:
            self.analyzer = get_analyzer()
    
    def verificar_configuracao(self) -> bool:
        """Verifica se todas as configurações estão corretas."""
        log("Verificando configuração...", "info")
        
        erros = []
        
        # Testa conexão com Google Sheets
        log("  Testando Google Sheets...", "info")
        ok, msg = sheets.testar_conexao()
        if ok:
            log(f"  {msg}", "ok")
        else:
            log(f"  Google Sheets: {msg}", "erro")
            erros.append(f"Google Sheets: {msg}")
        
        # Testa conexão com IA (se habilitada)
        if self.usar_ia and self.analyzer:
            log(f"  Testando IA ({config.ia_provider})...", "info")
            ok, msg = self.analyzer.testar_conexao()
            if ok:
                log(f"  {msg}", "ok")
            else:
                log(f"  IA: {msg}", "erro")
                erros.append(f"IA: {msg}")
        
        # Testa conexão com API Comunica
        log("  Testando API Comunica PJe...", "info")
        resultado = api.listar_tribunais()
        if resultado["sucesso"]:
            qtd = len(resultado["tribunais"])
            log(f"  API Comunica: {qtd} tribunais disponíveis", "ok")
        else:
            log(f"  API Comunica: {resultado['erro']}", "erro")
            erros.append(f"API Comunica: {resultado['erro']}")
        
        if erros:
            log("Configuração com erros!", "erro")
            for erro in erros:
                log(f"  - {erro}", "erro")
            return False
        
        log("Configuração OK!", "ok")
        return True
    
    def processar_processo(
        self,
        processo: ProcessoPlanilha
    ) -> tuple[ResultadoConsulta, AnaliseIA | None]:
        """
        Processa um único processo.
        
        Returns:
            tuple: (resultado_api, analise_ia)
        """
        # Consulta API
        resultado = api.consultar_processo(processo.numero)
        
        if not resultado.sucesso:
            return resultado, None
        
        if resultado.total == 0 or not resultado.publicacoes:
            return resultado, None
        
        # Analisa com IA se habilitado
        analise = None
        if self.usar_ia and self.analyzer and resultado.publicacoes:
            analise = self.analyzer.analisar(resultado.publicacoes)
        
        return resultado, analise
    
    def executar(self, aba: str = None):
        """
        Executa o bot para todos os processos.
        
        Args:
            aba: Nome da aba específica ou None para todas
        """
        log("="*60, "info")
        log("BOT CONSULTA PROCESSUAL - INICIANDO", "info")
        log("="*60, "info")
        
        # Verifica configuração
        if not self.verificar_configuracao():
            log("Abortando devido a erros de configuração.", "erro")
            return
        
        # Lista processos
        log("", "info")
        log("Carregando processos da planilha...", "info")
        
        processos = sheets.listar_processos(aba)
        
        if not processos:
            log("Nenhum processo encontrado na planilha!", "aviso")
            return
        
        # Agrupa por aba para log
        abas = {}
        for p in processos:
            if p.aba not in abas:
                abas[p.aba] = []
            abas[p.aba].append(p)
        
        log(f"Encontrados {len(processos)} processos em {len(abas)} aba(s):", "ok")
        for nome_aba, procs in abas.items():
            log(f"  - {nome_aba}: {len(procs)} processos", "info")
        
        # Processa cada processo
        log("", "info")
        log("Iniciando consultas...", "info")
        log("-"*60, "info")
        
        total = len(processos)
        sucesso = 0
        erros = 0
        sem_publicacao = 0
        
        for i, processo in enumerate(processos, 1):
            log(f"[{i}/{total}] {processo.numero}", "processo")
            log(f"        Aba: {processo.aba}", "info")
            
            # Consulta
            resultado, analise = self.processar_processo(processo)
            ultima = None
            processo_ok = False
            
            if not resultado.sucesso:
                log(f"        Erro: {resultado.erro}", "erro")
                erros += 1
                continue
            
            if resultado.total == 0:
                log(f"        Sem publicacoes encontradas", "aviso")
                sem_publicacao += 1
                status = "SEM_PUBLICACOES"
                resumo = ""
                processo_ok = True
            elif not resultado.publicacoes:
                log("        Resposta inconsistente: total > 0 mas lista vazia", "aviso")
                status = "ERRO_CONSULTA"
                resumo = ""
                erros += 1
            else:
                log(f"        Encontradas: {resultado.total} publicacoes", "ok")
                
                # Mostra ultima publicacao
                ultima = resultado.publicacoes[0]
                log(f"        Ultima: {ultima.data_formatada} - {ultima.tipo_comunicacao}", "info")
                
                # Mostra analise de IA
                if analise:
                    if analise.sucesso:
                        log(f"        IA: {analise.resumo[:80]}...", "ia")
                        log(f"        Situacao: {analise.situacao}", "ia")
                    else:
                        log(f"        IA: Erro - {analise.erro}", "aviso")
                
                status = analise.situacao if analise and analise.sucesso else "ATUALIZADO"
                resumo = analise.resumo if analise and analise.sucesso else ""
                resumo = limpar_resumo_planilha(resumo)
                processo_ok = True
            
            # Atualiza planilha (se não for modo teste)
            if not self.modo_teste:
                atualizacao = AtualizacaoProcesso(
                    status=status,
                    ultima_verificacao=datetime.now().strftime("%d/%m/%Y %H:%M"),
                    resumo_ia=resumo,
                    ultima_publicacao=ultima.data_formatada if resultado.publicacoes else None,
                    tipo_ultima_publicacao=ultima.tipo_comunicacao if resultado.publicacoes else None
                )
                
                if sheets.atualizar_processo(processo, atualizacao):
                    log(f"        Planilha atualizada", "ok")
                    if processo_ok:
                        sucesso += 1
                else:
                    log(f"        Erro ao atualizar planilha", "erro")
                    erros += 1
            else:
                log(f"        [MODO TESTE] Planilha não atualizada", "aviso")
                if processo_ok:
                    sucesso += 1
            
            # Rate limit info
            if resultado.rate_limit_remaining is not None:
                log(f"        Rate limit: {resultado.rate_limit_remaining}/{resultado.rate_limit_total}", "info")
            
            log("", "info")
        
        # Resumo final
        log("-"*60, "info")
        log("RESUMO DA EXECUÇÃO", "info")
        log("-"*60, "info")
        log(f"  Total processado: {total}", "info")
        log(f"  Sucesso: {sucesso}", "ok")
        log(f"  Sem publicações: {sem_publicacao}", "aviso")
        log(f"  Erros: {erros}", "erro" if erros > 0 else "info")
        
        if self.modo_teste:
            log("", "info")
            log("  ⚠️ MODO TESTE - Planilha não foi alterada", "aviso")
        
        log("="*60, "info")
        log("BOT CONSULTA PROCESSUAL - FINALIZADO", "info")
        log("="*60, "info")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Bot Consulta Processual - Monitora processos judiciais"
    )
    
    parser.add_argument(
        "--aba",
        type=str,
        default=None,
        help="Nome da aba específica para processar (default: todas)"
    )
    
    parser.add_argument(
        "--teste",
        action="store_true",
        help="Modo teste - não atualiza a planilha"
    )
    
    parser.add_argument(
        "--sem-ia",
        action="store_true",
        help="Desabilita análise de IA"
    )
    
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="NÃ£o aguarda Enter ao final (uso em automaÃ§Ãµes)"
    )
    
    args = parser.parse_args()
    
    bot = BotConsulta(
        usar_ia=not args.sem_ia,
        modo_teste=args.teste
    )
    
    bot.executar(aba=args.aba)
    return args

if __name__ == "__main__":
    args = main()
    if not args.no_prompt and sys.stdin.isatty():
        print("\nPressione Enter para sair...")
        input()
