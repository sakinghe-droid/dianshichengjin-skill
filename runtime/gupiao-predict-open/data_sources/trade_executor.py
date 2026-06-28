"""
trade_executor.py — 交易执行器 (N4)

封装 mx-moni 模拟交易 API，提供:
  - get_position():      查询持仓/资产
  - buy(code, qty, price):  买入
  - sell(code, qty, price): 卖出
  - get_orders():        查询委托记录
  - record_operation():  写入操作日志 (供W6复盘)

用法:
    from data_sources.trade_executor import TradeExecutor
    t = TradeExecutor()
    t.buy("000001", 100, 10.23)
"""

import os, sys, json, time, requests
from typing import Dict, List, Optional
from datetime import datetime

MX_API_URL = os.environ.get('MX_API_URL', 'https://mkapi2.dfcfs.com/finskillshub')
MX_APIKEY = os.environ.get('MX_APIKEY', '')
OP_LOG_DIR = os.path.expanduser("~/.hermes/trade_logs")


class TradeExecutor:
    """妙想模拟交易执行器"""
    
    def __init__(self):
        os.makedirs(OP_LOG_DIR, exist_ok=True)
    
    def _api(self, endpoint: str, payload: dict) -> Optional[dict]:
        """调用妙想 API"""
        try:
            r = requests.post(
                f"{MX_API_URL}{endpoint}",
                headers={'apikey': MX_APIKEY, 'Content-Type': 'application/json; charset=UTF-8'},
                json=payload, timeout=30
            )
            return r.json()
        except Exception as e:
            print(f"[ERROR] API {endpoint}: {e}")
            return None
    
    def get_position(self) -> dict:
        """查询持仓和资产"""
        result = self._api('/api/claw/mockTrading/positions', {'moneyUnit': 1})
        if not result or str(result.get('code')) not in ('0', '200'):
            return {"total_asset": 0, "available": 0, "holdings": []}
        
        data = result.get('data', {})
        return {
            "total_asset": data.get('totalAssets', 0),
            "available": data.get('availBalance', 0),
            "market_value": data.get('totalPosValue', 0),
            "total_pnl": data.get('totalProfit', 0),
            "holdings": [
                {
                    "code": h.get('stockCode', ''),
                    "name": h.get('secName', ''),
                    "shares": h.get('quantity', 0),
                    "cost": h.get('costPrice', 0),
                    "price": h.get('price', 0),
                    "pnl": h.get('pnlAmt', 0),
                }
                for h in data.get('posList', [])
            ],
        }
    
    def buy(self, code: str, quantity: int, price: Optional[float] = None) -> dict:
        """买入股票"""
        payload = {
            'type': 'buy',
            'stockCode': code,
            'quantity': quantity,
            'useMarketPrice': price is None,
        }
        if price is not None:
            decimals = 2 if code[0] in ('6', '9') else 3
            payload['price'] = int(round(price * (10 ** decimals)))
        
        result = self._api('/api/claw/mockTrading/trade', payload)
        self._log("BUY", code, quantity, price, result)
        return result or {}
    
    def sell(self, code: str, quantity: int, price: Optional[float] = None) -> dict:
        """卖出股票"""
        payload = {
            'type': 'sell',
            'stockCode': code,
            'quantity': quantity,
            'useMarketPrice': price is None,
        }
        if price is not None:
            decimals = 2 if code[0] in ('6', '9') else 3
            payload['price'] = int(round(price * (10 ** decimals)))
        
        result = self._api('/api/claw/mockTrading/trade', payload)
        self._log("SELL", code, quantity, price, result)
        return result or {}
    
    def get_orders(self, days: int = 1) -> list:
        """查询委托记录"""
        result = self._api('/api/claw/mockTrading/orders', {'fltOrderDrt': 0, 'fltOrderStatus': 0})
        if not result or result.get('code') != 0:
            return []
        
        orders = result.get('data', {}).get('orders', [])
        return [
            {
                "id": o.get('id', '')[:18],
                "code": o.get('stockCode', ''),
                "name": o.get('secName', ''),
                "type": "买入" if o.get('drt', 0) == 1 else "卖出",
                "price": o.get('price', 0) / (10 ** o.get('priceDec', 2)),
                "qty": o.get('quantity', 0),
                "status": o.get('status', 0),
                "time": o.get('createTime', ''),
            }
            for o in orders
        ]
    
    def cancel_all(self) -> dict:
        """一键撤单"""
        return self._api('/api/claw/mockTrading/cancel', {'type': 'all'}) or {}
    
    # ========== 操作日志 ==========
    
    def _log(self, action: str, code: str, qty: int, price: Optional[float], result: dict):
        """写入操作日志"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = f"{OP_LOG_DIR}/operations_{today}.jsonl"
        
        entry = {
            "time": datetime.now().isoformat(),
            "action": action,
            "code": code,
            "quantity": qty,
            "price": price,
            "success": result.get('code') == 0 if result else False,
            "message": result.get('msg', '') if result else 'API failed',
        }
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def get_daily_log(self, date: str = None) -> list:
        """读取某天的操作日志"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        log_file = f"{OP_LOG_DIR}/operations_{date}.jsonl"
        if not os.path.exists(log_file):
            return []
        
        entries = []
        with open(log_file) as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
        return entries
    
    def get_all_logs(self, days: int = 7) -> dict:
        """读取近N天的操作日志"""
        from datetime import timedelta
        logs = {}
        for i in range(days):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            entries = self.get_daily_log(d)
            if entries:
                logs[d] = entries
        return logs


# ========== CLI ==========
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="交易执行器")
    p.add_argument("--position", action="store_true", help="查询持仓")
    p.add_argument("--orders", action="store_true", help="查询委托")
    p.add_argument("--buy", help="买入: code,qty[,price]")
    p.add_argument("--sell", help="卖出: code,qty[,price]")
    p.add_argument("--cancel-all", action="store_true", help="一键撤单")
    p.add_argument("--log", action="store_true", help="查看今日操作日志")
    args = p.parse_args()
    
    t = TradeExecutor()
    
    if args.position:
        pos = t.get_position()
        print(json.dumps(pos, ensure_ascii=False, indent=2))
    
    if args.orders:
        orders = t.get_orders()
        print(f"委托记录: {len(orders)} 条")
        for o in orders:
            print(f"  {o['time']} {o['type']} {o['name']}({o['code']}) {o['qty']}股 @{o['price']}")
    
    if args.buy:
        parts = args.buy.split(',')
        code, qty = parts[0], int(parts[1])
        price = float(parts[2]) if len(parts) > 2 else None
        r = t.buy(code, qty, price)
        print(f"买入 {code} {qty}股: {'✅' if r.get('code')==0 else '❌'+r.get('msg','')}")
    
    if args.sell:
        parts = args.sell.split(',')
        code, qty = parts[0], int(parts[1])
        price = float(parts[2]) if len(parts) > 2 else None
        r = t.sell(code, qty, price)
        print(f"卖出 {code} {qty}股: {'✅' if r.get('code')==0 else '❌'+r.get('msg','')}")
    
    if args.cancel_all:
        t.cancel_all()
        print("✅ 已撤单")
    
    if args.log:
        entries = t.get_daily_log()
        print(f"今日操作: {len(entries)} 条")
        for e in entries:
            print(f"  {e['time']} {e['action']} {e['code']} {e['quantity']}股")
