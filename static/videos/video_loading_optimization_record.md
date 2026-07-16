# ForeTac 任务视频加载与同步播放优化记录

## 1. 背景与目标

ForeTac 项目网页在四个任务中分别并排展示真实执行视频（`*_real.mp4`）和触觉可视化视频（`*_viz.mp4`）：

- Board Wiping
- Vase Wiping
- Card Swiping
- Chip Grasping

目标是让每组左右视频加载完成后同步播放，并在媒体加载或缓冲期间显示转圈状态。

## 2. 遇到的问题

网页增加同步播放和加载转圈后，实际访问时仍出现以下现象：

1. 刷新页面后，视频区域先显示预览帧，用户不容易判断视频是否正在加载。
2. 左侧 `*_real.mp4` 通常可以进入可播放状态，右侧 `*_viz.mp4` 经常长时间转圈或无法继续播放。
3. 任一视频发生缓冲时，同组两个视频都会暂停，因此右侧卡顿会表现为整组停止播放。
4. 问题在四组任务上均可能发生，且弱网环境下更明显。

## 3. 排查思路与过程

### 3.1 确认文件是否为有效视频

使用 `ffprobe` 检查八个任务视频，确认它们均为浏览器支持的 MP4 视频：

- 视频编码：H.264 High Profile
- 像素格式：`yuv420p`
- 无音轨
- MP4 的 `moov` atom 位于 `mdat` 之前，支持 Fast Start
- 四组左右视频的源时长分别一致

因此，问题不是文件伪装成视频、编码格式不受支持或 MP4 索引位于文件末尾。

### 3.2 检查服务端响应

检查 GitHub Pages 的媒体响应，确认：

- `Content-Type` 为 `video/mp4`
- 支持 `206 Partial Content`
- 支持 HTTP Range 请求

因此，GitHub Pages 本身能够按字节范围传输视频。

### 3.3 检查网络吞吐和视频码率

一次实际网络测试中，从 GitHub Pages 下载媒体的速度约为 `25 KB/s`，约等于 `0.2 Mbps`。原右侧可视化视频为 1920x1080，平均码率约为 `1.7-2.1 Mbps`，明显高于该次测试中的可用吞吐。

原始 `*_viz.mp4` 属性如下：

| 文件 | 分辨率 | 帧率 | 平均码率 | 时长 | 文件大小 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `board_viz.mp4` | 1920x1080 | 24 fps | 1.73 Mbps | 31.167 s | 6.5 MB |
| `vase_viz.mp4` | 1920x1080 | 24 fps | 1.96 Mbps | 20.917 s | 4.9 MB |
| `card_viz.mp4` | 1920x1080 | 24 fps | 1.86 Mbps | 10.084 s | 2.3 MB |
| `chip_viz.mp4` | 1920x1080 | 约 15.79 fps | 2.11 Mbps | 14.125 s | 3.6 MB |

### 3.4 检查关键帧间隔

使用 `ffprobe -skip_frame nokey` 检查关键帧：

- `board_viz.mp4`：仅 3 个关键帧，最大间隔约 10.417 秒
- `vase_viz.mp4`：仅 3 个关键帧，最大间隔约 10.417 秒
- `card_viz.mp4`：整段只有起始关键帧
- `chip_viz.mp4`：整段只有起始关键帧

网页同步逻辑会在恢复播放或发生漂移时把右侧视频的 `currentTime` 对齐到左侧。关键帧过少时，浏览器为了从目标时间恢复解码，需要获取并解码更早的数据；在带宽不足时，这会显著增加等待时间。

### 3.5 检查网页同步逻辑

同步逻辑的设计行为是：

1. 两个视频都达到 `canplay` 后才同时调用 `play()`。
2. 任一视频触发 `waiting` 或 `stalled` 时，同时暂停两个视频。
3. 缓冲恢复后，将右侧时间对齐到左侧，再同时播放。
4. 播放中每 500 ms 检查一次时间差；偏差大于 0.12 秒时校正右侧视频。

