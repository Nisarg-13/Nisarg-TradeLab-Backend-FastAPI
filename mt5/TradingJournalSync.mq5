//+------------------------------------------------------------------+
//| TradingJournalSync.mq5                                           |
//| Nisarg's TradeLab — MT5 → backend sync (read-only)               |
//+------------------------------------------------------------------+
#property copyright "Nisarg's TradeLab"
#property link      "https://github.com/Nisarg-13/Nisarg-TradeLab-Backend-FastAPI"
#property version   "1.20"
#property description "Syncs deals, positions, and account data to TradeLab."

input string InpApiBaseUrl          = "https://your-backend.example.com";
input string InpConnectionKey         = "TJ_your_connection_key";
input int    InpSyncIntervalSeconds = 1;
input int    InpHistoryDays         = 90;

const string EA_VERSION = "1.2.0";
const int    DEAL_CHUNK_SIZE = 250;
const int    DEAL_REQUEST_TIMEOUT_MS = 120000;

bool     g_connected = false;
bool     g_initialSyncDone = false;
bool     g_historicalDealsDone = false;
ulong    g_lastDealTicket = 0;
int      g_syncTick = 0;

//+------------------------------------------------------------------+
string TrimTrailingSlash(string url)
  {
   while(StringLen(url) > 0 && StringGetCharacter(url, StringLen(url) - 1) == '/')
      url = StringSubstr(url, 0, StringLen(url) - 1);
   return url;
  }

//+------------------------------------------------------------------+
string FormatIso8601(datetime value)
  {
   MqlDateTime parts;
   datetime utc = value - (TimeCurrent() - TimeGMT());
   if(!TimeToStruct(utc, parts))
      return "";
   return StringFormat(
      "%04d-%02d-%02dT%02d:%02d:%02d.000Z",
      parts.year, parts.mon, parts.day,
      parts.hour, parts.min, parts.sec
   );
  }

//+------------------------------------------------------------------+
string JsonEscape(string value)
  {
   StringReplace(value, "\\", "\\\\");
   StringReplace(value, "\"", "\\\"");
   StringReplace(value, "\r", "\\r");
   StringReplace(value, "\n", "\\n");
   StringReplace(value, "%", "%%");
   return value;
  }

//+------------------------------------------------------------------+
string ApiBaseUrl()
  {
   return TrimTrailingSlash(InpApiBaseUrl);
  }

//+------------------------------------------------------------------+
bool PostJson(const string path, const string json, string &responseBody, int &httpStatus, int timeoutMs = 30000)
  {
   if(StringLen(InpConnectionKey) < 4 || StringFind(InpConnectionKey, "TJ_") != 0)
     {
      Print("TradeLab: ConnectionKey must start with TJ_");
      return false;
     }

   string url = ApiBaseUrl() + path;
   string headers =
      "Content-Type: application/json\r\n"
      "Authorization: Bearer " + InpConnectionKey + "\r\n";

   char data[];
   char result[];
   string resultHeaders;

   int bytes = StringToCharArray(json, data, 0, WHOLE_ARRAY, CP_UTF8);
   if(bytes > 0)
      ArrayResize(data, bytes - 1);

   ResetLastError();
   httpStatus = WebRequest("POST", url, headers, timeoutMs, data, result, resultHeaders);

   if(httpStatus == -1)
     {
      int err = GetLastError();
      Print("TradeLab WebRequest failed (", err, "). URL=", url);
      if(err == 4060 || err == 4014)
         Print("TradeLab: Add ", ApiBaseUrl(), " to Tools -> Options -> Expert Advisors -> Allow WebRequest for listed URL, then restart MT5.");
      return false;
     }

   responseBody = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);

   if(httpStatus < 200 || httpStatus >= 300)
     {
      Print("TradeLab HTTP ", httpStatus, " for ", path, " response=", responseBody);
      if(httpStatus == 1003)
         Print("TradeLab: request timed out after ", timeoutMs, "ms — retrying on next timer.");
      return false;
     }

   return true;
  }

