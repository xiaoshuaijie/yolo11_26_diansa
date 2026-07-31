# Progress Log

## Session: 2026-07-31

### Phase 1: 代码与设备发现
- **Status:** complete
- **Started:** 2026-07-31
- Actions taken:
  - 记录用户目标及赛道/车架的可见特征。
  - 初始化桌面软件操作环境；下一步将启动 MaixVision 并查看真实相机画面。
  - 并行检查项目中的 OpenCV 与 MaixVision 相关代码位置。
  - 已在 MaixVision 连续查看两帧设备实时画面，确认无钢珠时仍由 OpenCV 模板跟踪（`T`）输出固定车架假阳性。
- Files created/modified:
  - `task_plan.md`（创建）
  - `findings.md`（创建）
  - `progress.md`（创建）

### Phase 2: 实机参数采样与方案确定
- **Status:** complete
- Actions taken:
  - 阅读本地 `maixpy-skill` 的设备工作流和 MaixPy 代码规则；本机尚未配置 helper 的设备凭据，但 MaixVision 已持有实时设备连接。
  - 复核 OpenCV 实现：当前 `T` 分支未调用已存在的纹理校验，且模板跟踪会把 `last_seen_ms` 持续刷新，因此静态车架假阳性不会自然超时。
  - 核对 IDE 项目副本与 `E:\jie` 文件副本为独立文件，修改前哈希一致。
- Files created/modified:
  - `task_plan.md`（更新）
  - `findings.md`（更新）
  - `progress.md`（更新）

### Phase 3: 代码实施
- **Status:** in_progress
- Actions taken:
  - 将 YOLO 获取门限提高至 `0.24/0.24/0.40`，将 OpenCV 模板门限提高至 `0.70/0.78`。
  - 对局部和全画面模板结果统一启用纹理校验，并限制模板仅可在最近 320ms 的 Y/E 检测确认后补帧。
  - 将 `hybrid_tracker.py` 同步到 MaixVision 当前运行的项目副本。
  - 对原运行实例执行停止，然后验证了“运行当前文件”入口：设备端明确报 `ModuleNotFoundError: ball_position`，说明该入口不会同步项目模块；随后已回到完整项目运行路径。
  - 按用户红色标记把标定轴从 `(5, 80)` 到 `(475, 80)` 收至 `(21, 80)` 到 `(460, 80)`，物理范围保持 `-12.5/+12.5cm`。
- Files created/modified:
  - `hybrid_tracker.py`（`E:\jie` 与 MaixVision 项目副本均已更新）

## Test Results
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| 模板状态机 | 无 OpenCV 的本机桩测试 | T 不得刷新最近检测时间，320ms 后必须拒绝模板 | 通过 | PASS |
| 标定点换算 | 用户标定截图 | 两个白色导轨端点分别映射 -12.5/+12.5cm | 已写入 `(21,80)/(460,80)`，待 MaixVision 实机重启确认 | PENDING |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-07-31 | 并行探索任务被服务限流 | 1 | 由主任务完成相同的只读检查，未重复请求 |
| 2026-07-31 | `py -3` 环境缺少 `numpy` | 1 | 将定位并使用已安装 OpenCV/Numpy 的解释器执行行为测试 |
| 2026-07-31 | PowerShell 解释器探测命令参数组合错误 | 1 | 直接使用已列出的 Python 3.12 路径 |
| 2026-07-31 | Python 3.12 缺少 `cv2` | 2 | 不改变本机环境，改用桩测试时序门控并转入设备端实测 |
| 2026-07-31 | MaixVision 单文件运行缺少 `ball_position` | 1 | 使用项目运行入口部署所有文件 |
| 2026-07-31 | 调试记录补丁上下文已变化 | 1 | 重新读取文件后精确更新 |

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase 3：代码实施，待实机复核标定轴 |
| Where am I going? | 实机复核端点、验证识别，然后交付 |
| What's the goal? | 基于真实画面排除黑色车架干扰、校准 OpenCV 与位置映射 |
| What have I learned? | 车架假阳性主要来自模板回退；白色导轨端点不是图像边缘 |
| What have I done? | 已调模板门控，并把标定像素端点移至用户标记的导轨两端 |