该逻辑的目标是保证左右内容一致，但进一步的浏览器运行时检查发现，原实现存在同步 seek 与缓冲恢复相互重入的问题。

### 3.6 浏览器运行时诊断

通过 Chrome DevTools Protocol 分别检查 `file://` 直接打开和本地 HTTP 服务两种场景，得到相同结果：

- `board_viz.mp4` 和 `vase_viz.mp4` 已完整缓冲，`buffered` 覆盖整个视频。
- `video.error` 为 `null`，不存在媒体解码或文件读取错误。
- 右侧视频却持续处于 `readyState=1`、`seeking=true`、`paused=true`，播放时间停在开头。
- 3 秒内记录到 1128 个媒体事件，循环频率约为每 20 ms 一轮。
- Chrome renderer CPU 占用一度约为 168%。

事件循环路径为：

1. `playTogether()` 无条件将右侧 `currentTime` 设置为左侧时间，即使两者时间几乎相同。
2. 设置 `currentTime` 触发右侧 `seeking`，随后 `play()` 触发 `waiting`。
3. `waiting` handler 再次执行 `pauseTogether()` 和 `playTogether()`。
4. 新一轮 `playTogether()` 再次设置 `currentTime`，形成 seek/waiting 重入死循环。

运行时仅阻止原 `waiting` handler 重入后进行对照测试，左右视频立即正常播放：3 秒后 `board_real` 和 `board_viz` 的播放时间差约为 9 ms，两个 spinner 均消失。这证明持续转圈的直接原因是同步逻辑重入，而不是视频文件或本地打开协议。

### 3.7 与 PACE 网页实现对照

问题发生后重新检查 `/home/chenzhiyuan/projects/PACE-anon/index.html` 中已经验证过的 `syncPair` 实现。PACE 的核心机制很简单：

1. 初次播放前等待一对视频都达到 `canplaythrough` 或 `readyState >= 4`。
2. 双方就绪后统一归零并在同一轮任务中调用 `play()`。
3. 任一视频结束时同时暂停、归零并重新播放。
4. 不在 `waiting/stalled` 回调中递归启动完整同步流程，也不每 500 ms 强制 seek。

ForeTac 仍需保留 PACE 没有覆盖的 viewport 懒加载、离开视口暂停和真实 spinner 状态，但同步播放的核心本应优先复用 PACE 已验证的单次启动原则。此次错误是没有在实现前逐行审查 PACE 的状态机，而是在简单同步需求上自行叠加缓冲恢复、周期校时和 seek，造成媒体事件反馈循环。

媒体量化对比进一步说明了公网加载慢的原因：

- ForeTac 四组任务的 8 个原视频合计 36.89 MiB；PACE 同步区的 4 个视频合计 26.49 MiB，ForeTac 同步区总量高 39.3%。
- ForeTac 有 4 个同步对，PACE 有 2 个同步对；ForeTac 的 `IntersectionObserver` 使用 320 px root margin，相邻视频对可能同时激活。
- ForeTac 单对合计码率约为 3.17-4.72 Mbps，PACE 单对约为 5.99-6.05 Mbps，因此不能声称 ForeTac 单对天然比 PACE 更重。
- ForeTac 原视频关键帧最大间隔约 10.417 秒，部分视频整段只有首关键帧；PACE 同步视频约为 5-8.33 秒。ForeTac 在弱网 seek 和恢复时更不利。
- ForeTac 最大的任务视频是 `board_real.mp4`（11.11 MiB、约 2.99 Mbps），不是右侧可视化视频。只压缩 4 个 `*_viz.mp4` 不能解决同步对由较慢一侧决定加载速度的问题。

结论需要分层：本地持续转圈的正确性问题只由 JavaScript 修复；公网加载性能则确实需要额外优化全部 8 个任务视频。

## 4. 根因结论

右侧 `*_viz.mp4` 经常卡住包含两个层面：

