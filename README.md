# bundle-draft2-lookup-q8kv

Bonsai 2 27B · 262k-bundle（PrismML fork, build 10798）在 8GB 显存（RTX 4060 Laptop）上的
最优推理档位调优记录：**MTP draft2 + lookup32 + q8_0 KV + 262K tiered KV**。

2026-10-19 用「3D 夜间滑雪游戏」长代码提示词（~8.5K token 输出）做完整调优过程，含
draft 1/2/3 草稿档位对比、每档草稿接受率（draft acceptance）实测。

## 环境与档位配方

- 引擎：262k-bundle `bundle/bin/llama-server.exe`（build 10798）
- 模型：`Ternary-Bonsai-2-27B-PTQ1_0-mtp-procreations.gguf`（6.1GB，Q8 MTP head）
- 启动：`start-server-local.ps1`，关键 env：`BONSAI_SPEC=2`（MTP draft 2，过显存线 tail 1）、
  `BONSAI_CTK=q8_0`（K/V q8_0）、`BONSAI_THINK=0`（关思考）
- 8GB preset：262,144 窗口、tiered KV（0..35840 cells 显存 / 其余 pinned RAM）、
  共享 CUDA 池、packed KQ mask、lookup drafting 32、draft window 16384

## draft 档位对比（同提示词、temp 0.7、seed 42、关思考、每档两轮）

| draft | tok/s（两轮） | draft acceptance | mean accepted len | 备注 |
|---|---|---|---|---|
| 1 | **47.45 / 47.81** | **81.58%**（3888/4766） | 1.915 | 纯生成最快最稳 |
| 2 | 43.32 / 46.66 | 77.65%（5226/6730） | 2.78 | 现生产档；run 间方差略大 |
| 3 | ~5.3（3.9K token 处实测） | — | — | **崩**：8GB 上宽验证批次灾难性劣化，已终止 |

（固定种子下两轮输出逐字节一致，acceptance 数字也完全一致——贪心可复现。）

### 结论

1. **单 token 接受率 draft1 最高（81.6%）**，且吞吐稳定领先 ~2-4%（47.5-47.8 vs 43.3-46.7）。
2. **draft2 仍是合理生产档**：差距在测量噪声边缘，且 lookup drafting（上下文复写类任务）
   在 draft2+ 档收益更大（官方 lookup AB：file rewrite 58→126 tok/s @ depth 0）。
3. **draft3 起在 8GB 上不可用**（5.3 tok/s，宽 verify 批次 + tail 1 回滚环开销）。
4. 追求纯生成极限可在工作台把 `start-8898-gear.ps1` 的 `BONSAI_SPEC` 改 1（约 +2%）。

## 双引擎 262K 对决背景（同提示词）

| 引擎 | temp | 速度 | 结果 |
|---|---|---|---|
| bundle draft2+lookup+q8KV（本仓库档位） | 0.7 | 48.7 | ✅ 完整输出，运行零报错 |
| NInfer full_v3（MTP×4 adaptive + rk4v4-e8） | 0 | 46.5 | ✅ 完整但风声函数 bug |
| bundle（同档位） | 0 | 198.5 虚高 | ❌ 16K token 全烧 CSS 复读循环 |
| NInfer（思考未关） | 0 | 68.2 虚高 | ❌ 16K token 全烧思考，正文空 |

**稳定性坑**：bundle 必须 temp≥0.7（temp 0 贪心复读循环）；NInfer 必须 per-request
`chat_template_kwargs: {"enable_thinking": false}`。

## 协议支持（实测 build 10798）

- OpenAI：`/v1/chat/completions` ✅、`/v1/completions` ✅、`/v1/responses` ✅
- Anthropic：`/v1/messages` ✅（原生 Claude 协议，含 thinking 块；Bearer 与 x-api-key 均可）
- `/v1/embeddings`：501（无 embedding 模型，正常）

## 文件

```
code/tune_draft.py           # 自动化调优：重启引擎→预热→固定种子测速→抓日志接受率→落盘 jsonl
code/start-draft-test.ps1    # 测试包装（BONSAI_SPEC 可变；内含代理变量去重防崩）
code/start-8898-gear.ps1     # 生产档位包装（工作台 bonsai-8898 档同源）
code/ski_262k_test.py        # 单次长输出测试脚本
code/ski_prompt.txt          # 测试提示词（3D 夜间滑雪游戏）
results/draft-tune-results.jsonl
logs-sample/                 # draft1 完整轮 / draft3 崩溃轮服务端日志样本
outputs/ski-game-bundle.html # 本档位生成的滑雪游戏成品（可直接运行）
```

## 启动坑（重要）

PowerShell 5.1 的 `Get-ChildItem Env:` 在进程环境块存在大小写重复变量（如同时有
`HTTP_PROXY` 与 `http_proxy`）时抛「已添加了具有相同键的项」，bundle launcher 首行即崩。
包装脚本一律先 `Remove-Item Env:http_proxy; Remove-Item Env:https_proxy` 再启动。
