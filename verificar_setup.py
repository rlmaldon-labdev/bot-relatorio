#!/usr/bin/env python3
# verificar_setup.py
"""
Verificador de Setup - Bot Consulta Processual

Verifica se todas as dependências e configurações estão corretas
antes de executar o bot.
"""

import sys
from pathlib import Path


def verificar_python():
    """Verifica versão do Python."""
    print("🐍 Verificando Python...")
    
    versao = sys.version_info
    if versao.major < 3 or (versao.major == 3 and versao.minor < 10):
        print(f"   ❌ Python 3.10+ necessário. Atual: {versao.major}.{versao.minor}")
        return False
    
    print(f"   ✅ Python {versao.major}.{versao.minor}.{versao.micro}")
    return True


def verificar_dependencias():
    """Verifica se as bibliotecas necessárias estão instaladas."""
    print("\n📦 Verificando dependências...")
    
    dependencias = {
        "requests": "requests",
        "gspread": "gspread",
        "google.oauth2": "google-auth",
    }
    
    faltando = []
    
    for modulo, pacote in dependencias.items():
        try:
            __import__(modulo)
            print(f"   ✅ {pacote}")
        except ImportError:
            print(f"   ❌ {pacote} - NÃO INSTALADO")
            faltando.append(pacote)
    
    if faltando:
        print(f"\n   💡 Instale com: pip install {' '.join(faltando)}")
        return False
    
    return True


def verificar_arquivos():
    """Verifica se os arquivos de configuração existem."""
    print("\n📁 Verificando arquivos...")
    
    base = Path(__file__).parent
    
    arquivos = {
        "config.json": "Configuração principal",
        "credenciais.json": "Credenciais Google (Service Account)",
    }
    
    faltando = []
    
    for arquivo, descricao in arquivos.items():
        caminho = base / arquivo
        if caminho.exists():
            print(f"   ✅ {arquivo}")
        else:
            print(f"   ❌ {arquivo} - {descricao}")
            faltando.append(arquivo)
    
    if "config.json" in faltando:
        print(f"\n   💡 Copie o template: cp config.example.json config.json")
    
    if "credenciais.json" in faltando:
        print(f"\n   💡 Baixe as credenciais da Service Account em:")
        print(f"      https://console.cloud.google.com/iam-admin/serviceaccounts")
    
    return len(faltando) == 0


def verificar_configuracao():
    """Verifica se a configuração é válida."""
    print("\n⚙️ Verificando configuração...")
    
    try:
        from config import config
        
        ok, erros = config.validar()
        
        if ok:
            print(f"   ✅ Configuração válida")
            print(f"   📊 Planilha: {config.google_sheet_name}")
            print(f"   🤖 IA: {config.ia_provider}")
            return True
        else:
            for erro in erros:
                print(f"   ❌ {erro}")
            return False
    
    except Exception as e:
        print(f"   ❌ Erro ao carregar configuração: {e}")
        return False


def verificar_conexoes():
    """Verifica conexões com APIs."""
    print("\n🌐 Verificando conexões...")
    
    # API Comunica
    print("   Testando API Comunica PJe...")
    try:
        from api_comunica import api
        resultado = api.listar_tribunais()
        if resultado["sucesso"]:
            print(f"   ✅ API Comunica: {len(resultado['tribunais'])} tribunais")
        else:
            print(f"   ❌ API Comunica: {resultado['erro']}")
    except Exception as e:
        print(f"   ❌ API Comunica: {e}")
    
    # Google Sheets
    print("   Testando Google Sheets...")
    try:
        from google_sheets import sheets
        ok, msg = sheets.testar_conexao()
        if ok:
            print(f"   ✅ Google Sheets: Conectado")
        else:
            print(f"   ❌ Google Sheets: {msg}")
    except Exception as e:
        print(f"   ❌ Google Sheets: {e}")
    
    # IA
    print("   Testando IA...")
    try:
        from ia_analyzer import get_analyzer
        from config import config
        
        analyzer = get_analyzer()
        ok, msg = analyzer.testar_conexao()
        
        if ok:
            print(f"   ✅ IA ({config.ia_provider}): Conectado")
        else:
            print(f"   ⚠️ IA ({config.ia_provider}): {msg}")
            print(f"      (O bot pode rodar sem IA usando --sem-ia)")
    except Exception as e:
        print(f"   ⚠️ IA: {e}")


def main():
    print("="*60)
    print("🔍 VERIFICADOR DE SETUP - Bot Consulta Processual")
    print("="*60)
    
    etapas = [
        ("Python", verificar_python),
        ("Dependências", verificar_dependencias),
        ("Arquivos", verificar_arquivos),
        ("Configuração", verificar_configuracao),
    ]
    
    todas_ok = True
    
    for nome, func in etapas:
        if not func():
            todas_ok = False
            print(f"\n⛔ Setup incompleto. Corrija os erros acima.")
            break
    
    if todas_ok:
        verificar_conexoes()
        
        print("\n" + "="*60)
        print("✅ SETUP COMPLETO!")
        print("="*60)
        print("\nPróximos passos:")
        print("  1. Execute: python bot.py --teste")
        print("     (para testar sem alterar a planilha)")
        print("  2. Execute: python bot.py")
        print("     (para executar normalmente)")
        input("\nPressione Enter para encerrar...")
    else:
        print("\n" + "="*60)
        print("❌ SETUP INCOMPLETO")
        print("="*60)
        input("\nPressione Enter para encerrar...")
        sys.exit(1)


if __name__ == "__main__":
    main()
