import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from keras.models import Sequential
from keras.layers import Dense, LSTM, Input, Dropout

from keras_tuner import RandomSearch
from keras.optimizers import SGD

import config
def build_model(hp):
    model = Sequential()
    model.add(Input(shape=(config.time_step, 104)))
    for i in range(hp.Int('num_layers', 1, 3)):
        model.add(LSTM(units=hp.Int('units_' + str(i), min_value=50, max_value=200, step=50), return_sequences=True))
        model.add(Dropout(hp.Float('dropout_' + str(i), min_value=0.1, max_value=0.5, step=0.1)))
    model.add(LSTM(units=hp.Int('units_final', min_value=50, max_value=200, step=50), return_sequences=False))
    model.add(Dropout(hp.Float('dropout_final', min_value=0.1, max_value=0.5, step=0.1)))
    model.add(Dense(50, activation='relu'))
    model.add(Dense(25, activation='relu'))
    model.add(Dense(1))
    model.compile(loss='mean_squared_error')
    return model


class RNN():
    def __init__(self):
        self.tuner = RandomSearch(build_model, objective='val_loss', max_trials=5, executions_per_trial=3)
        

    def train2(self, X_train, y_train, X_val, y_val):
        X_train = np.array(X_train)
        y_train = np.array(y_train)
        X_val = np.array(X_val)
        y_val = np.array(y_val)
        self.tuner.search(X_train, y_train, epochs=config.epochs, validation_data=(X_val, y_val))
        self.best_model = self.tuner.get_best_models(num_models=1)[0]



    def predict(self, X_test, y_test=None, y_no_scaled=None, evalua=True):
        X_test = np.array(X_test)
        predictions = self.best_model.predict(X_test)
        scaler = MinMaxScaler()
        if y_no_scaled is not None:
            y_no_scaled = np.array(y_no_scaled).reshape(-1, 1)
            scaler.fit(y_no_scaled)
            predictions = predictions.reshape(-1, 1)
            predictions = scaler.inverse_transform(predictions)
        loss = None
        if y_test is not None and evalua:
            y_test = np.array(y_test)
            loss = self.best_model.evaluate(X_test, y_test, verbose=0)
        return predictions, loss


    @staticmethod
    def process_data(features):
        # Normaliza los datos
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled_data = scaler.fit_transform(features)
        return scaled_data
    

    
    @staticmethod
    def train_test_split2(dataset, no_scaled_data, porciento_train, porciento_val):
        dataX, dataY, y_no_scaled = [], [], []
        for i in range(len(dataset) - config.time_step - config.predict_step):
            a = dataset[i:(i + config.time_step), :]
            dataX.append(a)
            dataY.append(dataset[i + config.time_step + config.predict_step - 1, 0])
            y_no_scaled.append(no_scaled_data.iloc[i + config.time_step + config.predict_step - 1, 0])
        
        train_size = int(len(dataX) * porciento_train)
        val_size = int(len(dataX) * porciento_val)
        
        X_train = dataX[:train_size]
        y_train = dataY[:train_size]
        
        X_val = dataX[train_size:train_size + val_size]
        y_val = dataY[train_size:train_size + val_size]
        
        X_test = dataX[train_size + val_size:]
        y_test = dataY[train_size + val_size:]
        y_no_scaled = y_no_scaled[train_size + val_size:]


        return X_train, X_val, X_test, y_train, y_val, y_test, y_no_scaled

    @staticmethod
    def get_test_data(dataset):
        dataX = []
        for i in range(len(dataset)-config.time_step-config.predict_step):
            a = dataset[i:(i+config.time_step), :]
            dataX.append(a)
        return dataX


