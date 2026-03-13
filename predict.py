import torch
import torch.nn as nn
import pandas as pd
from sklearn.preprocessing import StandardScaler
from ta.trend import MACD
from ta.momentum import RSIIndicator
from ta.volume import OnBalanceVolumeIndicator
from ta.volatility import BollingerBands

class SimpleTradingModel(nn.Module):
    def __init__(self, input_size):
        super(SimpleTradingModel, self).__init__()
        self.fc1 = nn.Linear(input_size, 64)
        self.fc2 = nn.Linear(64, 32)
        self.fc3 = nn.Linear(32, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        x = self.fc3(x)
        return self.sigmoid(x)

def load_model(model_path, input_size):
    model = SimpleTradingModel(input_size)
    model.load_state_dict(torch.load(model_path))
    model.eval()
    return model

def preprocess_data(data_path):
    data = pd.read_csv(data_path, sep=';', header=None, 
                       names=['DateTime', 'Open', 'High', 'Low', 'Close', 'Volume'])
    data['DateTime'] = pd.to_datetime(data['DateTime'], format='%Y%m%d %H%M%S')
    
    # Calculate additional features
    data['EMA9'] = data['Close'].ewm(span=9, adjust=False).mean()
    data['EMA20'] = data['Close'].ewm(span=20, adjust=False).mean()
    data['EMA200'] = data['Close'].ewm(span=200, adjust=False).mean()
    data['SMA200'] = data['Close'].rolling(window=200).mean()
    data['VWAP'] = (data['Close'] * data['Volume']).cumsum() / data['Volume'].cumsum()
    
    macd = MACD(close=data['Close'])
    data['MACD'] = macd.macd()
    data['MACD_Signal'] = macd.macd_signal()
    data['MACD_Histogram'] = macd.macd_diff()
    
    rsi = RSIIndicator(close=data['Close'])
    data['RSI'] = rsi.rsi()
    
    obv = OnBalanceVolumeIndicator(close=data['Close'], volume=data['Volume'])
    data['OBV'] = obv.on_balance_volume()
    
    bb = BollingerBands(close=data['Close'])
    data['BB_High'] = bb.bollinger_hband()
    data['BB_Low'] = bb.bollinger_lband()
    
    X = data[['Close', 'Volume', 'MACD', 'MACD_Signal', 'MACD_Histogram', 'EMA9', 'EMA20', 'EMA200', 'SMA200', 'VWAP', 'OBV', 'RSI', 'BB_High', 'BB_Low']]
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    X_tensor = torch.tensor(X_scaled, dtype=torch.float32)
    return X_tensor

def predict(model, data_tensor):
    with torch.no_grad():
        predictions = model(data_tensor)
        predicted = (predictions > 0.5).float()
    return predicted

if __name__ == "__main__":
    model_path = "trading_model_final.pth"
    data_path = "historical_data_last.csv"
    
    # Load the model
    input_size = 14  # Number of features
    model = load_model(model_path, input_size)
    
    # Preprocess the data
    data_tensor = preprocess_data(data_path)
    
    # Make predictions
    predictions = predict(model, data_tensor)
    
    # Print predictions
    print(predictions)

