"""
tdx_mcp.py — 通达信 MCP 数据客户端

封装 wenda-mcp-server 的 SSE 传输协议，提供结构化查询接口。

用法:
    from data_sources.tdx_mcp import TDXClient
    tdx = TDXClient()
    stocks = tdx.query("今日涨停股票", size=100)
    indicators = tdx.query_indicators("000001")
"""

import requests, json, re, time
from typing import Dict, List, Optional, Any


class TDXClient:
    """通达信 MCP 客户端"""
    
    BASE = "https://mcp.tdx.com.cn:3001"
    
    def __init__(self, api_key: str = "TDX-b0696b2392e0c80e42d1a68196e01ebe"):
        self.api_key = api_key
        self.session_id: Optional[str] = None
        self._session = requests.Session()
        self._init_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
            'tdx-api-key': api_key,
        }
        self._reconnect()
    
    def _reconnect(self):
        """建立 MCP 会话"""
        r = self._session.post(
            f'{self.BASE}/mcp',
            json={
                'jsonrpc': '2.0', 'method': 'initialize', 'id': 1,
                'params': {
                    'protocolVersion': '2025-03-26',
                    'capabilities': {},
                    'clientInfo': {'name': 'hermes-agent', 'version': '2.0'},
                }
            },
            headers=self._init_headers,
            timeout=15,
        )
        self.session_id = r.headers.get('Mcp-Session-Id', '')
    
    def _call(self, question: str, range_val: str = "AG",
              page: int = 1, size: int = 100, retries: int = 1) -> Optional[Dict]:
        """调用 tdx_wenda_quotes 工具"""
        headers = {
            **self._init_headers,
            'Mcp-Session-Id': self.session_id or '',
        }
        
        for attempt in range(retries + 1):
            try:
                r = self._session.post(
                    f'{self.BASE}/mcp',
                    json={
                        'jsonrpc': '2.0', 'method': 'tools/call', 'id': 2,
                        'params': {
                            'name': 'tdx_wenda_quotes',
                            'arguments': {
                                'question': question,
                                'range': range_val,
                                'page': page,
                                'size': size,
                            }
                        }
                    },
                    headers=headers,
                    timeout=30,
                )
                
                # Parse SSE response
                match = re.search(r'data:\s*(\{.*\})', r.text, re.DOTALL)
                if match:
                    # 修复: ensure_ascii=False 保留中文
                    result = json.loads(match.group(1))
                    
                    # 修复编码: 遍历所有字符串值确保UTF-8
                    def fix_encoding(obj):
                        if isinstance(obj, dict):
                            return {fix_encoding(k): fix_encoding(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [fix_encoding(v) for v in obj]
                        elif isinstance(obj, str):
                            try:
                                # 如果字符串是 Latin-1 误解释的 UTF-8，修复它
                                return obj.encode('latin-1').decode('utf-8')
                            except (UnicodeEncodeError, UnicodeDecodeError):
                                return obj
                        return obj
                    
                    result = fix_encoding(result)
                    
                    # Check for errors
                    if 'error' in result:
                        err_msg = result['error'].get('message', '')
                        if 'session' in err_msg.lower():
                            self._reconnect()
                            headers['Mcp-Session-Id'] = self.session_id or ''
                            continue
                        return None
                    
                    return result
                
                # Try direct JSON parse
                try:
                    return r.json()
                except:
                    pass
                
            except requests.RequestException:
                if attempt < retries:
                    time.sleep(1)
                    self._reconnect()
                    headers['Mcp-Session-Id'] = self.session_id or ''
                    continue
        
        return None
    
    def _parse_table(self, result: Dict) -> Dict:
        """解析 MCP 响应中的结构化表格数据"""
        if not result:
            return {"headers": [], "data": [], "total": 0}
        
        content = result.get('result', {}).get('content', [])
        for item in content:
            if item.get('type') == 'text':
                try:
                    d = json.loads(item['text'])
                    if isinstance(d, dict) and 'data' in d:
                        return {
                            "headers": d.get('headers', []),
                            "data": d.get('data', []),
                            "total": d.get('meta', {}).get('total', len(d.get('data', []))),
                            "meta": d.get('meta', {}),
                        }
                except (json.JSONDecodeError, TypeError):
                    pass
            elif item.get('type') == 'resource':
                try:
                    txt = item.get('resource', {}).get('text', '')
                    d = json.loads(txt)
                    if isinstance(d, dict) and 'data' in d:
                        return {
                            "headers": d.get('headers', []),
                            "data": d.get('data', []),
                            "total": d.get('meta', {}).get('total', len(d.get('data', []))),
                        }
                except:
                    pass
        
        return {"headers": [], "data": [], "total": 0}
    
    # ============================================================
    # 高级查询接口
    # ============================================================
    
    def query(self, question: str, range_val: str = "AG",
              page: int = 1, size: int = 100) -> Dict:
        """通用查询，返回解析后的表格"""
        result = self._call(question, range_val, page, size)
        return self._parse_table(result)
    
    def get_limit_up_stocks(self, size: int = 200) -> List[Dict]:
        """获取今日涨停股列表"""
        table = self.query("今日涨停股票", size=size)
        return self._rows_to_dicts(table)
    
    def get_sector_stocks(self, sector_name: str, size: int = 500) -> List[Dict]:
        """获取行业/概念板块成分股"""
        table = self.query(f"{sector_name}行业板块成分股涨幅排名", size=size)
        return self._rows_to_dicts(table)
    
    def get_full_market(self, pages: int = 3, size: int = 100) -> List[Dict]:
        """获取全市场股票（多页）"""
        all_stocks = []
        for p in range(1, pages + 1):
            table = self.query("全市场股票行情", page=p, size=size)
            stocks = self._rows_to_dicts(table)
            if not stocks:
                break
            all_stocks.extend(stocks)
        return all_stocks
    
    def query_indicators(self, code: str) -> Dict:
        """查询个股技术指标 (RSI/MACD/KDJ)"""
        table = self.query(f"{code} RSI MACD KDJ 技术指标", size=1)
        rows = table.get('data', [])
        headers = table.get('headers', [])
        if not rows:
            return {}
        
        row = rows[0]
        result = {}
        for i, h in enumerate(headers):
            if i < len(row):
                result[h] = row[i]
        return result
    
    def query_financials(self, code: str) -> Dict:
        """查询个股财务指标 (PE/PB/ROE)"""
        table = self.query(f"{code} PE PB ROE 市净率 财务指标", size=1)
        rows = table.get('data', [])
        headers = table.get('headers', [])
        if not rows:
            return {}
        
        row = rows[0]
        result = {}
        for i, h in enumerate(headers):
            if i < len(row):
                result[h] = row[i]
        return result
    
    def get_capital_flow(self, size: int = 100) -> List[Dict]:
        """获取主力资金净流入排名"""
        table = self.query("今日主力资金净流入排名", size=size)
        return self._rows_to_dicts(table)
    
    def get_market_breadth(self) -> Dict:
        """获取市场涨跌家数"""
        table = self.query("今日市场上涨家数下跌家数统计", size=5)
        return table
    
    # ============================================================
    # 工具函数
    # ============================================================
    
    def _rows_to_dicts(self, table: Dict) -> List[Dict]:
        """将表格数据转为字典列表"""
        headers = table.get('headers', [])
        data = table.get('data', [])
        result = []
        for row in data:
            d = {}
            for i, h in enumerate(headers):
                if i < len(row):
                    d[h] = row[i]
            result.append(d)
        return result
    
    # 常用字段映射
    FIELD_MAP = {
        'sec_code': 'code',
        'sec_name': 'name', 
        'now_price': 'price',
        'chg': 'change_pct',
    }
    
    def normalize_stock(self, raw: Dict) -> Dict:
        """标准化股票数据字段名"""
        s = {}
        for k, v in raw.items():
            new_k = self.FIELD_MAP.get(k, k)
            s[new_k] = v
        
        # 类型转换
        if 'price' in s:
            try: s['price'] = float(s['price'])
            except: pass
        if 'change_pct' in s:
            try: s['change_pct'] = float(s['change_pct'])
            except: pass
        
        return s
