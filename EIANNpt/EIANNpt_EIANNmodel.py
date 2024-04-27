"""EIANNpt_EIANNmodel.py

# Author:
Richard Bruce Baxter - Copyright (c) 2024 Baxter AI (baxterai.com)

# License:
MIT License

# Installation:
see ANNpt_main.py

# Usage:
see ANNpt_main.py

# Description:
EIANNpt excitatory inhibitory artificial neural network model

"""

import torch as pt
from torch import nn
from ANNpt_globalDefs import *
from torchmetrics.classification import Accuracy
import ANNpt_linearSublayers


class EIANNconfig():
	def __init__(self, batchSize, numberOfLayers, hiddenLayerSize, inputLayerSize, outputLayerSize, linearSublayersNumber, numberOfFeatures, numberOfClasses, datasetSize, numberOfClassSamples):
		self.batchSize = batchSize
		self.numberOfLayers = numberOfLayers
		self.hiddenLayerSize = hiddenLayerSize
		self.inputLayerSize = inputLayerSize
		self.outputLayerSize = outputLayerSize
		self.linearSublayersNumber = linearSublayersNumber
		self.numberOfFeatures = numberOfFeatures
		self.numberOfClasses = numberOfClasses
		self.datasetSize = datasetSize		
		self.numberOfClassSamples = numberOfClassSamples
		
