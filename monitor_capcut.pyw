import argparse
import os
import sys
import time
from datetime import datetime, timedelta

import psutil

# --- ADAPTAÇÃO PARA EXECUTÁVEL ---
# Verifica se está rodando como um .exe compilado pelo PyInstaller
if getattr(sys, 'frozen', False):
    # Pega a pasta onde o .exe está localizado
    DIRETORIO_BASE = os.path.dirname(sys.executable)
else:
    # Pega a pasta onde o script .py está localizado
    DIRETORIO_BASE = os.path.dirname(os.path.abspath(__file__))
# ---------------------------------

DEFAULT_PROCESS_NAME = "capcut.exe" if sys.platform.startswith("win") else "CapCut"
# O log agora sempre será salvo na mesma pasta do programa
DEFAULT_LOG_FILE = os.path.join(DIRETORIO_BASE, "tempo_uso_capcut.txt")
DEFAULT_POLL_INTERVAL = 5


def parse_args():
    parser = argparse.ArgumentParser(
        description="Monitora um processo e grava sessões de uso em arquivo de log."
    )
    parser.add_argument(
        "--processo",
        "-p",
        default=DEFAULT_PROCESS_NAME,
        help="Nome do processo a monitorar (ex.: capcut.exe).",
    )
    parser.add_argument(
        "--log",
        "-l",
        default=DEFAULT_LOG_FILE,
        help="Arquivo de log onde serão gravadas as sessões.",
    )
    parser.add_argument(
        "--intervalo",
        "-i",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help="Intervalo de checagem em segundos.",
    )
    return parser.parse_args()


def garantir_diretorio_existente(caminho_arquivo):
    caminho_dir = os.path.dirname(os.path.abspath(caminho_arquivo))
    if caminho_dir and not os.path.exists(caminho_dir):
        os.makedirs(caminho_dir, exist_ok=True)


def verificar_processos_abertos(nome_processo):
    """Retorna a quantidade de processos em execução que casam com o nome informado."""
    contador = 0
    for proc in psutil.process_iter(["name"]):
        try:
            nome = proc.info["name"]
            if nome and nome_processo.lower() in nome.lower():
                contador += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return contador


WEEKDAYS_PT = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]

MONTHS_PT = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}

MONTHS_PT_INVERSE = {v: k for k, v in MONTHS_PT.items()}


def formatar_duracao(segundos):
    """Formata a duração como H:MM:SS."""
    return str(timedelta(seconds=int(segundos)))


def data_por_extenso(dt):
    return f"{WEEKDAYS_PT[dt.weekday()]}, {dt.day} de {MONTHS_PT[dt.month]} de {dt.year}"


def data_hora_por_extenso(dt):
    return f"{data_por_extenso(dt)} às {dt:%H:%M:%S}"


def parse_data_por_extenso(texto):
    if ", " in texto:
        texto = texto.split(", ", 1)[1]

    if " às " not in texto:
        raise ValueError("Formato de data inválido")

    data_texto, hora_texto = texto.split(" às ", 1)
    partes = data_texto.split(" de ")
    if len(partes) != 3:
        raise ValueError("Formato de data inválido")

    dia = int(partes[0])
    mes = MONTHS_PT_INVERSE[partes[1].lower()]
    ano = int(partes[2])
    hora, minuto, segundo = map(int, hora_texto.split(":"))
    return datetime(ano, mes, dia, hora, minuto, segundo)


def agora_formatado():
    return data_hora_por_extenso(datetime.now())


def gravar_log(linha, arquivo_log):
    garantir_diretorio_existente(arquivo_log)
    try:
        with open(arquivo_log, "a", encoding="utf-8") as arquivo:
            arquivo.write(linha)
    except OSError as exc:
        print(f"Erro ao gravar no arquivo de log: {exc}", file=sys.stderr)


