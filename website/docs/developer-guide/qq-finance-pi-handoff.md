# Hermes QQ → Finance：文本记账人工接入交接

Refs #5。仅 Pi 兼容分支，禁止合入或覆盖新版 Hermes main。本 PR 不部署、不 SSH、不读取真实配置/账本/聊天。目标是原 QQBot → 原 Hermes adapter → Finance → 原 QQ adapter 回复；Finance 没有 QQ 登录或平台凭据。

## 版本与结论边界

- Finance 固定 main：`8a47ba5bd7ce0342c9a2f241f8452710cbdf2fa4`，tree `aba87c623d6c344bc3cae6b2558706acec81e990`。
- Hermes 业务基线：`4ca5aa4f9a5f347446a537a7b00df81c3e0ef559`，分支 `finance/pi-baseline-f97608f`；与受审 PR #4 `16e9ff01f4deaa42dbbddd73f979d3f82d681301` 的 tree 相同。
- 本 PR 只新增探针、测试和本文。新交接 PR 的 SHA 不等于要求生产升级业务代码。探针的 REVIEWED_POINTER 特指上述业务基线；不同指针先停下做 tree/blob 对比，不强行 reset。
- Git HEAD、静态 factory 文件、wheel 名称 `0.1.0`、health ok 都不能证明进程加载了受审代码。运行字节、实际 profile/配置、companion 导入和真实 QQ 验收仍需独立证据。

## 1. 只读：无需猜目录的本机检查

用户在 Pi **本机终端**粘贴下面完整块。没有 SSH、网络、临时文件或安装；`-I -B` 隔离 Python 启动并禁止字节码写入。它与 `scripts/pi_qq_finance_probe.py` 相同，压缩内嵌仅为避免旧 checkout 没有新脚本；先验证 SHA-256 再运行。不要添加反斜线续行，也不要把 Markdown 标记复制进去。

探针只询问两个固定用户服务的 ActiveState/SubState/MainPID，读取对应 /proc exe/cwd/starttime 元数据和 cwd 的 Git HEAD/refs、factory 静态文件。不读取 argv、环境、config、密钥、数据库、消息或日志；不执行 Git 或运行中的 Python，也不 import 业务包。标准输出只有三个固定字段。`PYTHON_3_12_NAME_ONLY` 只是 exe 名字，不是 patch 版本验收。权限拒绝、进程变化、worktree/gitfile、特殊文件或未知布局均不得猜测 PASS。

```sh
python3 -I -B - <<'PY'
import base64, hashlib, sys, zlib
try:
    code = zlib.decompress(base64.b64decode("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", validate=True))
    if hashlib.sha256(code).hexdigest() != "d51cadc35eeb176acb25174845e91621a994d4c79749ed31b499f3f00e23ab1d":
        raise ValueError()
    scope = {"__name__": "qq_finance_checked"}
    exec(compile(code, "pi_qq_finance_probe.py", "exec"), scope)
    rc = scope["main"]([])
except (Exception, KeyboardInterrupt):
    print("UNVERIFIED tool PROBE_UNAVAILABLE")
    rc = 2
sys.exit(rc)
PY
```

退出码 3 表示存在 BLOCKED，2 表示存在 UNVERIFIED，0 才是全部已证明；本探针故意保留运行版本/配置/真实 QQ 的 UNVERIFIED，因此常规成功执行仍返回 2。不要把 2 当成脚本崩溃，也不要为了返回 0 关闭检查。

| 状态 | 下一步 |
| --- | --- |
| NOT_RUNNING / METADATA_UNAVAILABLE_OR_CHANGED | 停止切换；用户本机核实目标用户服务、权限与 PID，不自动启动/重启 |
| POINTER_MISMATCH / POINTER_UNAVAILABLE / SOURCE_UNAVAILABLE | 停止；在新目录准备固定受审源码，原 checkout 保留，不 pull/reset/clean |
| WORKTREE_NOT_ATTESTED | 必须使用独立受审 release/blob 校验；探针绝不使用 git status |
| RUNNING_IMPORT_NOT_ATTESTED / RUNNING_BYTES_NOT_ATTESTED | 在新候选 venv 做下述导入与源码/包摘要核验；不拿它冒充旧进程证明 |
| LOCAL_PRIVATE_REVIEW_REQUIRED / MANUAL_ACCEPTANCE_REQUIRED | 用户私下核对配置并做真实 QQ 验收；只报告常量结果 |

如果本机缺 systemd 用户总线，探针只报 UNVERIFIED，不安装/启动总线。无权限时不用 sudo，不向助手发送原始状态、私有路径或日志。