//+------------------------------------------------------------------+
string MapAssetClass(const string symbol)
  {
   string upper = symbol;
   StringToUpper(upper);
   if(StringFind(upper, "XAU") >= 0 || StringFind(upper, "GOLD") >= 0)
      return "COMMODITY";
   if(StringFind(upper, "XAG") >= 0 || StringFind(upper, "SILVER") >= 0)
      return "COMMODITY";
   if(StringFind(upper, "BTC") >= 0 || StringFind(upper, "ETH") >= 0)
      return "CRYPTO";
   if(StringFind(upper, "US30") >= 0 || StringFind(upper, "NAS") >= 0 || StringFind(upper, "SPX") >= 0)
      return "INDEX";
   return "FOREX";
  }

//+------------------------------------------------------------------+
bool ResolvePositionDirection(const ulong positionId, string &direction)
  {
   if(!HistorySelectByPosition(positionId))
      return false;

   const int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      const ulong ticket = HistoryDealGetTicket(i);
      const ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_IN && entry != DEAL_ENTRY_INOUT)
         continue;

      const ENUM_DEAL_TYPE type = (ENUM_DEAL_TYPE)HistoryDealGetInteger(ticket, DEAL_TYPE);
      direction = (type == DEAL_TYPE_BUY) ? "LONG" : "SHORT";
      return true;
     }

   return false;
  }

//+------------------------------------------------------------------+
void ApplyOrderSlTp(const ulong orderTicket, double &sl, double &tp)
  {
   double orderSl = 0;
   double orderTp = 0;
   HistoryOrderGetDouble(orderTicket, ORDER_SL, orderSl);
   HistoryOrderGetDouble(orderTicket, ORDER_TP, orderTp);

   if(orderSl > 0)
      sl = orderSl;
   if(orderTp > 0)
      tp = orderTp;

   const ENUM_ORDER_TYPE orderType = (ENUM_ORDER_TYPE)HistoryOrderGetInteger(orderTicket, ORDER_TYPE);
   double orderPrice = 0;
   HistoryOrderGetDouble(orderTicket, ORDER_PRICE_OPEN, orderPrice);

   if(orderPrice <= 0)
      return;

   if(orderType == ORDER_TYPE_BUY_STOP || orderType == ORDER_TYPE_SELL_STOP)
     {
      if(sl <= 0)
         sl = orderPrice;
     }
  }

//+------------------------------------------------------------------+
void ApplyDealSlTp(const ulong dealTicket, double &sl, double &tp)
  {
   double dealSl = 0;
   double dealTp = 0;
   HistoryDealGetDouble(dealTicket, DEAL_SL, dealSl);
   HistoryDealGetDouble(dealTicket, DEAL_TP, dealTp);

   if(dealSl > 0)
      sl = dealSl;
   if(dealTp > 0)
      tp = dealTp;
  }

//+------------------------------------------------------------------+
void ScanPositionOrdersAndDeals(const ulong positionId, const bool filterByPositionId, double &sl, double &tp)
  {
   const int ordersTotal = HistoryOrdersTotal();
   for(int i = 0; i < ordersTotal; i++)
     {
      const ulong orderTicket = HistoryOrderGetTicket(i);
      if(orderTicket == 0)
         continue;

      if(filterByPositionId)
        {
         const ulong orderPositionId = (ulong)HistoryOrderGetInteger(orderTicket, ORDER_POSITION_ID);
         if(orderPositionId != 0 && orderPositionId != positionId)
            continue;
        }

      ApplyOrderSlTp(orderTicket, sl, tp);
     }

   const int dealsTotal = HistoryDealsTotal();
   for(int i = 0; i < dealsTotal; i++)
     {
      const ulong dealTicket = HistoryDealGetTicket(i);
      if((ulong)HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID) != positionId)
         continue;

      ApplyDealSlTp(dealTicket, sl, tp);

      const ulong orderTicket = (ulong)HistoryDealGetInteger(dealTicket, DEAL_ORDER);
      if(orderTicket > 0)
         ApplyOrderSlTp(orderTicket, sl, tp);

      const ENUM_DEAL_ENTRY dealEntry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);

      if(dealEntry != DEAL_ENTRY_OUT && dealEntry != DEAL_ENTRY_OUT_BY)
         continue;

      const ENUM_DEAL_REASON reason = (ENUM_DEAL_REASON)HistoryDealGetInteger(dealTicket, DEAL_REASON);
      double dealPrice = 0;
      HistoryDealGetDouble(dealTicket, DEAL_PRICE, dealPrice);

      if(dealPrice <= 0)
         continue;

      if(reason == DEAL_REASON_SL && sl <= 0)
         sl = dealPrice;

      if(reason == DEAL_REASON_TP && tp <= 0)
         tp = dealPrice;
     }
  }

