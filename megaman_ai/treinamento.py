""" 
treinamento.py
Classes de execução do treinamento da rede neural a partir dos videos.
"""

# * Treinando frame a frame
# TODO: A contagem das estatísticas estão erradas. Consertar.

import cv2
import numpy
import yaml
import os
import timeit
from datetime import datetime

from . import inteligencia, visao

class Treinamento:
    """Armazena informações sobre uma instancia de treinamento
    incluindo estatísticas sobre o andamento do treinamento."""

    def __init__(self, videos, sprites, **kwargs):
        self.videos = videos
        self.visao = visao.MegaMan(sprites)
        self.tempo = kwargs.get("tempo", False)
        self.exibir = kwargs.get("exibir", False)
        self.qualidade = kwargs.get("qualidade", False)
        self.epochs = kwargs.get("epochs", 50)
        self.batch_size = kwargs.get("batch_size", 100)
        self.nome = kwargs.pop("nome")
        self._frameAnterior = None, -1
        self._s = [],[]
        self._rodada = 0
        self._log = open("logs/"+self.nome+".log", "a")

    def iniciar(self):
        """Inicia o treinamento em todos os videos"""
        
        self._exibirInfoInicioTreino()

        for video in self.videos:

            # Abre o video
            videoCapture = cv2.VideoCapture(video)

            # Exibe algumas informações antes do inicio do treinamento
            self._exibirInfosInicioVideo(video)

            try:
                # Chama a função de treinamento para o video atual
                self._treinar(videoCapture)
                print("\n")
            # Trata o caso de iterrupção pelo usuário via teclado
            # Para salvar o progresso do video
            except KeyboardInterrupt:
                print("Iterrompido pelo usuário.")

            # Exibe informações no fim do treinamento
            self._exibirInfosFimVideo(video)
            
            # Salva modelo
            inteligencia.salvar()
        
        self._exibirInfoFimTreino()

    def _exibirInfosFimVideo(self, video):
        """Exibe algumas informações antes do treinamento com o video"""
        print("Fim de treinamento com o vídeo: {}".format(video))

    def _exibirInfosInicioVideo(self, video):
        """Exibe algumas informações depois do treinamento com o video"""
        print("Iniciando Treino: {}".format(video))

    def _exibirInfoInicioTreino(self):
        print("""
  __  __                  __  __                  _    ___ 
 |  \/  | ___  __ _  __ _|  \/  | __ _ _ __      / \  |_ _|
 | |\/| |/ _ \/ _` |/ _` | |\/| |/ _` | '_ \    / _ \  | | 
 | |  | |  __/ (_| | (_| | |  | | (_| | | | |  / ___ \ | | 
 |_|  |_|\___|\__, |\__,_|_|  |_|\__,_|_| |_| /_/   \_\___|
              |___/                                        
    
    Iniciando treinamento... 
    Videos: {}
    Batch Size: {}
    Epochs: {}
    """.format(self.videos, self.batch_size, self.epochs))

    def _exibirInfoFimTreino(self):
        print("""
Treinamento finalizado com sucesso!

Arquivo de log: "logs/{}.log"
Modelo: "{}"

Para jogar use o comando: 
    sudo python3 -m megaman_ai --nome={}
    """.format(self.nome, inteligencia._caminho, self.nome))

    def _treinar(self, videoCapture):
        """Executa o treinamento em um video"""
        
        self._s = [],[]
        self._rodada = 0
        
        # Lê o video até o fim
        while videoCapture.isOpened():
            # Obtém o frame do video e aplica tranformações iniciais
            frameBruto = videoCapture.read()[1]
            fimVideo = frameBruto is None

            if not fimVideo:
                frameRedimencionado = cv2.resize(frameBruto, (256, 240))
                frameCinza = cv2.cvtColor(frameRedimencionado, cv2.COLOR_BGR2GRAY)
                # Vou usar 1/4 da imagem para treinar
                frameCinza = cv2.resize(frameCinza, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_NEAREST)
                frameTratado = visao.MegaMan.transformar(frameRedimencionado)
                
                # atualizar o estado do objeto megaman usando o frame
                self.visao.atualizar(frameTratado, 20)
                
                # treina a rede com o frame anterior e o rótulo do frame atual
                # apenas nas transições
                temAnterior = not self._frameAnterior[0] is None
                isTransicao = True #self._frameAnterior[1] != self.visao.rotulo
                temEstadoAtual = self.visao.rotulo != -1
                excecao = self.visao.rotulo in (10, 11)
                descSubida = False # self.visao.rotulo in (8, 9) and self._frameAnterior[1] in (8, 9)  

                if temAnterior and isTransicao and temEstadoAtual and \
                    not excecao and not descSubida:
                    # coloca no dataset
                    self._s[0].append(self._frameAnterior[0])
                    self._s[1].append(self.visao.rotulo)
                
            # atualiza o frame anterior
            self._frameAnterior = frameCinza,self.visao.rotulo

            # Verifica se está pronto para treinar
            prontoTreinar = len(self._s[0]) == self.batch_size 

            if  prontoTreinar or fimVideo:
                self._fit()
                # limpa o batch
                self._s[0].clear()
                self._s[1].clear()
                self._rodada += 1

            # Exibe informações do treinamento no console
            self._exibirInfoTreinamento(videoCapture)

            # Exibe a visão atual com alguns dados
            self._exibirVisaoTreinamento(frameCinza)

            # Quando a tecla 'q' é pressionada interrompe o treinamento
            if (cv2.waitKey(1) & 0xFF) == ord('q') or fimVideo:
                cv2.destroyAllWindows()
                break

    def _atualizarLog(self, historico):
        info = Info(
            acc = list(map(float, historico.history['acc'])), 
            loss = list(map(float, historico.history['loss'])),
            rotulos = self._s[1],
            tam_batch = len(self._s[0]))
        
        self._log.write(str(info))
        
    def _fit(self):
        treinar = True
        epochs = self.epochs
        
        while treinar:
            historico = inteligencia.modelo.fit(
                numpy.array(self._s[0])/255.0, 
                numpy.array(self._s[1]),
                batch_size=self.batch_size,
                epochs=epochs, 
                verbose=1, 
                shuffle=True)

            self._atualizarLog(historico)
            
            print("Mais epochs? Se sim digite a quantidade. Se não pressione Enter.")
            resp = input(">>> ")

            try:
                if len(resp) > 0:
                    treinar = int(resp) != 0
                    epochs = int(resp)
                else:
                    break
            except:
                break
                
    def _exibirInfoTreinamento(self, videoCapture):
        """Print de informações sobre o andamento do treinamento"""
        # Progresso
        frameAtual = int(videoCapture.get(cv2.CAP_PROP_POS_FRAMES))
        framesTotal = int(videoCapture.get(cv2.CAP_PROP_FRAME_COUNT))
        progresso = int((frameAtual/framesTotal)*100)
        texto = "\rProgresso: [{}] {}% {}"
        statBatch = "{}/{}".format(len(self._s[0]), self.batch_size)
        preenchimento = "#"*int(progresso/4)+">"+"."*(int(100/4)-int(progresso/4))
        # imprime
        print(texto.format(preenchimento, progresso, statBatch), end="")

    def _exibirVisaoTreinamento(self, frame):
        """Mostra a visão do treinamento"""
        if self.exibir:
            #* Comentado pois se tornou desnecessário
            # progresso = self.estatisticas.progresso
            # qualidade = self.estatisticas.qualidadeAtual
            # self.visao.desenhar_infos(frame, progresso, qualidade)
            frame = cv2.resize(frame, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
            cv2.imshow("Treinamento", frame)

class Info:
    def __init__(self, **kwargs):
        self.__dict__ = kwargs
    
    def __str__(self):
        return yaml.dump({datetime.now().isoformat(): self.__dict__})