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
import megaman_ai
import timeit

from megaman_ai import inteligencia

class Treinamento:
    """Armazena informações sobre uma instancia de treinamento
    incluindo estatísticas sobre o andamento do treinamento."""

    def __init__(self, videos, sprites, **kwargs):
        self.videos = videos
        self.visao = megaman_ai.visao.MegaMan(sprites)
        self.destino = kwargs.get("destino", "")
        self.tempo = kwargs.get("tempo", False)
        self.exibir = kwargs.get("exibir", False)
        self.qualidade = kwargs.get("qualidade", False)
        self.epochs = kwargs.get("epochs", 50)
        self.batch_size = kwargs.get("batch_size", 100)
        self.estatisticas = Estatisticas()
        self._frameAnterior = None, -1
        self._s = [],[]

    def iniciar(self):
        """Inicia o treinamento em todos os videos"""

        for video in self.videos:
            
            # Abre o video
            videoCapture = cv2.VideoCapture(video)

            # Exibe algumas informações antes do inicio do treinamento
            self._exibirInfosInicioTreinamento(video)

            try:
                # Chama a função de treinamento para o video atual
                self._treinar(videoCapture)

            # Trata o caso de iterrupção pelo usuário via teclado
            # Para salvar o progresso do video
            except KeyboardInterrupt:
                print("Iterrompido pelo usuário.")

            # Exibe informações no fim do treinamento
            self._exibirInfosFimTreinamento(video)
            
            # Salva modelo
            inteligencia.salvar()

    def _exibirInfosFimTreinamento(self, video):
        """Exibe algumas informações antes do treinamento com o video"""
        inteligencia.modelo.summary()
        print("Fim de treinamento com o video {}.".format(video))

    def _exibirInfosInicioTreinamento(self, video):
        """Exibe algumas informações depois do treinamento com o video"""
        print("Iniciando treinamento video {}.".format(video))

    def _treinar(self, videoCapture):
        """Executa o treinamento em um video"""
        
        self._s = [],[]

        # Lê o video até o fim
        while videoCapture.isOpened():
            # Obtém o frame do video e aplica tranformações iniciais
            frameBruto = videoCapture.read()[1]
            fimVideo = frameBruto is None

            if not fimVideo:
                frameRedimencionado = cv2.resize(frameBruto, (256, 240))
                frameTratado = megaman_ai.visao.MegaMan.transformar(frameRedimencionado)
                
                # atualizar o estado do objeto megaman usando o frame
                qualidade = self.visao.atualizar(frameTratado, 20)
                
                # treina a rede com o frame anterior e o rótulo do frame atual
                # apenas nas transições
                if not self._frameAnterior[0] is None and \
                    self._frameAnterior[1] != self.visao.rotulo and \
                    self.visao.rotulo != -1:
                    self._s[0].append(self._frameAnterior[0])
                    self._s[1].append(self.visao.rotulo)
                
                # atualiza o frame anterior
                self._frameAnterior = frameTratado,self.visao.rotulo
                
            if len(self._s[0]) == self.batch_size or fimVideo: # ou fim do video
                inteligencia.modelo.fit(
                    numpy.array(self._s[0])/255.0, 
                    numpy.array(self._s[1]),
                    batch_size=self.batch_size,
                    epochs=self.epochs)
                # limpa o batch
                self._s[0].clear()
                self._s[1].clear()

            # Atualiza as estatísticas com os novos dados
            # TODO: A qualidade deve ser atualizada a cada frame que pega, 
            # neste momento está sendo calculado errado
            # talvez retirar essa estatística seja uma opção
            self.estatisticas.atualizar(videoCapture, 0) 

            # Exibe informações do treinamento no console
            self._exibirInfoTreinamento()

            # Exibe a visão atual com alguns dados
            self._exibirVisaoTreinamento(frameTratado)

            # Quando a tecla 'q' é pressionada interrompe o treinamento
            if (cv2.waitKey(1) & 0xFF) == ord('q') or fimVideo:
                break

    def _exibirInfoTreinamento(self):
        """Print de informações sobre o andamento do treinamento"""

        # Progresso
        progresso = self.estatisticas.progresso
        print("Progresso: [{}] {}% {}\r".format(
                "#"*int(progresso/4)+">"+"."*(int(100/4)-int(progresso/4)),
                progresso,
                "{}/{}".format(len(self._s[0]), self.batch_size)),
            end="")

    def _exibirVisaoTreinamento(self, frame):
        """Mostra a visão do treinamento"""

        if self.exibir:
            progresso = self.estatisticas.progresso
            qualidade = self.estatisticas.qualidadeAtual
            self.visao.desenhar_infos(frame, progresso, qualidade)


class Estatisticas:
    """Armazena as informações sobre o desempenho do treinamento"""
    framesTotal = None
    frameAtual = 0
    progresso = 0
    qualidadeAtual = 0
    qualidadeTotal = 0
    qualidadeMedia = 0
    tempoTotal = 0
    tempoMedioFrame = 0
    tempoInicial = 0

    def iniciar(self):
        """Inicia as estatísticas"""

        # Seta o tempoInicial
        self.tempoInicial = timeit.default_timer()

    def atualizar(self, videoCapture, qualidadeAtual):
        """Recebe e atualiza as informações"""

        # Atualiza os contadores
        self.framesTotal = int(videoCapture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.frameAtual = int(videoCapture.get(cv2.CAP_PROP_POS_FRAMES))
        self.progresso = int((self.frameAtual / self.framesTotal) * 100)
        self.qualidadeTotal += qualidadeAtual
        self.qualidadeMedia = self.qualidadeTotal / self.frameAtual
        diferenca = timeit.default_timer() - self.tempoInicial
        self.tempoTotal += diferenca
        self.tempoMedioFrame = self.tempoTotal / self.frameAtual
        self.tempoInicial = timeit.default_timer()