1. **持续转圈的直接原因**：同步 seek 触发 `waiting`，而 `waiting` handler 重入同步流程，形成高频事件死循环。
2. **弱网下的放大因素**：右侧视频为 1080p，码率高于实际传输能力；浏览器可能优先调度 DOM 中更早出现的左侧媒体；原右侧视频 GOP 很长，进一步延长 seek 后的恢复时间。

## 5. 解决方案

### 5.1 重新编码实验与最终媒体决策

排查初期曾将四个原始可视化视频逐字节复制为：

- `board_viz_raw.mp4`
- `vase_viz_raw.mp4`
- `card_viz_raw.mp4`
- `chip_viz_raw.mp4`

通过 SHA-256 对比确认，实验期间的 `*_viz_raw.mp4` 与重新编码前相应的 `*_viz.mp4` 完全一致。

浏览器事件诊断确认持续转圈由 JavaScript 重入直接造成后，曾使用原始视频配合修复后的 JavaScript 重新测试。该阶段先恢复原始 `*_viz.mp4` 并移除四个重复的 `*_viz_raw.mp4`，用于证明重新编码不是正确性修复的必要条件。

恢复阶段再次对比 SHA-256，确认当时的 `*_viz.mp4` 与重新编码前原始文件逐字节一致。

随后用户确认公网加载仍慢。完成上述 PACE 量化对比后，最终媒体策略调整为：优化全部 8 个任务视频，并为每个文件保留 `_raw` 原始副本。当前目录中的 8 个 `_raw.mp4` 均与修改前文件逐字节一致。

### 5.2 重新编码实验参数（已撤销）

为排除带宽、分辨率和 GOP 的影响，实验中曾将网页文件重新编码为：

- 分辨率：1280x720
- 固定帧率：15 fps
- 编码：H.264 High Profile, Level 4.0
- 像素格式：`yuv420p`
- CRF：22
- 最大码率：900 kbps
- VBV Buffer：1800 kb
- GOP：15 帧，即每 1 秒一个关键帧
- 场景切换关键帧：关闭，保持稳定 GOP
- MP4 Fast Start：启用
- 音频：不写入

核心编码参数：

```bash
ffmpeg -i INPUT_RAW.mp4 \
  -map 0:v:0 -an \
  -vf "scale=1280:720:flags=lanczos,fps=15" \
  -c:v libx264 -preset slow -crf 22 \
  -maxrate 900k -bufsize 1800k \
  -profile:v high -level 4.0 -pix_fmt yuv420p \
  -g 15 -keyint_min 15 -sc_threshold 0 \
  -movflags +faststart OUTPUT_WEB.mp4
```

该实验能够降低传输量和关键帧间隔，但不能解决由 JavaScript 事件重入造成的本地持续转圈。确认原始视频在修复后的状态机中可正常播放后，曾临时撤销这些媒体改动，以隔离正确性问题和性能问题。

### 5.3 修复同步播放重入

同步 JavaScript 采用以下修复：

1. 增加单次同步状态，两个视频同时产生 `waiting/stalled` 时只允许一个恢复流程运行。
2. 仅在左右时间差超过 0.12 秒时设置右侧 `currentTime`，避免无意义 seek。
3. 同步 seek 期间忽略 `waiting/stalled` 重入。
4. seek 完成后再次等待两个视频达到 `HAVE_FUTURE_DATA`，再同时调用 `play()`。
5. 周期漂移修正不再直接修改 `currentTime`，统一进入带防重入保护的同步流程。

### 5.4 最终全部任务视频优化

公网性能对比确认有必要优化完整同步对后，对 `board/vase/card/chip` 的 `real` 和 `viz` 共 8 个文件统一处理：

- 原始文件：保留为对应的 `*_raw.mp4`
- 网页分辨率：1280x720
- 固定帧率：24 fps
- 编码：H.264 High Profile, Level 4.0
- 像素格式：`yuv420p`
- CRF：23
- 最大码率：1200 kbps
- VBV Buffer：2400 kb
- GOP：48 帧，即每 2 秒一个关键帧
- MP4 Fast Start：启用
- 音频：不写入