## 2. 写入（仅新候选目录）：固定源码、wheel 与独立 QA

本 PR 审核、用户手动合并后，先在开发电脑准备两个固定 release。Finance 可复用 #79 的 `finance_prepare_source.py` 和 `FINANCE_SOURCE_PREPARATION.md`：可信 bundle + 独立 SHA256 + commit/tree，默认 dry-run，显式 apply 只创建新目录；**不覆盖旧源码**。该工具只准备 Finance，不能把它的 SHA/tree 用给 Hermes。Hermes 使用 Pi 兼容基线的受审完整 archive，先逐文件 Git blob 校验；本 PR 的三个交接文件另按其最终 SHA 校验。禁止从新版 Hermes main 导出代替兼容 release。

开发电脑构建 Finance wheel：

```sh
python -m build --wheel ./finance/backend --outdir ./reviewed-wheels
python -m pip hash ./reviewed-wheels/hermes_finance-0.1.0-py3-none-any.whl
```

构建时间戳可使 wheel SHA 变化，不能照搬旧 wheel 摘要；记录**实际本次**摘要及对应源码 tree。验证 wheel 内容/schema SQL 与固定源码，并在全新 QA venv 安装该 wheel 后 `pip check`。源码指针不等于 wheel provenance。所有传输到 Pi、新目录和依赖安装另经用户批准；本任务没有传输。不要将运行数据库、密钥或日志加入 release。

用户选择一个本人所有、0700、本地文件系统的**全新**候选目录，路径只在本机维护记录中保存。旧 Gateway venv 不安装包；在新候选创建独立 Python 3.12 venv，安装固定 wheel 和兼容 Hermes 所需已审查依赖。不得绕过依赖失败，不能在生产环境运行 pip install -U。Finance 仍使用自己的独立 venv，不把 QQ SDK 装进 Finance。

以下变量由用户在本机选择准备好的候选文件，不是让用户猜旧服务目录；不要向助手发送变量值。它们不写入现有服务：

```sh
read -r -e -p '新候选 Hermes 源码的绝对路径: ' qq_source
read -r -e -p '新候选 venv/bin/python 的绝对路径: ' qq_python
read -r -e -p '固定 Finance 源码的绝对路径: ' finance_source
case "$qq_source:$qq_python:$finance_source" in /*:/*:/*) ;; *) echo 'BLOCKED candidate ABSOLUTE_PATHS_REQUIRED'; exit 3;; esac
"$qq_python" -m pip check
```

只有候选目录允许执行下面的**加载验证**。这会导入可信候选代码，故不属于只读生产探针。全新 HOME/HERMES_HOME、假 adapter/allowlist、无真实凭据、不监听、不请求网络：

```sh
qa_home=$(mktemp -d)
env -i PATH=/usr/bin:/bin HOME="$qa_home" HERMES_HOME="$qa_home/profile" "$qq_python" -I -B - "$qq_source" <<'PY'
import asyncio, sys
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from gateway.platforms.qqbot.intake_guard import IntakeGuard
adapter = SimpleNamespace(_dm_policy="allowlist", _is_dm_allowed=lambda user: False)
guard = IntakeGuard(adapter, {
    "factory": "gateway.platforms.qqbot.finance_intent_router:create_guard",
    "timeout_seconds": 5,
    "settings": {"receipt_enabled": False, "finance": {
        "base_url": "https://example.invalid", "natural_intents_enabled": True,
        "profiles": {"fake": {"key_id": "fake", "secret_file": "finance/fake.key"}}
    }}
})
assert guard.consumer is not None
assert asyncio.run(guard.allow("C2C_MESSAGE_CREATE", {"content": "你好"})) is True
assert asyncio.run(guard.allow("C2C_MESSAGE_CREATE", {"content": "4000", "author": {"user_openid": "fake"}})) is False
print("PASS candidate FACTORY_LOADED_CHAT_ALLOWED_SECRETS_WITHHELD")
PY
```

**停止条件：** 缺 companion、依赖冲突、factory.consumer 为 None 或普通聊天不放行。配置了 guard 但 factory 加载失败时，现有 IntakeGuard 会关闭**全部**消息，不能靠“先切换再补包”上线，也不能改成 fail-open。没有启用 guard 的原聊天不受该 optional 模块影响。成功加载后 Finance 断网才是“普通聊天继续、财务关闭”的路径。

## 3. 隔离开发验收（写虚构数据库，不连接 QQ）

在候选源码下，原入口必须执行，不能用 bare pytest 替代 Hermes runner。runner 会进一步隔离环境并逐文件启动子进程：