class EIANNmodel(nn.Module):
	def __init__(self, config):
		super().__init__()
		self.config = config

		layersLinearListEe = []
		layersLinearListEi = []
		layersLinearListIe = []
		layersLinearListIi = []
		layersActivationListE = []
		layersActivationListI = []
		for layerIndex in range(config.numberOfLayers):
			inFeaturesMatchHidden = False
			inFeaturesMatchOutput = False
			if(not firstHiddenLayerExcitatoryInputOnly):
				if(layerIndex == 0):	
					inFeaturesMatchHidden = True	#inhibitoryInterneuronFirstLayer	#CHECKTHIS: set first inhibitory layer size to input layer size (ensure zEi will be a same shape as zEe)
				if(layerIndex == config.numberOfLayers-1):
					inFeaturesMatchOutput = True	#inhibitoryInterneuronLastLayer	
			linearEe = ANNpt_linearSublayers.generateLinearLayer(self, layerIndex, config, sign=True)	#excitatory neuron excitatory input
			linearEi = ANNpt_linearSublayers.generateLinearLayer(self, layerIndex, config, sign=False, inFeaturesMatchHidden=inFeaturesMatchHidden, inFeaturesMatchOutput=inFeaturesMatchOutput)	#excitatory neuron inhibitory input
			linearIe = ANNpt_linearSublayers.generateLinearLayer(self, layerIndex, config, sign=True)	#inhibitory neuron excitatory input
			linearIi = ANNpt_linearSublayers.generateLinearLayer(self, layerIndex, config, sign=False)	#inhibitory neuron inhibitory input
			layersLinearListEe.append(linearEe)
			layersLinearListEi.append(linearEi)
			layersLinearListIe.append(linearIe)
			layersLinearListIi.append(linearIi)
			activationE = ANNpt_linearSublayers.generateActivationLayer(self, layerIndex, config)
			activationI = ANNpt_linearSublayers.generateActivationLayer(self, layerIndex, config)
			layersActivationListE.append(activationE)
			layersActivationListI.append(activationI)
		self.layersLinearEe = nn.ModuleList(layersLinearListEe)
		self.layersLinearEi = nn.ModuleList(layersLinearListEi)
		self.layersLinearIe = nn.ModuleList(layersLinearListIe)
		self.layersLinearIi = nn.ModuleList(layersLinearListIi)
		self.layersActivationE = nn.ModuleList(layersActivationListE)
		self.layersActivationI = nn.ModuleList(layersActivationListI)
	
		if(useInbuiltCrossEntropyLossFunction):
			self.lossFunction = nn.CrossEntropyLoss()
		else:
			self.lossFunction = nn.NLLLoss()	#nn.CrossEntropyLoss == NLLLoss(log(softmax(x)))
		self.accuracyFunction = Accuracy(task="multiclass", num_classes=self.config.outputLayerSize, top_k=1)
		
		ANNpt_linearSublayers.weightsSetPositiveModel(self)
				
	def forward(self, trainOrTest, x, y, optim=None, l=None):
		if(useLinearSublayers):
			x = x.unsqueeze(dim=1)
		xE = x
		xI = pt.zeros_like(x)	#there is no inhibitory input to first hidden layer in network
		for layerIndex in range(self.config.numberOfLayers):
			#print("layerIndex = ", layerIndex)
			xPrevE = xE
			xPrevI = xI
			if(trainLastLayerOnly):
				xE = xE.detach()
				xI = xI.detach()
			zIe = ANNpt_linearSublayers.executeLinearLayer(self, layerIndex, xPrevE, self.layersLinearIe[layerIndex], parallelStreams=False, sign=True)	#inhibitory neuron excitatory input
			zIi = ANNpt_linearSublayers.executeLinearLayer(self, layerIndex, xPrevI, self.layersLinearIi[layerIndex], parallelStreams=False, sign=False)	#inhibitory neuron inhibitory input
			zI = zIe + zIi	#sum the positive/negative inputs of the inhibitory neurons
			xI = ANNpt_linearSublayers.executeActivationLayer(self, layerIndex, zI, self.layersActivationI[layerIndex], parallelStreams=False)	#relU
			if(firstHiddenLayerExcitatoryInputOnly):
				zEe = ANNpt_linearSublayers.executeLinearLayer(self, layerIndex, xPrevE, self.layersLinearEe[layerIndex], parallelStreams=False, sign=True)	#excitatory neuron excitatory input
				zEi = ANNpt_linearSublayers.executeLinearLayer(self, layerIndex, xPrevI, self.layersLinearEi[layerIndex], parallelStreams=False, sign=False)	#excitatory neuron inhibitory input
			else:
				zEe = ANNpt_linearSublayers.executeLinearLayer(self, layerIndex, xPrevE, self.layersLinearEe[layerIndex], parallelStreams=False, sign=True)	#excitatory neuron excitatory input
				zEi = ANNpt_linearSublayers.executeLinearLayer(self, layerIndex, xI, self.layersLinearEi[layerIndex], parallelStreams=False, sign=False)	#excitatory neuron inhibitory input
			zE = zEe + zEi	#sum the positive/negative inputs of the excitatory neurons
			xE = ANNpt_linearSublayers.executeActivationLayer(self, layerIndex, zE, self.layersActivationE[layerIndex], parallelStreams=False)	#relU
			if(firstHiddenLayerExcitatoryInputOnly):
				#normalise via top k (normalise activation sparsity) because there is no inhibitory input
				k = self.hiddenLayerSize//2
				xE = self.deactivateNonTopKneurons(xE, k)
				
			if(debugSmallNetwork):
				print("layerIndex = ", layerIndex)
				print("xE after linear = ", xE)
				print("xI after linear = ", xI)
			if(layerIndex == self.config.numberOfLayers-1):
				if(useInbuiltCrossEntropyLossFunction):
					x = zE
				else:
					#xI = ANNpt_linearSublayers.executeActivationLayer(self, layerIndex, zI, self.layersActivationI[layerIndex], parallelStreams=False)	#there is no final/output inhibitory layer
					xE = ANNpt_linearSublayers.executeActivationLayer(self, layerIndex, zE, self.layersActivationE[layerIndex], parallelStreams=False)
					x = torch.log(x)
			else:
				if(simulatedDendriticBranches):
					x, xIndex = self.performTopK(x)
			if(trainOrTest and EIANNlocalLearning):
				if(hebbianWeightsUsingEIseparableInputsCorrespondenceMatrix):
					hebbianMatrixEe = self.calculateAssociationMatrix(layerIndex, zEe, xPrevE)	#all +ve
					hebbianMatrixEi = self.calculateAssociationMatrix(layerIndex, zEi, xI)	#all -ve
					hebbianMatrixIe = self.calculateAssociationMatrix(layerIndex, zIe, xPrevE)	#all -ve
					hebbianMatrixIi = self.calculateAssociationMatrix(layerIndex, zIi, xPrevI)	#all +ve
				else:
					hebbianMatrixE = self.calculateAssociationMatrix(layerIndex, zE, xPrevE)	#all +ve
					hebbianMatrixI = self.calculateAssociationMatrix(layerIndex, zI, xPrevI)	#all -ve
					hebbianMatrixEe = hebbianMatrixE
					hebbianMatrixEi = hebbianMatrixE
					hebbianMatrixIe = hebbianMatrixI
					hebbianMatrixIi = hebbianMatrixI
				if(EIANNlocalLearningApplyError):
					error = self.calculateError(xE, xI)
					hebbianMatrixEe = self.calculateHebbianMatrix(hebbianMatrixEe, error, False)	#if +ve error, want to decrease Ee (ie +ve) weights
					hebbianMatrixEi = self.calculateHebbianMatrix(hebbianMatrixEi, error, True)	#if +ve error, want to increase Ei (ie -ve) weights
					hebbianMatrixIe = self.calculateHebbianMatrix(hebbianMatrixIe, error, False)	#if +ve error, want to decrease Ie (ie +ve) weights
					hebbianMatrixIi = self.calculateHebbianMatrix(hebbianMatrixIi, error, True)	#if +ve error, want to increase Ii (ie -ve) weights
				self.trainWeightsLayer(layerIndex, hebbianMatrixEe, self.layersLinearEe[layerIndex])
				self.trainWeightsLayer(layerIndex, hebbianMatrixEi, self.layersLinearEi[layerIndex])
				self.trainWeightsLayer(layerIndex, hebbianMatrixIe, self.layersLinearIe[layerIndex])
				self.trainWeightsLayer(layerIndex, hebbianMatrixIi, self.layersLinearIi[layerIndex])
			if(debugSmallNetwork):
				print("x after activation = ", x)
		
		if(useLinearSublayers):
			x = x.squeeze(dim=1)

		loss = self.lossFunction(x, y)
		accuracy = self.accuracyFunction(x, y)
		accuracy = accuracy.detach().cpu().numpy()
		
		return loss, accuracy

	def deactivateNonTopKneurons(self, activations, k):
		topk_values, topk_indices = pt.topk(activations, k=k, dim=1)
		mask = pt.zeros_like(activations)
		mask.scatter_(1, topk_indices, 1)
		masked_activations = activations * mask
		return masked_activations
	
	def performTopK(self, x):
		xMax = pt.max(x, dim=1, keepdim=False)
		x = xMax.values
		xIndex = xMax.indices
		return x, xIndex
	
	def calculateAssociationMatrix(self, layerIndex, x, xPrev):
		if(useLinearSublayers):
			x = pt.squeeze(x, dim=1)		#assume linearSublayersNumber=1
			xPrev = pt.squeeze(xPrev, dim=1)	#assume linearSublayersNumber=1
		associationMatrix = pt.matmul(pt.transpose(x, 0, 1), xPrev)
		return associationMatrix
		
	def calculateError(self, xE, xI):
		error = xE + xI
		return error

	def calculateHebbianMatrix(self, associationMatrix, error, sign):
		associationMatrix = pt.abs(associationMatrix)
		#print("associationMatrix.shape = ", associationMatrix.shape)
		#print("error.shape = ", error.shape)
		error = pt.mean(error, dim=0) #average error over batchSize	#associationMatrix has already been averaged over batchSize
		error = pt.unsqueeze(error, dim=1)
		if(sign):
			hebbianMatrix = associationMatrix*error*1
		else:
			hebbianMatrix = associationMatrix*error*-1
		return hebbianMatrix
	
	def trainWeightsLayer(self, layerIndex, hebbianMatrix, layerLinear):
		#use local hebbian learning rule - CHECKTHIS
		layerWeights = layerLinear.weight
		#layerWeights = pt.reshape(layerWeights, (linearSublayersNumber, hiddenLayerSize, layerWeights.shape[1], layerWeights.shape[2]))	#useLinearSublayers only
	
		weightUpdate = hebbianMatrix*EIANNlocalLearningRate
		layerWeights = layerWeights + weightUpdate
			
		#layerWeights = pt.reshape(layerWeights, (linearSublayersNumber*hiddenLayerSize, layerWeights.shape[2], layerWeights.shape[3]))	#useLinearSublayers only
		layerLinear.weight = pt.nn.Parameter(layerWeights)