最终采用 24 fps 而不是初次实验的 15 fps，以保留真实机器人动作的流畅度；同时对左右两侧使用完全相同的帧率和编码时间轴，确保每对输出时长严格一致。

## 6. 解决后的验证结果

### 6.1 重新编码实验结果（未作为最终媒体）

| 文件 | 优化后码率 | 优化后大小 | 原始大小 | 关键帧最大间隔 |
| --- | ---: | ---: | ---: | ---: |
| `board_viz.mp4` | 0.82 Mbps | 3.1 MB | 6.5 MB | 1.000 s |
| `vase_viz.mp4` | 0.81 Mbps | 2.1 MB | 4.9 MB | 1.000 s |
| `card_viz.mp4` | 0.80 Mbps | 0.98 MB | 2.3 MB | 1.000 s |
| `chip_viz.mp4` | 0.90 Mbps | 1.6 MB | 3.6 MB | 1.000 s |

实验中四个网页视频合计由约 17.3 MB 降至约 7.8 MB，减少约 55%。

重新编码造成的时长取整误差均小于一个 15 fps 帧：

| 任务 | 左侧时长 | 右侧时长 | 差值 |
| --- | ---: | ---: | ---: |
| Board Wiping | 31.167 s | 31.200 s | 0.033 s |
| Vase Wiping | 20.917 s | 20.934 s | 0.017 s |
| Card Swiping | 10.084 s | 10.067 s | 0.017 s |
| Chip Grasping | 14.125 s | 14.134 s | 0.009 s |

抽取四个实验压缩版视频在 5 秒位置的画面进行人工检查，触觉图、曲线、图例和数值仍可辨认。该实验说明：

1. 右侧视频首播和缓冲恢复所需的数据量显著下降。
2. 同步校时后最多只需回溯约 1 秒的关键帧，而不是 10 秒以上或回到视频开头。
3. 弱网下出现长时间转圈和整组停播的概率降低。
4. 原始 1080p 文件仍随仓库保留，后续可以重新调整编码参数。

这些结果只证明初次重新编码方案技术上可用，不代表它是本次持续转圈问题的必要解决方案。

### 6.2 JavaScript 修复验证

初次本地网页冒烟测试确认页面、视频容器和 spinner 可以渲染，但右侧持续转圈；该结果触发了上述 Chrome DevTools Protocol 深入诊断，不能视为播放验证通过。

同步代码修复后，先使用实验压缩版视频和全新 Chrome profile、1280x900 viewport，分别在 `file://` 和本地 HTTP 下依次滚动到四个任务，每组持续观察 3 秒。结果如下：

- 四组左右视频全部达到 `readyState=4`。
- 四组视频均为 `paused=false`、`seeking=false`、`error=null`。
- 所有 spinner 均正常消失，左右播放时间持续推进。
- `file://` 下四组最大同步误差低于 1.2 ms。
- 本地 HTTP 下四组最大同步误差低于 0.9 ms。
- 修复后每个视频在 3 秒内通常只产生 11-12 个正常 `timeupdate`，未再出现事件风暴。
- Headless Chrome renderer 平均 CPU 约为 26%，较修复前约 168% 明显下降。

该测试证明 JavaScript 重入已修复。

### 6.3 恢复原视频后的隔离验证

为确认 JavaScript 修复不依赖重新编码，曾恢复四个原始 1080p `*_viz.mp4`，并在 `file://` 与本地 HTTP 下重新测试：

- 四组左右视频全部 `readyState=4`、`paused=false`、`seeking=false`、`error=null`。
- 所有 spinner 均消失，3 秒内每个视频只有 10-11 个正常 `timeupdate`。
- 全程没有 `waiting/stalled/seeking/seeked/error` 事件风暴。
- `file://` 最大同步误差为 1.359 ms；本地 HTTP 最大同步误差为 2.215 ms。

该结果确认：原视频能够正确播放，持续转圈确由 JavaScript 重入造成。

### 6.4 最终 8 个网页视频验证

