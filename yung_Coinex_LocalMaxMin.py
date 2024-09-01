import pickle
import os
import platform
import sys
import time
import pandas as pd
import pandas_ta as ta

from client import RequestsClient
from correo import enviar_correo
from monitor import update_text_code,post_action
import config

# from IPython.display import clear_output


def clear_console():
    os_system = platform.system()
    if os_system == 'Windows':
        os.system('cls')
    else:
        os.system('clear')


# Clase del bot de trading
class SwingTradingBot:
    def __init__(self):
        self.last_data=None#Esto es para que controlar el momento de entrenamiento del modelo        
        self.ganancia=0
        self.current_operation=None
        self.current_price=None
        self.open_price=None
        self.analisis=1
        self.cant_opr=0
        self.cant_win=0
        self.cant_loss=0
        self.client=RequestsClient(access_id=config.access_id,secret_key=config.secret_key)

        self.cant_trainings = 0
        self.last_patron = None
        self.save_state()


    def predecir(self, data):
        if str(data)!=self.last_data:
            self.cant_trainings += 1
            self.last_data = str(data)

            if (data.iloc[-1]['EMA7'] > data.iloc[-1]['EMA20']) and data.iloc[-1]['RSI'] < 30:
                self.last_patron = 'LONG'
                self.save_state()
                return "LONG"
            elif (data.iloc[-1]['EMA7'] < data.iloc[-1]['EMA20']) and data.iloc[-1]['RSI'] > 70:
                self.last_patron = 'SHORT'
                self.save_state()
                return "SHORT"
            else:
                self.last_patron = 'LATERALIZACION'
                self.save_state()
                return "LATERALIZACION"
                
            signals = pd.DataFrame(index=data.index)
            signals['signal'] = 'NONE'

            # Señales de apertura de posición long
            signals.loc[(data['RSI'] < 30) & (data['EMA7'] > data['EMA20']) & (data['ATR'] > data['ATR'].shift(1)), 'signal'] = 'LONG'

            # Señales de apertura de posición short
            signals.loc[(data['RSI'] > 70) & (data['EMA7'] < data['EMA20']) & (data['ATR'] > data['ATR'].shift(1)), 'signal'] = 'SHORT'

            # Señales de cierre de posición long
            signals.loc[(data['RSI'] > 70) & (data['EMA7'] < data['EMA20']) & (data['ATR'] < data['ATR'].shift(1)), 'signal'] = 'CLOSE_LONG'

            # Señales de cierre de posición short
            signals.loc[(data['RSI'] < 30) & (data['EMA7'] > data['EMA20']) & (data['ATR'] < data['ATR'].shift(1)), 'signal'] = 'CLOSE_SHORT'

            # Señales de lateralización
            signals.loc[(data['RSI'] > 40) & (data['RSI'] < 60) & (abs(data['EMA7'] - data['EMA20']) < 0.01 * data['close']) & (data['ATR'] < data['ATR'].shift(1)), 'signal'] = 'LATERALIZACION'


            if signals.iloc[-1]['signal'] == 'NONE':
                self.last_patron = 'LATERALIZACION'
                self.save_state()
                return 'LATERALIZACION'
            self.last_patron = signals.iloc[-1]['signal']
            self.save_state()
            return signals.iloc[-1]['signal']
        else:
            if self.last_patron == None:
                self.last_patron = 'LATERALIZACION'
                self.save_state()
                return 'LATERALIZACION'
            return self.last_patron


    #ESTRATEGIA LISTA
    def trade(self):
        patron=''
        sma=None
        s=""

        #$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
        #generar_señal
        data=self.get_data()
        patron=self.predecir(data)
        #$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

        nueva=False
        s=f"[#] Entrenamiento # {self.cant_trainings}\n"
        s+=f"[#] Analisis # {self.analisis}\n"
        self.analisis+=1
        s+=f"[#] OPERACION ACTUAL: {self.current_operation}\n"
        s+=f"[#] GANANCIA ACTUAL: {self.ganancia}\n"
        s+=f"[#] PRECIO BTC-USDT: {self.current_price}\n"
        s+=f"[#] PATRON: {patron}\n"

        balance=7

        if self.current_operation == "LONG":
            if patron in ["SHORT","LATERALIZACION","CLOSE_LONG"]:
                s+=self.close_operations(self.current_price)
                nueva=True
            else:
                s+=self.mantener(self.current_price)
                #============================================
        elif self.current_operation == "SHORT":
            if patron in ["LONG","LATERALIZACION","CLOSE_SHORT"]:
                s+=self.close_operations(self.current_price)
                nueva=True
            else:
                s+=self.mantener(self.current_price)
                #============================================

                
        if self.current_operation == None:
            if patron=="LONG" and balance*0.9>=2:
                s+=self.open_long()
                nueva=True
            elif patron=="SHORT" and balance*0.9>=2:
                s+=self.open_short()
                nueva=True
            else:
                s+=self.mantener(self.current_price)

        s+=f"[#] BALANCE: {balance} USDT\n"
        s+=f"[#] OPERACIONES: {self.cant_opr}\n"
        s+=f"[#] GANADAS: {self.cant_win}\n"
        s+=f"[#] PERDIDAS: {self.cant_loss}\n"
        if data.iloc[-1]['EMA7']>=data.iloc[-1]['EMA20']:
            s+=f"[#] EMA7: {data.iloc[-1]['EMA7']}\n"
            s+=f"[#] EMA20: {data.iloc[-1]['EMA20']}\n"
        else:
            s+=f"[#] EMA20: {data.iloc[-1]['EMA20']}\n"
            s+=f"[#] EMA7: {data.iloc[-1]['EMA7']}\n"
        s+=f"[#] RSI: {data.iloc[-1]['RSI']}\n"
        s+="\n--------------------------------------\n"
        if nueva == True and config.ENVIO_MAIL==True:
            enviar_correo(s=s,email=config.email)
        return s

    def close_operations(self,current_price):
        if config.Operar:
            self.close()
        s=""
        s+=f"[++++] CERRANDO POSICION {self.current_operation}\n"
        if self.current_operation == "LONG":
            self.ganancia+=current_price - self.open_price
            s+=f"[#] ESTADO: {current_price - self.open_price}\n"
            if current_price - self.open_price > 0:
                self.cant_win+=1
            else:
                self.cant_loss+=1
        else:
            self.ganancia+=self.open_price - current_price
            s+=f"[#] ESTADO: {self.open_price - current_price}\n"
            if self.open_price - current_price > 0:
                self.cant_win+=1
            else:
                self.cant_loss+=1
        s+=f"[#] GANANCIA: {self.ganancia}\n"
        self.open_price=None
        self.current_operation=None
        self.save_state()
        
        post_action(self.ganancia,self.analisis)
        return s

    #LISTO
    def mantener(self,current_price,s=""):
        s=""
        if self.current_operation != None:
            s+=f"[++++] MANTENER OPERACION {self.current_operation} a {self.open_price}\n"
            s+="[#] ESTADO: "
            if self.current_operation == "LONG":
                s+=str(current_price-self.open_price)+"\n"
            else:
                s+=str(self.open_price-current_price)+"\n"
        else:
            s+="[#] NO EJECUTAR ACCION\n"
        return s

    #LISTO
    def open_long(self,s=""):
        self.open_price=self.current_price
        s=""
        if self.open_price == None:
            s+=f"[++++] Error al abrir posicion en long:\n"
        else:
            s+=f"[++++] ABRIENDO POSICION LONG A {self.open_price}\n"
            self.current_operation="LONG"
            self.cant_opr+=1
            self.save_state()
        return s

    #LISTO
    def open_short(self,s=""):
        self.open_price=self.current_price
        s=""
        if self.open_price == None:
            s+=f"[++++] Error al abrir posicion en short:\n"
        else:
            s+=f"[++++] ABRIENDO POSICION SHORT A {self.open_price}\n"
            self.current_operation="SHORT"
            self.cant_opr+=1
            self.save_state()
        return s



    #LISTO
    def get_data(self):
        request_path = "/futures/kline"
        params = {
            "market":config.simbol,
            "limit":config.size,
            "period":config.temporalidad
        }
        response = self.client.request(
            "GET",
            "{url}{request_path}".format(url=self.client.url, request_path=request_path),
            params=params,
        )
        data=response.json().get("data")
        ohlcv_df = pd.DataFrame(data)
        # Convertir las columnas de precios y volumen a numérico
        ohlcv_df['close'] = pd.to_numeric(ohlcv_df['close'])
        ohlcv_df['high'] = pd.to_numeric(ohlcv_df['high'])
        ohlcv_df['low'] = pd.to_numeric(ohlcv_df['low'])
        ohlcv_df['open'] = pd.to_numeric(ohlcv_df['open'])
        ohlcv_df['volume'] = pd.to_numeric(ohlcv_df['volume'])
        self.current_price = ohlcv_df['close'].iloc[-1]
        ohlcv_df = ohlcv_df.drop('market', axis=1)
        ohlcv_df = ohlcv_df.drop('created_at', axis=1)
        if config.incluir_precio_actual==False:
            ohlcv_df = ohlcv_df.drop(ohlcv_df.index[-1])
        ohlcv_df['RSI'] = ta.rsi(ohlcv_df['close'],length=15)

        #new_columns = pd.DataFrame()
        #EMA
        #for i in range(5,101):
        #    new_columns[f'EMA-{i}'] = ta.ema(ohlcv_df['close'], length=i)
        #ohlcv_df = pd.concat([ohlcv_df, new_columns], axis=1)
        ohlcv_df[f'EMA7'] = ta.ema(ohlcv_df['close'], length=7)
        ohlcv_df[f'EMA20'] = ta.ema(ohlcv_df['close'], length=20)
        
        # ATR
        ohlcv_df['ATR'] = ta.atr(ohlcv_df['high'], ohlcv_df['low'], ohlcv_df['close'])
        
        # Eliminar las primeras filas para evitar NaNs
        ohlcv_df = ohlcv_df.dropna()
        '''
        ohlcv_df = ta.add_all_ta_features(
            ohlcv_df, open="open", high="high", low="low", close="close", volume="volume", fillna=True
        )
        '''
        return ohlcv_df


    #LISTO
    def save_state(self):
        with open('yungIA_data.pkl', 'wb') as file:
            pickle.dump(self, file)

    #LISTO
    @staticmethod
    def load_state():
        if os.path.exists('yungIA_data.pkl'):
            with open('yungIA_data.pkl', 'rb') as file:
                return pickle.load(file)
        else:
            return None


def run_bot():
    bot = SwingTradingBot.load_state()
    if bot is None:
        bot = SwingTradingBot()

    clear_console()
    
    # Iniciar el bot
    while True:
        error=False
        #try:
        print("\nPROCESANDO ANALISIS...")
        s=bot.trade()
        clear_console()
        update_text_code(mensaje=s)
        print(s)
        #except Exception as e:
        #    clear_console()
        #    print(f"Error: {str(e)}\n")
        #    error=True
        print("Esperando para el próximo análisis...")
        if error:
            tiempo_espera=1
        else:
            tiempo_espera=config.tiempo_espera
        for i in range(tiempo_espera, 0, -1):
            sys.stdout.write("\rTiempo restante: {:02d}:{:02d} ".format(i // 60, i % 60))
            sys.stdout.flush()
            time.sleep(1)
        sys.stdout.write("\r" + " " * 50)  # Limpiar la línea después de la cuenta regresiva
        sys.stdout.flush()
