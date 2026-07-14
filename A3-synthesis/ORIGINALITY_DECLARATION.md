# 原创性与开发方式声明

## 1. 参赛信息

- 队伍：思路全队
- 工具名称与版本：LightSynth v1.0
- 源码版本/commit：v1.0

## 2. 开发类型

- [x] 开源工具增强型 `open_source_based`

## 3. 自主完成的模块

- **config.json**：多策略 ABC 优化配置 + 电路定制方案（`config.json`）
- **synth_tool.py**：Yosys/ABC 综合流程封装，含多策略选择、故障回退、参数校验（`src/synth_tool.py`）
- **Makefile**：build/synth/clean 目标，符合竞赛评测接口规范（`Makefile`）

## 4. 开源工具调用边界

- **Yosys 0.54**（ISC许可证）：RTL前端解析、基础综合（`synth`）、触发器映射（`dfflibmap`）。通过 `subprocess` 调用，未修改源码
- **Berkeley ABC**（BSD-like，内嵌于Yosys）：技术无关优化与工艺映射。通过 `abc -script` 脚本调用
- **Nangate45 Liberty**（academic）：工艺库文件，仅作为输入读取

## 5. 大模型辅助开发

- 使用的大模型：Claude
- 主要用途：代码框架生成、调试建议、策略设计头脑风暴
- 人工复核方式：所有模型输出经人工审查修改后采用，核心算法逻辑由人工设计和验证
- 大模型生成代码路径：`src/synth_tool.py`（框架级辅助）

## 6. 原创算法与效果证据

- 7点差异化ABC优化策略（`$default`）：覆盖 `compress2rs+dch` 面积路径、零代价重写（`-z`）面积优先、两轮 rewrite+refactor 深度优化、`resyn2` 综合、独立 `if -K 6` 时序路径、`resyn2+if` 混合时序路径
- 电路定制：LSV01-LSV04 各配置5-7点独立策略，基于公开参考Pareto数据做差异化（如 LSV01 K=4 vs K=6 扇入适配）
- 故障回退机制：主策略失败时自动回退到基础策略

### 消融对比

| 消融项 | 基线配置 | 优化配置 | 预期效果 |
|--------|----------|----------|----------|
| compress2rs 路径 | 仅 rewrite/refactor | + `compress2rs; dch` 面积点 | 补 compress2rs 搜索空间 |
| 独立 if-K6 路径 | K6 仅与 resyn2 混合 | + `if -K 6 -g -C 8; dch` 时序点 | 覆盖大电路时序最优区 |
| SDC 约束驱动 | 无 read_sdc | `read_sdc` 参与 synth | 时序感知优化 |
| 线程限制 | `OPENMD` 无效 | `OPENMP`=1 正确限制 | 符合评测规范 |

## 7. 声明

本队确认提交源码可在指定离线镜像中从头构建，第三方代码均已在 `THIRD_PARTY.md` 披露，且未使用其他参赛队的未公开代码或针对隐藏题预生成的网表。