| 文件 | 原始大小 | 网页大小 | 网页码率 | 关键帧最大间隔 |
| --- | ---: | ---: | ---: | ---: |
| `board_real.mp4` | 11.11 MiB | 4.43 MiB | 1.19 Mbps | 2.000 s |
| `board_viz.mp4` | 6.44 MiB | 2.18 MiB | 0.59 Mbps | 2.000 s |
| `vase_real.mp4` | 4.50 MiB | 2.66 MiB | 1.06 Mbps | 2.000 s |
| `vase_viz.mp4` | 4.89 MiB | 1.58 MiB | 0.63 Mbps | 2.000 s |
| `card_real.mp4` | 1.58 MiB | 0.90 MiB | 0.74 Mbps | 2.000 s |
| `card_viz.mp4` | 2.24 MiB | 0.73 MiB | 0.60 Mbps | 2.000 s |
| `chip_real.mp4` | 2.58 MiB | 1.43 MiB | 0.84 Mbps | 2.000 s |
| `chip_viz.mp4` | 3.55 MiB | 1.12 MiB | 0.66 Mbps | 2.000 s |

8 个网页任务视频总量从 38,684,447 字节降至 15,752,291 字节，减少 59.3%。四组左右视频的输出时长分别严格一致：31.167、20.917、10.084、14.125 秒。

通过 SHA-256 确认 8 个 `_raw.mp4` 均与修改前原文件一致。抽取每个网页视频 5 秒处画面进行人工检查，真实机器人画面、触觉点阵、曲线、图例和数值均保持清晰。

使用全新 Chrome profile 对最终 8 个网页视频进行逐组播放测试：

- `file://` 下四组最大同步误差为 1.818 ms。
- 本地 HTTP 下四组最大同步误差为 1.954 ms。
- 所有视频均为 `readyState=4`、`paused=false`、`seeking=false`、`error=null`。
- 所有 spinner 均正常消失，每个视频只产生正常频率的 `timeupdate`。
- 未出现 `waiting/stalled/seeking/error` 或事件风暴。

同一轮修改还根据最终实验矩阵更新了 Results 章节。使用 1280x900 桌面 viewport 和 390x844 移动 viewport 检查表格：单元格无重叠，横向滚动限制在表格容器内，移动页面本身没有横向溢出。

### 6.5 线上加载与交互验证

GitHub Pages 更新到功能提交后，使用全新 Chrome profile 对公网页面逐组测试：

- Board 首次进入 `playing` 约 0.80 秒，持续播放期间无 waiting。
- Vase 首次进入 `playing` 约 0.83 秒，弱网发生短暂 waiting 后可同步恢复。
- Card 在进入视口前已由 observer 预加载，进入时可直接播放。
- Chip 首次进入 `playing` 约 0.90 秒，弱网短暂缓冲后可同步恢复。
- 四组最终均为 `readyState=4`、`seeking=false`、`error=null`、spinner 消失。
- 弱网恢复后的最大同步误差为 2.778 ms，没有再次发生事件风暴。

GitHub Pages 对网页视频返回正确的 `video/mp4`、`Accept-Ranges: bytes` 和 `206 Partial Content`。线上 `board_real.mp4` 大小为 4,644,749 字节，其 `_raw` 原始副本为 11,652,263 字节，确认网页引用的是优化版且原始文件可访问。

循环和点击交互使用完整可 seek 的本地文件进行严格边界测试：

- 4 个同步对点击任一侧后，两侧均暂停且时间停止；再次点击后约 50 ms 内同时恢复。
- 将每对视频定位到结尾前 0.2 秒，4 组均触发结束处理、统一归零并继续同步播放。
- 独立 foresight 视频同样通过点击暂停、点击继续和结束循环测试。
- 循环后所有视频均为 `readyState=4`、`paused=false`、spinner 消失、`error=null`。