```sh
(cd "$qq_source" && HOME="$qa_home" HERMES_HOME="$qa_home/profile" bash scripts/run_tests.sh -j 1 tests/gateway/test_qq_intake_guard.py tests/gateway/test_qqbot.py tests/gateway/test_qq_finance_intent_router.py tests/gateway/test_pi_qq_finance_probe.py)
(cd "$finance_source" && "$qq_python" -m pytest -q backend/tests)
(cd "$finance_source" && "$qq_python" backend/scripts/demo_offline.py)
(cd "$finance_source" && "$qq_python" backend/scripts/demo_hermes_offline.py)
(cd "$finance_source" && "$qq_python" backend/scripts/demo_full_finance_offline.py)
```

上述命令仅用于准备好的开发 venv/源码，不能替换为正在服务的 venv 或真实 HERMES_HOME。Finance 全量检查所需 age 等开发依赖须预先审批安装在候选环境；缺失应记录跳过，不自动安装生产依赖。

| 必验行为 | 已有真实源码或本 PR 覆盖 |
| --- | --- |
| 普通聊天/会议确认/收入讨论 | 原 QQ adapter early gate 放行且无 Finance RPC；源码 guard 位于 body/dedup/busy/runner/STT/日志前 |
| 无默认“记账 午饭 25 元” | 追问；`选择 来源 ID`、`选择 目标 ID` 更新同一持久任务，不选第一账户 |
| Web 可信默认账户 | Web 登录 + Origin/CSRF 后设置 approved_default_source 与午饭 category；完整 25.00 元、来源→目标、描述及任务摘要 |
| 确认/重复事件/取消 | 同事件与新事件重复确认最多一笔；取消不入账；仍由 Finance 验证 |
| 重启/撤权/过期 | 原 Finance reopen 测试与本 PR router 重建；授权失效拒绝；不恢复过期任务 |
| 入账后丢响应/断网 | UNKNOWN 不自动新建账务任务，重复确认不会重复入账；普通聊天仍放行 |
| A→B→A/秘密混合文本 | 既有跨仓 profile/key 测试和输入护栏，四位答案/任务 token 不到 Agent、历史/通用日志 |

账户选择只补充当前任务，**不会偷偷保存为未来默认**；长期默认只能由用户 Web 设置。当前“自然语言”是确定性受限语法，不承诺任意闲聊自动记账。不确定表达转 Web/澄清，不调用普通模型兜底。

## 4. 私有配置人工核对（本轮不执行）

用户本机从现有服务管理记录确认实际 ExecStart/venv、Gateway cwd、canonical HERMES_HOME/config 路径和旧恢复版本；不打印完整 unit、命令行或环境。探针通过 MainPID/cwd 自动检查指针，不假设入口必须是 `python -m gateway.run`。若旧版本/恢复配置无法证实，停止，不能继续切换。

核对 Finance 当前模式：Web-only 不提供受控 QQ v2 接口；必须按 Finance `FINANCE_CONNECTED_RUNTIME.md` 先审核 connected runtime、allow_writes=true、正确允许账户和既有 POWER4。`serve --check` **不是只读探针**：lifespan 可能开启/迁移数据库并更新状态；只能先用于虚构实例，真实库需停机快照、Schema 兼容审核后单独批准。

真实 Schema 未确认时，不运行新 AuthStore 或 Ledger 去探测旧库。维护窗口静止全部写入者，按现有维护工具成对 backup→verify→新目录 restore/迁移；源不变。既有链为 Ledger v1→v2→v3→v4、Identity v5→v6→v7→v8→v9，按实际源版本选择 `maintenance --help` 中受审 dry-run 命令。未知链即停。本轮无需 Google Drive。

HMAC 两端必须同 key_id/材料、canonical bot/profile/user/session 与 epoch/key generation，一端不匹配即拒绝；密钥只在本机生成/核对，不通过聊天、argv 或本报告传递。Hermes secret_file 仅相对该 canonical runtime_home，不能复制整个 Finance 秘密目录，POWER4 参数留在 Finance。禁止借 launch/default profile key。既有 DM policy 必须 allowlist，Finance 同时有独立 allowlist；pairing/open 不构成金融授权，不为集成扩大原权限。

TLS base_url 必须是已批准的现有私有 origin，CA 绝对路径且链/SAN匹配；不猜 IP/端口、不 verify=False、不 trust_env、不 redirect、不改证书或网络。health 只能证明存活，不能证明 HMAC/授权/数据库模式。

只在原 QQ `PlatformConfig.extra` 内人工合并以下**最小片段**，保持 app_id、client_secret、登录/连接、原 sender 和其他设置。原 YAML 支持 `platforms.qqbot.extra`；若同名值同时在顶层与 extra，显式 extra 优先，用户须检查歧义。不用下面片段替换整份配置：