//+------------------------------------------------------------------+
bool GetPositionMeta(const ulong positionId, string &symbol, datetime &openedAt)
  {
   symbol = "";
   openedAt = 0;

   const int dealsTotal = HistoryDealsTotal();
   for(int i = 0; i < dealsTotal; i++)
     {
      const ulong dealTicket = HistoryDealGetTicket(i);
      if((ulong)HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID) != positionId)
         continue;

      const ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_IN && entry != DEAL_ENTRY_INOUT)
         continue;

      symbol = HistoryDealGetString(dealTicket, DEAL_SYMBOL);
      openedAt = (datetime)HistoryDealGetInteger(dealTicket, DEAL_TIME);
      return symbol != "";
     }

   return false;
  }

//+------------------------------------------------------------------+
bool ResolvePositionSlTp(const ulong positionId, double &sl, double &tp)
  {
   sl = 0;
   tp = 0;

   if(HistorySelectByPosition(positionId))
     {
      ScanPositionOrdersAndDeals(positionId, false, sl, tp);
      if(sl > 0 || tp > 0)
         return true;
     }

   const datetime from = TimeCurrent() - (datetime)(InpHistoryDays * 86400);
   if(!HistorySelect(from, TimeCurrent()))
      return false;

   ScanPositionOrdersAndDeals(positionId, true, sl, tp);
   return sl > 0 || tp > 0;
  }

//+------------------------------------------------------------------+
bool BuildDealJson(const ulong dealTicket, string &jsonObject)
  {
   if(!HistoryDealSelect(dealTicket))
      return false;

   const long entryRaw = HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
   const ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)entryRaw;
   if(entry != DEAL_ENTRY_IN && entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY && entry != DEAL_ENTRY_INOUT)
      return false;

   string entryType = "ENTRY";
   if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
      entryType = "EXIT";

   const ulong positionId = (ulong)HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);
   string direction = "LONG";
   if(!ResolvePositionDirection(positionId, direction))
     {
      const ENUM_DEAL_TYPE type = (ENUM_DEAL_TYPE)HistoryDealGetInteger(dealTicket, DEAL_TYPE);
      direction = (type == DEAL_TYPE_BUY) ? "LONG" : "SHORT";
     }

   const string symbol = HistoryDealGetString(dealTicket, DEAL_SYMBOL);
   const double volume = HistoryDealGetDouble(dealTicket, DEAL_VOLUME);
   const double price = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
   if(volume <= 0.0 || price <= 0.0)
      return false;
   const double profit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
   const double commission = HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);
   const double swap = HistoryDealGetDouble(dealTicket, DEAL_SWAP);
   const double fee = HistoryDealGetDouble(dealTicket, DEAL_FEE);
   const datetime executedAt = (datetime)HistoryDealGetInteger(dealTicket, DEAL_TIME);
   double sl = 0;
   double tp = 0;
   ApplyDealSlTp(dealTicket, sl, tp);

   if(sl <= 0 && tp <= 0)
      ResolvePositionSlTp(positionId, sl, tp);
   else
     {
      if(sl <= 0 || tp <= 0)
        {
         double resolvedSl = 0;
         double resolvedTp = 0;
         if(ResolvePositionSlTp(positionId, resolvedSl, resolvedTp))
           {
            if(sl <= 0)
               sl = resolvedSl;
            if(tp <= 0)
               tp = resolvedTp;
           }
        }
     }

   jsonObject = StringFormat(
      "{\"dealId\":\"%s\",\"positionId\":\"%s\",\"symbol\":\"%s\",\"direction\":\"%s\",\"entryType\":\"%s\",\"volume\":%.4f,\"price\":%.10f,\"profit\":%.2f,\"commission\":%.2f,\"swap\":%.2f,\"fee\":%.2f,\"executedAt\":\"%s\",\"assetClass\":\"%s\"",
      IntegerToString(dealTicket),
      IntegerToString(positionId),
      JsonEscape(symbol),
      direction,
      entryType,
      volume,
      price,
      profit,
      commission,
      swap,
      fee,
      FormatIso8601(executedAt),
      MapAssetClass(symbol)
   );

   if(sl > 0)
      jsonObject += StringFormat(",\"stopLoss\":%.10f", sl);
   if(tp > 0)
      jsonObject += StringFormat(",\"takeProfit\":%.10f", tp);

   jsonObject += "}";

   return true;
  }

