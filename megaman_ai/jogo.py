from threading import Thread
import subprocess
import shlex
import time
import socket
import json
import os
import cv2
import numpy
import yaml
from .comuns import sttinf, sttwrn
from . import inteligencia, visao

# TODO: Usar um "whereis" para encontrar o caminho do executável do emulador
# TODO: É obrigatório passar o arquivo com os sprites para modo jogar
# TODO: Implemetar tradução de indice de predict para ação

class Jogo:

    def __init__(self, room, sprites, fceux="/usr/games/fceux", 
            fceux_script="server.lua", carregar_pre=False, time_steps=10):
        self.room = room
        self.classes = self._getClasses(sprites)
        self.comandos = self._getComandos(sprites)
        self.fceux = fceux
        self.fceux_script = os.path.abspath(fceux_script)
        self._emulador = Thread(target=self._iniciarEmulador)
        self._conexao = None
        self._conectado = False
        self._caminhoFrame = "/tmp/.megamanAI.screen"
        self._winScala = 2
        self._time_steps = time_steps
        self.repeticoesA = 0
        self.repeticoesB = 0

    def iniciar(self):
        # inicia o emulador
        self._emulador.start()
        print("[{}] Emulador iniciado".format(sttinf))

        # conecta ao emulador
        self._conectar()

        print("[{}] Iniciando modo jogar".format(sttinf))
        # executa a função jogar
        self._jogar()
        
        # verifica se o emulador continua ativo (caso tenha dado algum erro com o servidor)
        if self._emulador.isAlive():
            print("[{}] Emulador continua ativo! main-(join)->emulador".format(sttwrn))
            # join no emulador
            self._emulador.join()

        print("[{}] Fim modo jogo".format(sttwrn))

    def obterFrame(self):
        """Obtém o frame atual do emulador"""
        try:
            # Recebe uma mensagem de 'pode ler a tela'
            self._conexao.recv(4096)
            
            # entra em loop tentando ler o arquivo de frame
            frame = None
            
            while frame is None:
                frame = cv2.imread(self._caminhoFrame)
            
            return frame

        except ConnectionResetError:
            print("[{}] Conexão fechada pelo servidor".format(sttwrn))
            self._conectado = False

    def _jogar(self):
        """ Joga o game"""
        mem = [numpy.zeros(2016) for _ in range(self._time_steps-1)]

        # enquanto o emulador estiver ativo E conectado
        while self._emulador.isAlive() and self._conectado:

            while len(mem) < self._time_steps:
                frame = self.obterFrame()
                
                cv2.imshow("Jogo", cv2.resize(frame, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST))
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                if not frame is None:
                    for s in (0.5, 0.5, 0.75):
                        frame = cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_BITS)
                    frame[frame <= 40] = 0
                    mem.append(frame.flatten())
            
            acao = inteligencia.modelo.predict(numpy.array([mem]))
            classe = numpy.argmax(acao[0])
            
            print("=> {:20.20}: {:06.2f}%".format(self.classes[classe], acao[0][classe]*100))
            
            comando = self.comandos[classe].copy()
            # trata o problema do 'A' pressionado infinitamente
            if "A" in comando:
                self.repeticoesA += 1    
                if self.repeticoesA > 20:
                    del comando["A"]
                    self.repeticoesA = 0
            else:
                self.repeticoesA = 0
            
            # trata o problema do 'A' pressionado infinitamente
            if "B" in comando:
                self.repeticoesB += 1    
                if self.repeticoesB > 5:
                    del comando["B"]
                    self.repeticoesB = 0
            else:
                self.repeticoesB = 0
            
            
            # envia o comando para o emulador
            self._enviarComando(comando)
            
            if (cv2.waitKey(1) & 0xFF) == ord('q'):
                cv2.destroyAllWindows() 
                self._emulador.join()
            
            del mem[0]

    def _iniciarEmulador(self):
        """Inicia a thread do emulador com os parâmetros passados"""

        # define o comando
        comando = shlex.split("{fceux} --nogui {room} --xscale {escala} --yscale {escala} --loadlua {fceux_script}".format(
            fceux=self.fceux,
            room=self.room,
            escala=self._winScala,
            fceux_script=self.fceux_script))

        # executa, essa chamada trava a thread até o fim da execução
        processo = subprocess.run(
            comando,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL)

        # verifica o código de saída do comando
        if processo.returncode == 0:
            print("[{}] Emulador finalizado normalmente".format(sttinf))
        else:
            print("[{}] Houve algum erro na execução do emulador".format(sttwrn))

    def _conectar(self):
        """Se conecta ao emulador"""
        tentativas = 10

        while tentativas > 0:
            try:
        
                # Espera um tempinho para dar tempo de começar a executar o servidor
                time.sleep(1)

                # tenta se conectar
                self._conexao = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._conexao.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self._conexao.connect(("127.0.0.1", 4321))
                
                self._conectado = True
                print("[{}] Conectado ao emulador".format(sttinf), end="")
                break

            except ConnectionRefusedError:
                tentativas -= 1
                print(".", end="")
        
        print("")
        
        if tentativas == 0:
            print("[{}] Conexão recusada pelo emulador.".format(sttwrn))

    def _enviarComando(self, comando):
        """Envia um comando para o emulador em formato JSON, o comando deve estar 
        na forma de dicionário."""
        try:
            self._conexao.send((json.dumps(comando)+"\n").encode())
        
        except BrokenPipeError:
            print("[{}] Conexão fechada pelo servidor".format(sttwrn))
            self._conectado = False

    def _getClasses(self, sprites):
        classes = []
        for s in list(yaml.load(open(sprites, "r").read())['estados'].keys()):
            classes.append(s+"-l")
            classes.append(s+"-r")
        return classes
    
    def _getComandos(self, sprites):
        sprites = yaml.load(open(sprites, "r").read())
        comandos = []

        for estado in sprites['estados']:
            comando = sprites['estados'][estado]['comando']

            if comando is None:
                comandos.append({})
                comandos.append({})
                continue
            
            comandos.append(dict().fromkeys(comando, True))
            
            if 'left' in comando:
                comando[comando.index('left')] = 'right'
                comandos.append(dict().fromkeys(comando, True))
            else:
                comandos.append(dict().fromkeys(comando, True))
        return comandos