```yaml
intake_guard:
  factory: gateway.platforms.qqbot.finance_intent_router:create_guard
  timeout_seconds: 5
  settings:
    receipt_enabled: false
    finance:
      base_url: https://YOUR_APPROVED_PRIVATE_ORIGIN
      ca_file: /YOUR_APPROVED_CA_ABSOLUTE_PATH
      request_timeout_seconds: 2
      natural_intents_enabled: true
      profiles:
        YOUR_CANONICAL_PROFILE:
          key_id: YOUR_APPROVED_KEY_ID
          secret_file: finance/transport.key
```

所有占位值仅由用户本机填写，不提交 GitHub；若系统已信任证书链，省略 ca_file。Finance receipt_ocr_enabled 与所有新 AI/receipt/云功能继续关闭。未来图片启用前，外层 intake_guard **必须 timeout_seconds=30**，不能沿用本文纯文本 5 秒；隔离视觉仍未验证，不能借普通模型绕过。

## 5. 写入/切换门槛与真人验收

只有用户确认旧版本/配置私有备份、完整成对数据库恢复演练、新目录 Schema/依赖/CA/HMAC/profile/allowlist 和虚构闭环均通过后，才另行批准最小切换。旧 venv/源码不原地覆盖；使用新候选引用与原受审启动方式。没有可恢复启动引用就停止，不自造新的 unit。本 PR 不授权 systemd 修改。

批准窗口中由用户仅切换已审核的 Finance/原 Gateway 目标；若 Finance 已 connected 且无需改变，不重启它。只在 Gateway 引用/配置核对后执行：

```sh
systemctl --user restart hermes-gateway.service
systemctl --user is-active --quiet hermes-gateway.service && echo 'PASS gateway ACTIVE' || echo 'BLOCKED gateway NOT_ACTIVE'
```

不重启 Dashboard、Trace 或其他服务，不动 Compose/Samba/OpenClaw。

用户亲自按顺序验收，不向助手发送财务内容、验证码或任务令牌：

1. 原 QQ 发“你好”“帮我确认一下明天的会议时间”“如何提高收入”，原 Hermes 正常回复。
2. 无默认账户时发“记账 午饭 25 元”：应追问；根据 Web 允许账户 ID 回“选择 来源 ID”“选择 目标 ID”；核对类型/25.00/来源→目标/分类/描述/任务，未确认不入账。
3. “取消记账”后“确认”不得入账；再建新候选并确认一次，Web 核对恰好一笔；再“确认”不能新增。
4. Web 通过受保护设置显式保存默认支付账户及“午饭”类别；新请求应直接给完整摘要，用户检查后才确认。选错账户可取消，不盲目确认。
5. 过期或权限拒绝应保持关闭；真实断网/超时注入只在另经批准的测试窗口进行，不为了验收停生产 Finance。平台重复事件自动化已在虚构环境覆盖，不能伪造真实QQ回调攻击生产。
6. UNKNOWN/超时先在 Web 核对原任务和账务；不要反复发新的“记账”制造不同任务。

任何一步失败即停止启用：尤其普通聊天沉默、摘要不完整/账户方向错误、未确认入账、重复入账、秘密进入模型、跨profile串用、未知Schema或TLS失败。生产 QQ 尚未执行这些步骤，因此状态一直 UNVERIFIED。

## 6. 回退

切换前用户在本机私有0700目录保存原源码/venv引用、仅本机配置0600副本、受审旧启动方式、成对快照与新目录恢复验证；不上传。故障时用户停止新的财务输入，先在本机撤下新 factory/恢复旧已审配置和 Gateway 引用，仅重启 Gateway 恢复普通聊天。**关闭财务护栏后不再发送认证答案或财务内容**，直到重新通过安全验收。

Finance 未改变则不操作；若本次另批准更换了 Finance，按其受审方案停止目标写入者、保留故障时点快照，恢复与 Schema 兼容的 release 或已验证的新目录恢复副本。保留账本/WAL/SHM，不删数据、不降 Schema；错误交易以正常追加冲正处理。密钥/会话轮换依现有恢复规范。原恢复点或完整性不明即停止，不能扩大权限“修复”。源码撤回使用独立 revert PR，不以 Git 撤销真实交易。

## 开发测试证据

见本 PR 正文的最终 HEAD、固定 Finance SHA、真实命令和计数。Windows 的 linux_only 跳过单独列出；未运行的 CI/ARM64/真实 Pi 不能沿用旧报告冒充。模拟 QQ/ASGI 不是生产 QQ。
