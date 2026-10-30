---
name: hermes-finance
description: 通过 Finance 工具完成可核验的财务记账与查询。
version: 0.2.0
author: yanwuchen (@yanwuchen), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [finance, ledger, accounting, 记账, 财务]
    category: productivity
---

# Hermes Finance Skill

Hermes 负责理解用户的自然语言，Finance 负责确定性账户、金额、权限和账本校验。
QQ、Telegram 或其他平台的连接与回复始终由 Hermes 管理；Finance 不创建聊天机器人。

## When to Use

用户明确要求记账、收入、支出、转账、还款、退款、余额或交易查询时使用。
普通聊天、密码、验证码和服务管理不使用本 skill。

## Prerequisites

Finance Gateway 已由管理员配置为受控私有服务，且当前会话属于允许的私聊身份。
不要读取或询问密码、POWER4、HMAC、QQ 凭据、SQLite 文件或运行日志。

## How to Run

纯文本财务请求由已配置的 Hermes QQ intake guard 在模型前处理。
复杂自然语言由 Hermes 解析为受限结构化 Finance 请求；只调用已注册的 Finance 能力，
不要通过 `terminal`、`read_file` 或任意 HTTP 请求自行访问数据库或服务。

## Quick Reference

- 记账：识别业务类型、金额、描述、来源和目标；缺字段就追问。
- 账户：优先调用 Finance 的账户候选/别名解析；同名或多账户必须列出候选。
- 退款：必须引用 Finance 返回的原交易 ID；不能猜 ID。
- 查询：只向用户返回 Finance 已授权的结果。
- 取消：取消当前候选，不创建替代请求。

## Procedure

1. 从用户话语提取候选业务，不把模型推测当成事实。
2. 调用 Finance 获取账户、分类和历史候选；不自动选择第一个账户。
3. 向用户显示完整摘要：类型、金额、来源账户、目标账户、分类、描述；
   退款还要显示原交易 ID。
4. 缺少账户、金额、分类或原交易引用时先追问；用户取消则停止。
5. 只有 Finance 返回已完成且带幂等结果时，才告诉用户“已记账”。
   候选、超时、未知状态、网络故障都只能报告未完成。
6. 重复消息沿用同一请求/任务标识；不要新建替代写入。
7. 普通聊天保持原 Hermes 路径；任何 Finance 组件异常都 fail-closed，
   不把敏感输入交给通用模型或日志。

## Pitfalls

- 不把“确认”“收入”等普通聊天词语单独当作财务命令。
- 不发送密码、验证码、任务 token、HMAC 或 QQ 身份到模型、聊天历史或 `terminal`。
- 不把 Finance 网页链接当作唯一确认流程；日常记账在受控 QQ 路由中完成。
- 不声称模拟测试或候选创建已经入账。
- 不安装 QQ SDK，不启动第二个 QQBot，不修改服务配置。

## Verification

离线验证应使用虚构 Finance 服务和 fake QQ adapter，覆盖普通聊天放行、
账户歧义追问、取消、重复确认、服务故障和敏感输入隔离。
真实 QQ/树莓派上线必须由用户按已审核的部署步骤手动验收。