//+------------------------------------------------------------------+
bool ConnectToTradeLab()
  {
   string body = StringFormat(
      "{\"mt5Login\":\"%I64d\",\"serverName\":\"%s\",\"brokerName\":\"%s\",\"currency\":\"%s\",\"balance\":%.2f,\"equity\":%.2f,\"leverage\":%d,\"accountType\":\"%s\",\"eaVersion\":\"%s\"}",
      AccountInfoInteger(ACCOUNT_LOGIN),
      JsonEscape(AccountInfoString(ACCOUNT_SERVER)),
      JsonEscape(AccountInfoString(ACCOUNT_COMPANY)),
      JsonEscape(AccountInfoString(ACCOUNT_CURRENCY)),
      AccountInfoDouble(ACCOUNT_BALANCE),
      AccountInfoDouble(ACCOUNT_EQUITY),
      (int)AccountInfoInteger(ACCOUNT_LEVERAGE),
      (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO) ? "DEMO" : "LIVE",
      EA_VERSION
   );

   string response;
   int status = 0;
   if(!PostJson("/api/v1/mt5/connect", body, response, status))
      return false;

   g_connected = true;
   Print("TradeLab: connected. ", response);
   return true;
  }

//+------------------------------------------------------------------+
bool SendHeartbeat()
  {
   string body = StringFormat("{\"eaVersion\":\"%s\"}", EA_VERSION);
   string response;
   int status = 0;
   return PostJson("/api/v1/mt5/heartbeat", body, response, status);
  }

//+------------------------------------------------------------------+
bool SendAccountSnapshot()
  {
   string body = StringFormat(
      "{\"balance\":%.2f,\"equity\":%.2f,\"currency\":\"%s\"}",
      AccountInfoDouble(ACCOUNT_BALANCE),
      AccountInfoDouble(ACCOUNT_EQUITY),
      JsonEscape(AccountInfoString(ACCOUNT_CURRENCY))
   );

   string response;
   int status = 0;
   return PostJson("/api/v1/mt5/account", body, response, status);
  }

//+------------------------------------------------------------------+
void AddUniqueSymbol(string &symbols[], const string symbol)
  {
   if(StringLen(symbol) < 1)
      return;

   for(int i = 0; i < ArraySize(symbols); i++)
      if(symbols[i] == symbol)
         return;

   const int size = ArraySize(symbols);
   ArrayResize(symbols, size + 1);
   symbols[size] = symbol;
  }

//+------------------------------------------------------------------+
void CollectSymbols(string &symbols[])
  {
   ArrayResize(symbols, 0);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
         AddUniqueSymbol(symbols, PositionGetString(POSITION_SYMBOL));
     }

   const datetime from = TimeCurrent() - (datetime)(MathMax(InpHistoryDays, 7) * 86400);
   if(HistorySelect(from, TimeCurrent()))
     {
      const int deals = HistoryDealsTotal();
      for(int i = 0; i < deals; i++)
        {
         const ulong dealTicket = HistoryDealGetTicket(i);
         AddUniqueSymbol(symbols, HistoryDealGetString(dealTicket, DEAL_SYMBOL));
        }
     }

   if(ArraySize(symbols) == 0)
      AddUniqueSymbol(symbols, _Symbol);
  }

//+------------------------------------------------------------------+
double SafePositive(const double value, const double fallback)
  {
   if(value > 0.0 && value == value)
      return value;
   return fallback;
  }

//+------------------------------------------------------------------+
double SafeNonNegative(const double value, const double fallback)
  {
   if(value >= 0.0 && value == value)
      return value;
   return fallback;
  }