PACE 的普通视频通过原生 `loop` 循环，但同步对同样在 `ended` 时统一重启。ForeTac 保留统一结束重启，不能给同步视频直接添加原生 `loop`，否则会绕开成对状态和 viewport 暂停。PACE 没有点击暂停 handler；ForeTac 当前交互更完整。ForeTac 的状态化 spinner、IntersectionObserver、固定 16:9 尺寸和移动端行为也优于 PACE，因此未移植 PACE 的常驻底层 spinner、非标准 video `loading="lazy"` 或禁右键等低价值机制。

## 7. Git 同步记录

开始修改前执行了远端检查：

1. 两个 GitHub 仓库的 `main` 均位于提交 `17d84c2`。
2. GitLab `origin/ProjectPage` 已有合作者新增的两个提交：
   - `ec59f1e Add foresight prediction quality figure`
   - `d04232a Add main comparison table placeholder`
3. 本地分支和 GitLab 已分叉，因此先 fetch GitLab，再使用普通 merge 将合作者内容与本地视频同步功能合并。
4. 合并由 Git 的 `ort` 策略自动完成，没有发生文本冲突；合作者新增的图、JSON、绘图工具和网页内容均得到保留。
5. 提交前分别 fetch 两个 GitHub `main`；两个远端均无本地尚未包含的新提交。
6. 首次修复提交为 `0c9ed5c`，其中包含 JavaScript 修复、重新编码视频、`_raw` 副本和本文档。
7. `0c9ed5c` 曾同步到 GitLab `ProjectPage`、GitHub `Foretac/main` 和 GitHub `foretac.github.io/main`，三个远端均推送成功。
8. GitHub Pages 随后更新到 `0c9ed5c`，确认 HTML、Markdown、`video/mp4`、HTTP Range 和 `206 Partial Content` 响应正常。
9. 确认 JavaScript 才是直接根因后，曾恢复原始视频并移除 `_raw` 重复副本，以完成不依赖转码的隔离复测；该中间状态未作为最终媒体方案发布。
10. 用户反馈公网加载仍慢后，量化比较 PACE 与 ForeTac 媒体负载，确认性能层面应优化完整的 8 个任务视频。
11. 最终重新创建 8 个 `_raw` 原始副本，并生成 720p、24 fps、短 GOP 网页版本；本轮同时按用户给定实验矩阵更新 Results 章节。
12. 功能提交 `38a9b69` 完成 Results 重组和全部任务视频优化。推送前发现 co-worker 新增 `e8f5837` 和 `8591889`，因此暂停推送并检查主表标签。
13. 按用户确认，主实验采用 co-worker 的 DP、DP+tactile、π0.5、RDT、ForeAR、Ours 列表；通过合并提交 `5756ded` 保留双方历史和其他 Results 新增内容。
14. `5756ded` 已同步到 GitLab `ProjectPage` 和 GitHub `foretac.github.io/main`；两个远端指向相同提交，GitHub Pages 构建和线上播放验证通过。本轮未推送 GitHub `Foretac` 项目仓库。
15. 提交 `53d0e9c` 将 Ablation Study 的 ForeTac (Full) 移到最后一行，使主实验、结构消融和重建对比均保持 Ours 最后一行。
16. 对 4 个同步视频对和独立 foresight 视频完成点击暂停/继续及结束循环测试；现有行为符合要求，无需额外修改播放状态机。

本文档的跟进提交将继续同步到 GitLab `ProjectPage` 和 GitHub `foretac.github.io/main`。

### 6.6 宽版布局回滚记录

曾将全局容器改为 1200 px，并为段落增加独立宽度；实测发现标题、正文和图片的左边界错位，部分段落换行也不符合原有页面节奏。该布局调整已通过提交 `3905f57` 回滚到 960 px 容器。

回滚后的全面检查结果：

- 1440 px 桌面：Abstract、Method、Results、BibTeX 容器为 960 px；Demos 保持 1280 px。
- 正文宽度为容器内 912 px，段落自然换行，标题、正文和图片边界一致。
- 390 px 移动视口：正文约 342 px，视频单列，表格只在自身容器内横向滚动。
- 桌面和移动端均无页面级横向溢出或元素重叠。