def resumir_log(arquivo_log):
    if not os.path.exists(arquivo_log):
        return 0

    total_segundos = 0
    try:
        with open(arquivo_log, "r", encoding="utf-8") as arquivo:
            for linha in arquivo:
                if "Tempo de uso:" in linha:
                    trecho = linha.split("Tempo de uso:", 1)[1].strip()
                    try:
                        partes = trecho.replace(")", "").split(":")
                        if len(partes) == 3:
                            horas, minutos, segundos = map(int, partes)
                            total_segundos += horas * 3600 + minutos * 60 + segundos
                    except ValueError:
                        continue
    except OSError:
        return 0

    return total_segundos


def resumir_log_por_data(arquivo_log, data_alvo):
    if not os.path.exists(arquivo_log):
        return 0

    total_segundos = 0
    try:
        with open(arquivo_log, "r", encoding="utf-8") as arquivo:
            for linha in arquivo:
                if "encerrado em " in linha and "Tempo de uso:" in linha:
                    try:
                        data_texto = linha.split("encerrado em ", 1)[1].split(" (Tempo de uso:", 1)[0].strip()
                        data_fim = parse_data_por_extenso(data_texto)
                    except (ValueError, KeyError, IndexError):
                        continue

                    if data_fim.date() == data_alvo.date():
                        trecho = linha.split("Tempo de uso:", 1)[1].strip()
                        try:
                            partes = trecho.replace(")", "").split(":")
                            if len(partes) == 3:
                                horas, minutos, segundos = map(int, partes)
                                total_segundos += horas * 3600 + minutos * 60 + segundos
                        except ValueError:
                            continue
    except OSError:
        return 0

    return total_segundos


def main():
    args = parse_args()
    processo = args.processo
    arquivo_log = os.path.abspath(args.log)
    intervalo = max(1, args.intervalo)

    print(f"Iniciando monitoramento do processo: {processo}")
    print(f"Arquivo de log: {arquivo_log}")
    print(f"Intervalo de verificação: {intervalo} segundos")
    print("Pressione Ctrl+C para encerrar.\n")

    tempo_inicio = None
    processo_ativo = False
    total_acumulado = resumir_log(arquivo_log)
    total_hoje = resumir_log_por_data(arquivo_log, datetime.now())

    if total_acumulado:
        print(f"Total de uso registrado até agora: {formatar_duracao(total_acumulado)}")

    if total_hoje:
        print(
            f"Total de uso hoje ({data_por_extenso(datetime.now())}): {formatar_duracao(total_hoje)}\n"
        )

    while True:
        quantidade = verificar_processos_abertos(processo)
        esta_rodando = quantidade > 0

        if esta_rodando and not processo_ativo:
            processo_ativo = True
            tempo_inicio = time.time()
            agora = agora_formatado()
            linha_aberto = f"{processo} aberto em {agora} ({quantidade} instância(s))\n"
            gravar_log(linha_aberto, arquivo_log)
            print(linha_aberto.strip())

        elif not esta_rodando and processo_ativo:
            processo_ativo = False
            tempo_fim = time.time()
            duracao_sessao = tempo_fim - tempo_inicio
            tempo_formatado = formatar_duracao(duracao_sessao)
            agora = agora_formatado()
            linha_fechado = (
                f"{processo} encerrado em {agora} (Tempo de uso: {tempo_formatado})\n\n"
            )
            gravar_log(linha_fechado, arquivo_log)
            print(linha_fechado.strip())

            total_hoje = resumir_log_por_data(arquivo_log, datetime.now())
            print(
                f"Total de uso hoje ({data_por_extenso(datetime.now())}): {formatar_duracao(total_hoje)}\n"
            )

        time.sleep(intervalo)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitoramento encerrado pelo usuário.")
    except Exception as exc:
        print(f"Erro inesperado: {exc}", file=sys.stderr)
        # Manter a janela do console aberta caso ocorra um erro (útil para debugar o .exe)
        input("Pressione Enter para fechar...")
        raise