//+------------------------------------------------------------------+
string BuildInstrumentJson(const string symbol)
  {
   if(!SymbolSelect(symbol, true))
      return "";

   const int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   const double point = SafePositive(SymbolInfoDouble(symbol, SYMBOL_POINT), MathPow(10, -MathMax(digits, 1)));
   const double tickSize = SafePositive(SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE), point);
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickValue <= 0.0 || tickValue != tickValue)
      tickValue = 1.0;

   const double contractSize = SafePositive(SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE), 1.0);
   const double volumeMin = SafeNonNegative(SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN), 0.01);
   const double volumeMax = SafePositive(SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX), MathMax(volumeMin, 100.0));
   const double volumeStep = SafePositive(SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP), MathMax(volumeMin, 0.01));

   return StringFormat(
      "{\"symbol\":\"%s\",\"description\":\"%s\",\"assetClass\":\"%s\",\"digits\":%d,\"point\":%.10f,\"tickSize\":%.10f,\"tickValueProfit\":%.6f,\"tickValueLoss\":%.6f,\"contractSize\":%.2f,\"volumeMin\":%.4f,\"volumeMax\":%.4f,\"volumeStep\":%.4f}",
      JsonEscape(symbol),
      JsonEscape(symbol),
      MapAssetClass(symbol),
      digits,
      point,
      tickSize,
      tickValue,
      tickValue,
      contractSize,
      volumeMin,
      volumeMax,
      volumeStep
   );
  }

//+------------------------------------------------------------------+
bool SendInstruments()
  {
   string symbols[];
   CollectSymbols(symbols);

   string json = "{\"instruments\":[";
   bool first = true;
   for(int i = 0; i < ArraySize(symbols); i++)
     {
      string item = BuildInstrumentJson(symbols[i]);
      if(item == "")
         continue;
      if(!first)
         json += ",";
      json += item;
      first = false;
     }

   if(first)
     {
      string item = BuildInstrumentJson(_Symbol);
      if(item != "")
        {
         json += item;
         first = false;
        }
     }

   if(first)
     {
      Print("TradeLab: no instrument specs available — skipping instrument sync.");
      return true;
     }

   json += "]}";

   string response;
   int status = 0;
   return PostJson("/api/v1/mt5/instruments", json, response, status);
  }

//+------------------------------------------------------------------+
bool SendDealsChunk(const ulong &tickets[], const int start, const int count)
  {
   if(count <= 0)
      return true;

   string json = "{\"deals\":[";
   bool first = true;
   int added = 0;

   for(int i = start; i < start + count && i < ArraySize(tickets); i++)
     {
      string dealJson;
      if(!BuildDealJson(tickets[i], dealJson))
         continue;

      if(!first)
         json += ",";
      json += dealJson;
      first = false;
      added++;
     }

   json += "]}";

   if(added == 0)
      return true;

   string response;
   int status = 0;
   if(!PostJson("/api/v1/mt5/deals", json, response, status, DEAL_REQUEST_TIMEOUT_MS))
      return false;

   Print("TradeLab: imported deals chunk (", added, "). ", response);
   return true;
  }

//+------------------------------------------------------------------+
bool AppendUniquePositionId(ulong &ids[], const ulong positionId)
  {
   if(positionId == 0)
      return false;

   for(int i = 0; i < ArraySize(ids); i++)
     {
      if(ids[i] == positionId)
         return false;
     }

   const int size = ArraySize(ids);
   ArrayResize(ids, size + 1);
   ids[size] = positionId;
   return true;
  }

//+------------------------------------------------------------------+
bool SendPositionLevelsChunk(const ulong &positionIds[], const int start, const int count)
  {
   if(count <= 0)
      return true;

   string json = "{\"levels\":[";
   bool first = true;
   int added = 0;

   for(int i = start; i < start + count && i < ArraySize(positionIds); i++)
     {
      double sl = 0;
      double tp = 0;
      if(!ResolvePositionSlTp(positionIds[i], sl, tp))
         continue;

      string symbol = "";
      datetime openedAt = 0;
      GetPositionMeta(positionIds[i], symbol, openedAt);

      string item = StringFormat("{\"positionId\":\"%s\"", IntegerToString(positionIds[i]));

      if(symbol != "")
         item += StringFormat(",\"symbol\":\"%s\"", JsonEscape(symbol));
      if(openedAt > 0)
         item += StringFormat(",\"openedAt\":\"%s\"", FormatIso8601(openedAt));

      if(sl > 0)
         item += StringFormat(",\"stopLoss\":%.10f", sl);
      if(tp > 0)
         item += StringFormat(",\"takeProfit\":%.10f", tp);

      item += "}";

      if(!first)
         json += ",";
      json += item;
      first = false;
      added++;
     }

   json += "]}";

   if(added == 0)
      return true;

   string response;
   int status = 0;
   if(!PostJson("/api/v1/mt5/position-levels", json, response, status))
      return false;

   Print("TradeLab: synced SL/TP levels (", added, "). ", response);
   return true;
  }

