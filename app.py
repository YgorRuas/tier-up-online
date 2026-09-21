from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import random
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave_secreta_tier_up'
socketio = SocketIO(app, cors_allowed_origins="*")

jogadores = {}
partida_atual = {}
placar_geral = {}
rodada_atual = 0

with open('temas.json', 'r', encoding='utf-8') as ficheiro:
    temas = json.load(ficheiro)

niveis_disponiveis = ["S", "A", "B", "C", "F"]


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('entrar_jogo')
def handle_entrar_jogo(nome):
    nome = nome.strip()
    if nome != "":
        jogadores[request.sid] = nome
        if nome not in placar_geral:
            placar_geral[nome] = 0

    emit('atualizar_lista', list(jogadores.values()), broadcast=True)


@socketio.on('iniciar_partida')
def iniciar_partida():
    global rodada_atual, placar_geral

    if len(jogadores) > 0:
        if rodada_atual >= 10:
            rodada_atual = 0
            # SOLUÇÃO FANTASMA: Limpa o placar e recria apenas para quem está conectado agora
            placar_geral.clear()
            for sid, nome in jogadores.items():
                placar_geral[nome] = 0

        rodada_atual += 1
        partida_atual.clear()

        tema_escolhido = random.choice(temas)
        qtd_jogadores = min(len(jogadores), 5)
        niveis_embaralhados = random.sample(niveis_disponiveis, qtd_jogadores)

        emit('jogo_iniciado', {'tema': tema_escolhido,
             'rodada': rodada_atual}, broadcast=True)

        i = 0
        for sid in jogadores.keys():
            if i < len(niveis_embaralhados):
                letra = niveis_embaralhados[i]
                partida_atual[sid] = {'nivel': letra}
                emit('receber_nivel_secreto', letra, room=sid)
                i += 1


@socketio.on('enviar_resposta')
def handle_resposta(resposta_texto):
    sid_jogador = request.sid
    if sid_jogador in partida_atual:
        partida_atual[sid_jogador]['resposta'] = resposta_texto.strip()

    respostas_dadas = [d for d in partida_atual.values() if 'resposta' in d]
    if len(respostas_dadas) == len(partida_atual):
        lista_respostas = [d['resposta'] for d in respostas_dadas]
        random.shuffle(lista_respostas)
        emit('fase_debate', lista_respostas, broadcast=True)


@socketio.on('movimento_tabuleiro')
def handle_atualizar_tabuleiro(estado_tabuleiro):
    emit('tabuleiro_sincronizado', estado_tabuleiro,
         broadcast=True, include_self=False)


@socketio.on('finalizar_debate')
def handle_finalizar(estado_final):
    global placar_geral, rodada_atual
    detalhes = []

    # SOLUÇÃO DO NULL: Cria um "gabarito" em letras minúsculas e sem espaços acidentais
    gabarito = {dados['resposta'].strip().lower(): dados['nivel']
                for dados in partida_atual.values() if 'resposta' in dados}
    autores = {dados['resposta'].strip().lower(): jogadores[sid]
               for sid, dados in partida_atual.items() if 'resposta' in dados}

    for tier_id, palavras in estado_final.items():
        if tier_id == 'banco-palavras':
            continue
        letra_tier = tier_id.split('-')[1].upper()

        for palavra in palavras:
            # Na hora de procurar, converte também para minúsculas e retira os espaços acidentais
            palavra_procura = palavra.strip().lower()

            nivel_real = gabarito.get(palavra_procura)
            autor = autores.get(palavra_procura)
            correto = (nivel_real == letra_tier)

            if correto and autor:
                if autor in placar_geral:
                    placar_geral[autor] += 1

            detalhes.append({
                # Mostra no ecrã a palavra original (como foi escrita)
                'palavra': palavra,
                'autor': autor if autor else "Erro de leitura",
                'nivel_real': nivel_real if nivel_real else "?",
                'onde_foi_colocado': letra_tier,
                'correto': correto
            })

    resultado = {
        'detalhes': detalhes,
        'placar': placar_geral,
        'rodada': rodada_atual,
        'fim_de_jogo': rodada_atual >= 10
    }

    emit('mostrar_resultado', resultado, broadcast=True)


@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in jogadores:
        del jogadores[request.sid]
        if request.sid in partida_atual:
            del partida_atual[request.sid]
        emit('atualizar_lista', list(jogadores.values()), broadcast=True)


if __name__ == '__main__':
    socketio.run(app, debug=True)
