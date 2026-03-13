import os
os.environ['CUDA_LAUNCH_BLOCKING'] = '1'

import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
import numpy as np
from ta.trend import MACD
from ta.momentum import RSIIndicator
from ta.volume import OnBalanceVolumeIndicator
from ta.volatility import BollingerBands
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
from sklearn.metrics import precision_score, recall_score, f1_score

# Check if GPU is available
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Load CSV data
data = pd.read_csv('historical_data_last.csv', sep=';', header=None, 
                   names=['DateTime', 'Open', 'High', 'Low', 'Close', 'Volume'])

# Convert DateTime to a proper datetime object
data['DateTime'] = pd.to_datetime(data['DateTime'], format='%Y%m%d %H%M%S')

# Calculate additional features
data['EMA9'] = data['Close'].ewm(span=9, adjust=False).mean()
data['EMA20'] = data['Close'].ewm(span=20, adjust=False).mean()
data['EMA200'] = data['Close'].ewm(span=200, adjust=False).mean()
data['SMA200'] = data['Close'].rolling(window=200).mean()

# Calculate VWAP
data['VWAP'] = (data['Close'] * data['Volume']).cumsum() / data['Volume'].cumsum()

# Add MACD
macd = MACD(close=data['Close'])
data['MACD'] = macd.macd()
data['MACD_Signal'] = macd.macd_signal()
data['MACD_Histogram'] = macd.macd_diff()

# Add RSI
rsi = RSIIndicator(close=data['Close'])
data['RSI'] = rsi.rsi()

# Add OBV
obv = OnBalanceVolumeIndicator(close=data['Close'], volume=data['Volume'])
data['OBV'] = obv.on_balance_volume()

# Add Bollinger Bands
bb = BollingerBands(close=data['Close'])
data['BB_High'] = bb.bollinger_hband()
data['BB_Low'] = bb.bollinger_lband()

# Define features (X) and labels (y)
X = data[['Close', 'Volume', 'MACD', 'MACD_Signal', 'MACD_Histogram', 'EMA9', 'EMA20', 'EMA200', 'SMA200', 'VWAP', 'OBV', 'RSI', 'BB_High', 'BB_Low']]

# Create a simple label (you should replace this with your actual labeling strategy)
data['Label'] = (data['Close'].shift(-1) > data['Close']).astype(int)

y = data['Label']

# Drop NaN values
data.dropna(inplace=True)

# Reset index after dropping rows
data.reset_index(drop=True, inplace=True)

# Split data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Normalize the data
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Convert to PyTorch tensors
X_train_tensor = torch.tensor(X_train_scaled, dtype=torch.float32).to(device)
y_train_tensor = torch.tensor(y_train.values, dtype=torch.float32).view(-1, 1).to(device)
X_test_tensor = torch.tensor(X_test_scaled, dtype=torch.float32).to(device)
y_test_tensor = torch.tensor(y_test.values, dtype=torch.float32).view(-1, 1).to(device)

# Replace NaN values with 0
X_train_tensor = torch.nan_to_num(X_train_tensor, nan=0.0)
y_train_tensor = torch.nan_to_num(y_train_tensor, nan=0.0)
X_test_tensor = torch.nan_to_num(X_test_tensor, nan=0.0)
y_test_tensor = torch.nan_to_num(y_test_tensor, nan=0.0)

# Check for NaN or infinity values
print("NaN in X_train:", torch.isnan(X_train_tensor).any())
print("Inf in X_train:", torch.isinf(X_train_tensor).any())
print("NaN in y_train:", torch.isnan(y_train_tensor).any())
print("Inf in y_train:", torch.isinf(y_train_tensor).any())

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

# Initialize the model, loss function, and optimizer
input_size = X_train.shape[1]
model = SimpleTradingModel(input_size).to(device).double()
criterion = nn.BCELoss()
optimizer = optim.Adam(model.parameters(), lr=0.0001)  # Smaller learning rate

# Convert data to double precision
X_train_tensor = X_train_tensor.double()
y_train_tensor = y_train_tensor.double()
X_test_tensor = X_test_tensor.double()
y_test_tensor = y_test_tensor.double()

# Clear CUDA cache
torch.cuda.empty_cache()

# Training loop with resume capability
num_epochs = 100
batch_size = 64
start_epoch = 0  # Default start epoch

# Load checkpoint if exists
if os.path.isfile('checkpoint.pth'):
    checkpoint = torch.load('checkpoint.pth')
    model.load_state_dict(checkpoint['model_state_dict'])
    optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    start_epoch = checkpoint['epoch']
    loss = checkpoint['loss']
    print(f"Resuming training from epoch {start_epoch}")

epoch_losses = []

for epoch in range(start_epoch, num_epochs):
    model.train()
    epoch_loss = 0
    for i in range(0, len(X_train_tensor), batch_size):
        batch_X = X_train_tensor[i:i+batch_size]
        batch_y = y_train_tensor[i:i+batch_size]
        
        # Remove NaN values from the batch
        mask = ~torch.isnan(batch_X).any(dim=1)
        batch_X = batch_X[mask]
        batch_y = batch_y[mask]
        
        optimizer.zero_grad()
        outputs = model(batch_X)
        outputs = torch.clamp(outputs, min=0, max=1)  # Ensure outputs are in the range [0, 1]
        loss = criterion(outputs, batch_y)
        loss.backward()
        optimizer.step()
        
        epoch_loss += loss.item()

    epoch_losses.append(epoch_loss / len(X_train_tensor))

    if (epoch + 1) % 10 == 0:
        print(f'Epoch [{epoch + 1}/{num_epochs}], Loss: {epoch_loss/len(X_train_tensor):.4f}')

    # Save checkpoint
    torch.save({
        'epoch': epoch + 1,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'loss': loss,
    }, 'checkpoint.pth')

# Save the final model
torch.save(model.state_dict(), "trading_model_final.pth")

# Plot the training loss
plt.plot(range(start_epoch, num_epochs), epoch_losses)
plt.xlabel('Epoch')
plt.ylabel('Loss')
plt.title('Training Loss Over Epochs')
plt.show()

# Evaluation
model.eval()
with torch.no_grad():
    predictions = model(X_test_tensor)
    predicted = (predictions > 0.5).float()
    accuracy = (predicted.eq(y_test_tensor).sum() / y_test_tensor.shape[0]).item()
    precision = precision_score(y_test_tensor.cpu(), predicted.cpu())
    recall = recall_score(y_test_tensor.cpu(), predicted.cpu())
    f1 = f1_score(y_test_tensor.cpu(), predicted.cpu())

print(f'Test Accuracy: {accuracy:.4f}')
print(f'Precision: {precision:.4f}')
print(f'Recall: {recall:.4f}')
print(f'F1 Score: {f1:.4f}')