//+------------------------------------------------------------------+
bool SendHistoricalPositionLevels()
  {
   const datetime from = TimeCurrent() - (datetime)(InpHistoryDays * 86400);
   if(!HistorySelect(from, TimeCurrent()))
     {
      Print("TradeLab: HistorySelect failed for position level sync.");
      return false;
     }

   ulong positionIds[];
   ArrayResize(positionIds, 0);

   for(int i = 0; i < HistoryDealsTotal(); i++)
     {
      const ulong dealTicket = HistoryDealGetTicket(i);
      const ulong positionId = (ulong)HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);
      AppendUniquePositionId(positionIds, positionId);
     }

   Print("TradeLab: resolving SL/TP for ", ArraySize(positionIds), " historical positions...");

   for(int start = 0; start < ArraySize(positionIds); start += DEAL_CHUNK_SIZE)
     {
      const int count = MathMin(DEAL_CHUNK_SIZE, ArraySize(positionIds) - start);
      if(!SendPositionLevelsChunk(positionIds, start, count))
         return false;
     }

   return true;
  }

//+------------------------------------------------------------------+
bool ImportHistoricalDeals()
  {
   const datetime from = TimeCurrent() - (datetime)(InpHistoryDays * 86400);
   if(!HistorySelect(from, TimeCurrent()))
     {
      Print("TradeLab: HistorySelect failed for deal import.");
      return false;
     }

   const int total = HistoryDealsTotal();
   ulong tickets[];
   ArrayResize(tickets, 0);

   for(int i = 0; i < total; i++)
     {
      const ulong ticket = HistoryDealGetTicket(i);
      const int size = ArraySize(tickets);
      ArrayResize(tickets, size + 1);
      tickets[size] = ticket;
      if(ticket > g_lastDealTicket)
         g_lastDealTicket = ticket;
     }

   Print("TradeLab: importing ", ArraySize(tickets), " historical deals...");

   for(int start = 0; start < ArraySize(tickets); start += DEAL_CHUNK_SIZE)
     {
      const int count = MathMin(DEAL_CHUNK_SIZE, ArraySize(tickets) - start);
      if(!SendDealsChunk(tickets, start, count))
         return false;
     }

   return true;
  }

//+------------------------------------------------------------------+
bool SyncRecentDeals()
  {
   const datetime from = TimeCurrent() - 86400;
   if(!HistorySelect(from, TimeCurrent()))
      return false;

   ulong tickets[];
   ArrayResize(tickets, 0);

   const int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      const ulong ticket = HistoryDealGetTicket(i);
      if(ticket <= g_lastDealTicket)
         continue;

      const int size = ArraySize(tickets);
      ArrayResize(tickets, size + 1);
      tickets[size] = ticket;
     }

   if(ArraySize(tickets) == 0)
      return true;

   ArraySort(tickets);

   for(int start = 0; start < ArraySize(tickets); start += DEAL_CHUNK_SIZE)
     {
      const int count = MathMin(DEAL_CHUNK_SIZE, ArraySize(tickets) - start);
      if(!SendDealsChunk(tickets, start, count))
         return false;
      g_lastDealTicket = tickets[start + count - 1];
     }

   return true;
  }

