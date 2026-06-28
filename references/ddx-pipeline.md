# DDX 数据管道

## 四级降级链

```
① 妙想 mx-data → 多周期 DDX (3日/5日/10日)
   查询: "{CODE} 近10日DDX DDY 主力资金DDE大单净量"
   输出: Excel (.xlsx) → 读 sheet "3日DDX/5日DDX/10日DDX"
   字段: 3日DDX, 5日DDX, 10日DDX, DDY, 市盈率
   API: POST https://mkapi2.dfcfs.com/finskillshub/api/claw/query
   Key: 环境变量 MX_APIKEY

② TDX MCP 大单 → 单日大单净额 DDX
   查询: "{CODE} 大单买入 大单卖出 超大单买入"
   字段: 大单净额(元), 超大单净额(元)
   计算: DDX = |大单净额| / (成交额×20) × 100
         成交额来自 data_fallback quote/kline

③ L2大单 + ddx_calculator → 额基近似
   查询: data_fallback --mode l2 --code {CODE}
   字段: big_order.net_amount
   计算: ddx_calculator.calculate_ddx_from_amount(
           main_net_inflow, float_shares, current_price)

④ 标注缺失 → "⚠️ 未获取到DDX数据, DDX一票否决不可用"
   绝不使用硬编码默认值 0.5/0.3
```

## mx-data 查询注意事项

- 查询词必须包含 "DDE大单净量" 才返回 DDX 表格
- 查询词包含股票名称 (如"飞沃科技") 可提高成功率
- 数据在 Excel 文件中，不在 stdout 的 markdown 表格
- 同时查询 DDX + 主力资金 + PE 需要两次 API 调用
- 每次查询前清除旧 mx output 文件避免读取旧数据
- mx_data.py 需要在工作目录 ~/skills/mx-data/ 下执行

## TDX MCP 编码修复

wenda-mcp-server 返回的 JSON 中文字段名被 Latin-1 误解释。
修复: `tdx_mcp.py` 中的 `fix_encoding()` 递归函数:
```python
obj.encode('latin-1').decode('utf-8')
```

## 不可用的数据源

- push2.eastmoney.com: 服务器主动断开连接 (RemoteDisconnected)
- push2his.eastmoney.com: 间歇性可用，不稳定
- eltdx capital: main_net 始终返回 0
- 东财 emweb 行业页面: 可访问但无 DDX 数据
