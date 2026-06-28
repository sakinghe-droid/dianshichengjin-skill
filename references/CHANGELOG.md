点石成金技能本次更新摘要:

## 新增文件
- `references/data-enrichment-chain.md` — 六维博弈引擎多源降级补全链完整文档

## SKILL.md 变更
1. 执行铁律新增第7条: 行情数据禁止默认值，必须走多源补全链
2. 数据补全优先级新增 ddx_calculator 兜底环节 + 引用 references
3. 「开源实现说明」更新为实际数据补全链描述

## 关键学习
- mx-data DDX查询需要带"主力资金DDE大单净量"关键词才返回DDX表
- mx-data 返回Excel格式，需通过 openpyxl 解析 Sheet
- TDX MCP JSON中文键名需 latin-1→utf-8 编码修复
- DDX fallback链: mx-data → TDX → L2 → ddx_calculator → defaults