//+------------------------------------------------------------------+
bool SendOpenPositions()
  {
   string json = "{\"positions\":[";
   bool first = true;
   const datetime snapshotAt = TimeCurrent();

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket))
         continue;

      const ulong positionId = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      const string symbol = PositionGetString(POSITION_SYMBOL);
      const ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      const string direction = (posType == POSITION_TYPE_BUY) ? "LONG" : "SHORT";
      const double volume = PositionGetDouble(POSITION_VOLUME);
      const double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      const double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      const double floatingPnl = PositionGetDouble(POSITION_PROFIT);
      const double swap = PositionGetDouble(POSITION_SWAP);
      const datetime openedAt = (datetime)PositionGetInteger(POSITION_TIME);

      string item = StringFormat(
         "{\"positionId\":\"%s\",\"symbol\":\"%s\",\"direction\":\"%s\",\"volume\":%.4f,\"openPrice\":%.10f,\"currentPrice\":%.10f",
         IntegerToString(positionId),
         JsonEscape(symbol),
         direction,
         volume,
         openPrice,
         currentPrice
      );

      if(sl > 0)
         item += StringFormat(",\"stopLoss\":%.10f", sl);
      if(tp > 0)
         item += StringFormat(",\"takeProfit\":%.10f", tp);

      item += StringFormat(
         ",\"floatingPnl\":%.2f,\"swap\":%.2f,\"openedAt\":\"%s\",\"snapshotAt\":\"%s\",\"assetClass\":\"%s\"}",
         floatingPnl,
         swap,
         FormatIso8601(openedAt),
         FormatIso8601(snapshotAt),
         MapAssetClass(symbol)
      );

      if(!first)
         json += ",";
      json += item;
      first = false;
     }

   json += "]}";

   string response;
   int status = 0;
   if(first)
     {
      Print("TradeLab: syncing 0 open positions.");
      return PostJson("/api/v1/mt5/positions", json, response, status);
     }

   if(!PostJson("/api/v1/mt5/positions", json, response, status))
     {
      Print("TradeLab: open position sync failed.");
      return false;
     }

   Print("TradeLab: open position sync ok.");
   return true;
  }

//+------------------------------------------------------------------+
bool RunInitialSync()
  {
   if(!ConnectToTradeLab())
      return false;

   SendAccountSnapshot();

   if(!SendInstruments())
      Print("TradeLab: instrument sync failed — continuing with deal import.");

   // Sync live prices first — must not wait on historical deal import.
   if(!SendOpenPositions())
      Print("TradeLab: open position sync failed — will retry on timer.");

   bool dealsOk = ImportHistoricalDeals();
   if(!dealsOk)
      Print("TradeLab: historical deal import failed — will retry on timer.");
   else
     {
      g_historicalDealsDone = true;
      if(!SendHistoricalPositionLevels())
         Print("TradeLab: historical SL/TP sync failed — will retry on next attach.");
     }

   g_initialSyncDone = true;
   Print("TradeLab: initial sync complete.");
   return dealsOk;
  }

//+------------------------------------------------------------------+
bool RunPeriodicSync()
  {
   if(!g_connected)
      return ConnectToTradeLab();

   g_syncTick++;

   // Heartbeat, balance, and deal catch-up every 30s; positions every tick.
   if(g_syncTick == 1 || g_syncTick >= 30)
     {
      SendHeartbeat();
      SendAccountSnapshot();
      SyncRecentDeals();
      if(!g_historicalDealsDone)
        {
         if(ImportHistoricalDeals())
           {
            g_historicalDealsDone = true;
            SendHistoricalPositionLevels();
           }
        }
      g_syncTick = 0;
     }

   if(!SendOpenPositions())
      Print("TradeLab: open position sync failed — retrying on next timer.");
   return true;
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(StringFind(ApiBaseUrl(), "https://") != 0)
     {
      Print("TradeLab: ApiBaseUrl must start with https://");
      return INIT_PARAMETERS_INCORRECT;
     }

   if(StringFind(InpConnectionKey, "TJ_") != 0)
     {
      Print("TradeLab: paste your TJ_ connection key from TradeLab Accounts.");
      return INIT_PARAMETERS_INCORRECT;
     }

   if(InpSyncIntervalSeconds < 1)
     {
      Print("TradeLab: SyncIntervalSeconds must be at least 1.");
      return INIT_PARAMETERS_INCORRECT;
     }

   EventSetTimer(InpSyncIntervalSeconds);

   if(!RunInitialSync())
     {
      Print("TradeLab: initial sync failed — will retry on timer.");
     }

   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   if(!g_initialSyncDone)
     {
      RunInitialSync();
      return;
     }

   RunPeriodicSync();
  }

//+------------------------------------------------------------------+
void OnTradeTransaction(
   const MqlTradeTransaction &trans,
   const MqlTradeRequest &request,
   const MqlTradeResult &result
)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD)
      return;

   const ulong dealTicket = trans.deal;
   if(dealTicket == 0)
      return;

   ulong tickets[1];
   tickets[0] = dealTicket;
   SendDealsChunk(tickets, 0, 1);

   if(dealTicket > g_lastDealTicket)
      g_lastDealTicket = dealTicket;

   SendOpenPositions();
  }

//+------------------------------------------------------------------+
