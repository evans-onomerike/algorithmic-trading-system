// MyNinZaRenkoStrategy.cs
// NinjaTrader 8 Strategy — Multi-indicator confluence entry/exit system
// Communicates with Python execution backend via local HTTP

#region Using declarations
using NinjaTrader.NinjaScript.Strategies;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
using System.Windows.Media;
using System;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class MyNinZaRenkoStrategy : Strategy
    {
        private static readonly HttpClient client = new HttpClient();
        private MACD macd;
        private EMA ema200, ema9, ema20;
        private SMA sma200;
        private VWAP vwap;
        private OBV obv;
        private double entryPrice;
        private bool isLongPosition;
        private double lastPartialProfitPrice;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"NinZaRenko strategy with multi-indicator confluence and Python execution bridge";
                Name = "MyNinZaRenkoStrategy";
                Calculate = Calculate.OnEachTick;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 0;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TraceOrders = true;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 20;
                IncludeCommission = true;
                IsInstantiatedOnEachOptimizationIteration = false;
                isLongPosition = false;
            }
            else if (State == State.DataLoaded)
            {
                macd = MACD(12, 26, 9);
                ema200 = EMA(200);
                sma200 = SMA(200);
                ema9 = EMA(9);
                ema20 = EMA(20);
                vwap = VWAP();
                obv = OBV();
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade)
                return;

            bool market_open = ToTime(Time[0]) >= 040000 && ToTime(Time[0]) <= 210000;

            if (isLongPosition)
            {
                if (IsExitConditionMet())
                {
                    ExitLongLimit(0, true, Position.Quantity, GetCurrentAsk(), "Exit", "LongEntry");
                    isLongPosition = false;
                    Draw.ArrowDown(this, "SellSignal" + CurrentBar, true, 0, High[0] + TickSize, Brushes.Red);
                    SendSignalToBot("sell", Instrument.FullName, Position.Quantity, GetCurrentBid(), GetCurrentAsk());
                }
                else if (Close[0] >= lastPartialProfitPrice + 0.15 && Position.Quantity > 100)
                {
                    int exitQuantity = Math.Min(25, Position.Quantity - 100);
                    ExitLongLimit(0, true, exitQuantity, GetCurrentAsk(), "PartialProfit", "LongEntry");
                    lastPartialProfitPrice = Close[0];
                    SendSignalToBot("sell", Instrument.FullName, exitQuantity, GetCurrentBid(), GetCurrentAsk());
                }
                else if (Close[0] <= lastPartialProfitPrice - 0.10)
                {
                    ExitLong("StopLoss", "LongEntry");
                    isLongPosition = false;
                    Draw.ArrowDown(this, "StopLossSignal" + CurrentBar, true, 0, High[0] + TickSize, Brushes.Red);
                    SendSignalToBot("sell", Instrument.FullName, Position.Quantity, GetCurrentBid(), GetCurrentAsk());
                }
            }
            else if (market_open && IsLongEntryConditionMet())
            {
                EnterLongLimit(0, true, 200, GetCurrentAsk(), "LongEntry");
                entryPrice = Close[0];
                lastPartialProfitPrice = entryPrice;
                isLongPosition = true;
                Draw.ArrowUp(this, "BuySignal" + CurrentBar, true, 0, Low[0] - TickSize, Brushes.Green);
                SendSignalToBot("buy", Instrument.FullName, 200, GetCurrentBid(), GetCurrentAsk());
            }
        }

        private bool IsLongEntryConditionMet()
        {
            return macd[0] > 0 &&
                   macd.Diff[0] > 0 &&
                   !CrossBelow(macd.Diff, macd.Avg, 1) &&
                   Close[0] > ema200[0] &&
                   Close[0] > sma200[0] &&
                   Close[0] > ema9[0] &&
                   obv[0] > obv[1] &&
                   Close[0] > vwap[0] &&
                   Close[0] > ema20[0] &&
                   Close[1] > ema20[0];
        }

        private bool IsExitConditionMet()
        {
            return Close[0] < ema20[0] && Close[1] < ema20[0];
        }

        private async Task SendSignalToBot(string signal, string symbol, int quantity, double bidPrice, double askPrice)
        {
            var payloadString = $"{{\"signal\":\"{signal}\",\"symbol\":\"{symbol}\",\"quantity\":{quantity},\"bidPrice\":{bidPrice},\"askPrice\":{askPrice}}}";
            var content = new StringContent(payloadString, Encoding.UTF8, "application/json");

            try
            {
                HttpResponseMessage response = await client.PostAsync("http://localhost:5000/send_signal", content);
                if (response.IsSuccessStatusCode)
                    Print($"Successfully sent {signal} signal for {symbol}");
                else
                    Print($"Failed to send signal: {response.ReasonPhrase}");
            }
            catch (Exception ex)
            {
                Print($"Error sending signal: {ex.Message}");
            }
        }

        private double GetCurrentBid() => GetCurrentBid(0);
        private double GetCurrentAsk() => GetCurrentAsk(0);
    }
}
