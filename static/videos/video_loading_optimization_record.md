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
13. 主实验采用 DP、DP+tactile、π0.5、RDP、ForeAR、Ours 列表；其中该 tactile baseline 最终按用户确认统一命名为 RDP，并通过合并提交 `5756ded` 保留双方历史和其他 Results 新增内容。
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

### 6.7 选择性宽布局验证

参考 OmniVTA 的分层宽度策略，采用 section 级宽容器而不是再次修改全局正文宽度：

- 默认 Abstract、Key Idea、BibTeX 容器保持 960 px。
- Method 容器使用 1200 px，说明文字仍限制为 960 px，架构和训练图使用更宽媒体区域。
- Results、Demos 容器使用 1280 px，说明文字仍限制为 960 px，结果图和视频使用宽区域。
- 移动端继续由现有断点切换为单列，表格只在自身容器内滚动。

在 1440x900、1280x900 和 390x844 三种 viewport 下验证：

- 页面级 `scrollWidth` 均等于 client width，无横向溢出。
- 1440 px 下 Method 为 1200 px，Results/Demos 为 1280 px，Results 图宽约 1230 px，视频双列各约 604 px。
- 1280 px 下三张 Results 表均无需横向滚动。
- 390 px 下正文约 342 px，视频单列，三张表独立横滚且没有元素重叠。
- 所有章节的标题、正文和媒体边界无重叠或截断。

### 6.8 终版媒体统一到 ProjectPage-v3（2026-09-22）

- 终版页面实际播放的 Hero、Overview、四个任务双视频和 foresight 视频均改为从 `/home/chenzhiyuan/projects/foretac_web-v3/static/videos/` 复制的版本。
- 覆盖了 v3 与终版同名但编码不同的 `board_real`、`vase_real`、`chip_real`、`chip_viz` 及其预览图；其余引用媒体也逐一用 SHA256 核对。
- 终版旧有的 Generalization 播放段在 v3 中没有对应媒体，已从页面移除，避免混用非 v3 视频。旧文件和 `_raw` 文件仍作为未引用的本地副本保留。
- 调亮顶部 Hero 视频蒙版：桌面和移动端均降低海军蓝 scrim 的不透明度，同时保留标题文字对比度。
- 终版页面重新检查后，所有可见视频来源均指向 v3 媒体，Hero 画面可见度改善；原 8123 和 8124 工作树未修改。

## 2026-09-23 依据 foretac_v3 重建 8125 页面与视频交互复测

### 本次问题与排查

1. 对照 `/home/chenzhiyuan/projects/foretac_manuscript/foretac_v3/main.tex` 逐项检索网页，发现旧页面仍含旧标题、Socket/five-task 叙事、SSR/Safe Success/Contact Failure、TBD 消融行、Trust-Region/Energy Model 术语和过时的五任务 overview 片段。
2. 检查现有媒体引用，确认四组任务视频仍是有效 MP4；本轮没有再次转码，也没有删除已有 `_raw` 副本。旧 `foretac_overview.mp4` 保留在本地但不再被 HTML 引用，避免发布与 v3 不一致的旁白。
3. 浏览器边界测试发现同步视频若同时使用原生 `loop`，可能绕过 `ended` 同步处理；且在尾帧 `readyState` 降低后先等待 `canplay` 会使循环停在尾帧。

### 实施内容

- 重写 `index.html`：标题、摘要、方法、四任务、SR/CSR、主结果、消融、重建、action conditioning、horizon、scorer transfer、guidance diagnostics、`pi_0.5` 和计算成本均按 v3 稿件对齐。
- 删除页面中的 Socket、五任务、SSR/Safe Success、Contact Failure、TBD 和 Trust-Region/Energy Model 旧表述；主结果方法为 DP、RDT、DP + Tactile Concat、RDP、ForeTac，ForeTac 保持最后一行。
- 引入论文当前概念图、方法图和 Fig. 4 诊断图到 `static/images/`；图片设置稳定尺寸、`decoding` 和下折 `loading` 属性。
- 重建 `static/css/style.css`：全局内容边界 1200px，正文约 74ch，媒体/表格保留宽版；补充移动端汉堡菜单、skip link、表格滚动、错误提示和响应式 Hero。
- 成对视频移除原生 `loop`，由 JS 统一处理结束归零、同步播放、点击暂停/继续、缓冲恢复和视口激活；增加键盘 Enter/Space 操作。

### 验证结果

- `git diff --check`、内联 JavaScript `node --check` 和静态资源存在性检查通过。
- Chrome 1440x1000、390x844 以及长页截图检查通过：Hero、方法图、结果表、四组视频和 BibTeX 无明显重叠；移动端无页面级横向溢出。
- Firefox WebDriver 检查：移动视口 `scrollWidth == clientWidth`；结果表容器分别在自身内部滚动；标题为 `ForeTac: Predictive Contact Guidance for Generative Robot Policies`；无媒体错误节点。
- 四组任务视频首次进入均达到 `readyState=4` 并同时播放；点击任一侧后两侧均暂停，离开/返回视口不会覆盖用户暂停状态，再次点击同步恢复，复测同步误差约 5--6 ms。
- 将四组视频定位到结束前约 0.12 秒后复测，均能统一回到开头继续播放，最终 `paused=false`、`ended=false`、`error=null`、spinner 消失。
- `ffprobe` 检查确认任务视频均为 H.264；四组 nominal duration 分别为 31.1667、20.9167、10.0833、14.125 s。`chip_viz` 的编码时长与 `chip_real` 相差约 0.35 ms，不影响统一重启和同步播放。

本次仅修改本地 `foretac_web-final` 工作区及本记录，未执行 commit 或 push。

## 2026-09-23 Hero、宣传片与稿件图片同步优化

### 用户反馈与排查

1. 8125 Hero 顶部黑板和花瓶画面中，擦拭区域被裁到矩形上缘，首屏主要看到静止物体；检查 1280x720 四宫格成片、源视频时间轴和 CSS 后确认问题来自两层原因：新版成片从各路视频 0 秒开始，黑板/花瓶动作尚未进入；页面 Hero 约 16:9 但使用 `object-fit: cover`，桌面视口还会再次裁掉上下边缘。
2. 对比历史 `build_hero_background.py` 与 Git 历史成片，确认旧版本曾使用 Board/Vase/Card/Chip 的时间偏移 `5/3/1/2` 秒，并裁除顶部 76px 标签栏。原始桌面素材路径已不存在，因此用当前网页任务视频按该已核对的 filter 重建，保留 card/chip 的可见内容。
3. 8124 宣传视频原页面虽有 `controls`，但 8125 没有播放器；进一步用 Chrome 检查发现本地 `python -m http.server` 对 Range 请求返回 `200` 而不是 `206 Content-Range`。因此 `metadata` 预加载时拖到未缓冲位置会停在 0 秒，这是服务器 Range 能力问题，不是原生 controls 缺失。
4. 对 117 秒宣传片逐帧抽样并检索 v3 稿件，发现其中仍有当前稿件已删除的 safe success/SSR、trust-region 和旧 0--2 px 叙述。旧的 45 秒版本只包含当前四任务、概念、方法、同步视频和 SR/CSR 结果，故选择 45 秒版本作为网页播放器素材；117 秒文件保留为本地 legacy 副本，不在 HTML 引用。
5. 核对 `/home/chenzhiyuan/projects/foretac_manuscript/foretac_v3/fig-submission/`，确认三张权威 PNG 的实际内容分别为：Fig.1 概念图、Fig.2 方法架构、Fig3 实验平台与四任务，而不是按文件名机械对应网页旧图。

### 实施

- 旧 Hero 成片和海报分别备份为 `foretac_hero_loop_before_layout.mp4`、`foretac_hero_poster_before_layout.jpg`。
- 用已验证的时间偏移和顶部标签栏裁切重建 Hero；为顶部两路增加居中的缩放和背景填充，使擦拭器/擦块不贴边，同时保持 1280x720、H.264、24 fps、faststart。新海报取新成片首帧。
- 将 `foretac_overview.mp4` 改为 45 秒、1920x1080、H.264 faststart 版本；原 117 秒版本保存为 `foretac_overview_legacy_117s.mp4` 及对应海报。
- 在 Overview（Abstract 前）增加独立宣传片 `<video controls playsinline preload="auto">`。播放器不加入任务视频同步状态机或自定义点击拦截，保留浏览器原生进度条；4.6 MB 文件使用 `preload=auto`，使无 Range 的本地服务器在完整缓冲后也能拖动。
- 从 `fig-submission` 复制原始图片到 `static/images/manuscript/`，并生成 2400px WebP 浏览器副本：Fig.1 用于概念/Overview，Fig.2 用于 Method，Fig3 用于 Results 任务总览；原始 PNG 保留以便追溯。
- 将方法图从原 Overview 位置移入 Method，将四任务总览图放在 Results 开头；页面文字继续以 `foretac_v3/main.tex` 为唯一事实源。

### 验证

- `ffprobe`：Hero 仍为 1280x720、12 s、H.264、24 fps；宣传片为 1920x1080、45 s、H.264，`moov` 位于文件开头。
- Chrome 1440x900 和 390x844 截图：Hero 顶部黑板/花瓶主体与擦拭区域可见，移动端无页面横向溢出；Overview 播放器位于 Abstract 前且布局稳定。
- Chrome CDP 检查：Overview 原生 `controls=true`、duration=45、seekable=[0,45]；在本地服务器完整缓冲后设置 `currentTime=30` 成功，事件序列包含 `seeking/seeked`。任务视频仍为 8 个成对视频，未出现媒体错误节点。
- `git diff --check` 通过。本轮只修改本地 `foretac_web-final` 工作区和记录文档，未 commit、未 push。

## 2026-09-24 依据 v3 终稿事实边界修正 8125（本地）

### 复核发现

1. 逐帧复核 `foretac_overview.mp4` 后确认其末页仍标注 `SR / SSR`，且中段保留旧版 score/scale 画面和 legacy guidance 术语；这些内容不符合当前 `foretac_v3/main.tex` 的 `SR / CSR`、两面板 Fig. 4 和当前 guidance 表述。
2. `board_guidance_evidence.png` 是旧版诊断图，尺寸为 3076x1692；当前稿件 Fig. 4 是 `board_guidance_panels_r7_20260923.png` 的两面板版本（2799x1080）。
3. 网页 flow-matching 表并非独立的 Table VIII，而是论文 Table I 的第二个 block；计算成本表对应论文 Table VIII。网页原先写成 Table VIII/Table IX，编号错误。
4. 任务视频渲染脚本对 score/scale 使用启发式诊断信号；Chip 右侧 marker panel 来自实测 `marker_offset`，不能统称为真实部署的 foresight/guidance 输出。

### 修正

- 移除 `foretac_overview.mp4` 播放器及其加载脚本引用。45 秒和 117 秒宣传片均保留为本地未发布素材，待按 v3 事实重新导出后再嵌入。
- 主结果表补入论文 Table I 的 `pi_0.5` / `pi_0.5 + ForeTac` block，并将主方法命名统一为 `DP + ForeTac`；消融行统一为论文的 `ForeTac`。
- 将 flow-matching 说明改为“Table I 第二个 block”，将计算成本说明改为 `Table VIII`。
- 将网页诊断图替换为 `static/images/board_guidance_panels_v3.png`，并同步更新 alt、caption 和统计范围。
- 将演示区说明改为：Board/Vase/Card 为 predicted marker visualization，Chip 为 measured marker visualization；曲线只作为 illustrative diagnostics，不作为额外部署指标。
- 更新 README，使标题、方法术语、图资产、媒体来源和当前指标与 v3 一致。

### 验证

- `node --check`、`git diff --check` 和本地资源引用检查通过。
- 重新核对 `main.aux`：I=main results（含 flow block），II=ablation，III=reconstruction，IV=action conditioning，V=horizon，VI=recorded ranking，VII=scorer transfer，VIII=efficiency；网页说明已与此一致。
- 未执行 commit、push 或删除任何历史媒体；当前变更仅在本地 `foretac_web-final`。

## 2026-09-24 移动端 Hero 动态区域复核（本地）

### 发现与修正

- Chrome 移动视口复核发现，Hero 使用 `object-fit: contain` 后，16:9 视频带之外仍会显示桌面 poster 背景；该区域不会随视频时间变化，容易造成“整块画面都在播放”的误解。
- 在 `@media (max-width: 768px)` 中将 `.hero-video` 的背景改为纯 `var(--navy)`，保留完整四象限视频带，并让标题、摘要和按钮落在明确的深色静态区域。桌面端仍使用满幅动态视频和原有 poster 回退。

### 验证

- Chrome CDP 视口 `1440x900` 与 `390x844`：页面 `scrollWidth == clientWidth`（分别为 1425 与 390），视频总数 9（1 个 Hero + 8 个任务视频），同步任务对 4 组，Overview 视频为 0。
- 逐组滚动激活后，9 个视频均为 `readyState=4`，`error=null`，加载 spinner 数量为 0，错误状态节点数量为 0。
- 点击任一任务视频：左右视频同时暂停，再次点击同时恢复；两次检查的播放时间差分别约 `0.00001 s` 和 `0.00006 s`。
- 将四组视频定位到尾帧附近后等待循环：每组均回到约 1.0 s、`paused=false`、`ended=false`，左右时间差为 0。
- 复查桌面 Results/Demos、移动 Results/Demos 截图：正文、表格、图注和视频卡无重叠，表格仅在自身容器内横向滚动；移动端 Hero 四个任务象限可辨认。
- 本轮修改 `static/css/style.css`、`README.md` 和本记录，未执行 commit、push 或删除历史媒体。

## 2026-09-24 宣传片 Foresight 页按 v3 事实边界重导出（本地）

### 复核与处理

- 逐帧检查 `static/videos/foresight_prediction_board_episode6_tplus16.mp4`，确认原始画面烧录了单个 episode 的 `t`/`t+H`、L2、逐帧 `max`/`mean` 以及 episode-level raw/smoothed L2 曲线。
- 对照 `foretac_v3/main.tex` 的预测时域实验：论文只报告跨 9,631 个 held-out Board windows 的 H=1/4/8/12/16 聚合结果，不报告上述单集数值。因此这些诊断数值不作为网页宣传片中的可解释主结果。
- 在 `tools/build_v3_media.sh` 中重建第 5 页：遮盖原始标题和单帧统计，裁掉 episode-level 曲线，仅保留 `GT future`、`Predicted future`、`Error (pred - GT)` 三个定性面板；页眉改为 `Action-conditioned tactile foresight` 与 `Ground-truth future - predicted future - error (qualitative, H=16)`。
- 重新生成 `static/videos/foretac_overview.mp4` 及海报；117 秒旧片继续作为 `foretac_overview_legacy_117s.mp4` 本地副本，不作为当前页面素材。

### 验证

- `ffprobe`：成片为 45.000 s、1920x1080、H.264、30 fps，`moov` 位于文件开头（faststart）。
- 抽查成片第 5 页约 25--31 s 的首帧、中段和末帧：未见单集 `L2`、`max/mean` 或 episode-level 误差曲线，只见三面板定性预测过程；H=16 仅作为可视化条件标识。
- 当前变更仅在本地，尚未 commit 或 push；发布前需再次检查共享远程仓库并同步成片、海报和记录。

## 2026-09-24 终版网页媒体与事实一致性审计（本地）

- 重新运行 `tools/build_v3_media.sh`，确认第 5 页遮罩后的定性 foresight 画面仍只展示三面板，没有单集 `L2`、`max/mean` 或 episode-level 曲线。
- 对照 `foretac_v3/main.tex` 和网页逐项检查主结果、消融、TacVAE 重建、action conditioning、prediction horizon、scorer transfer、Fig. 4 guidance diagnostics、flow-matching 和 efficiency；未发现旧的 SSR、Trust-Region、Energy Model、Socket、五任务或 TBD 公开表述残留。
- 对所有 HTML 媒体引用执行静态资源存在性检查，28 个本地资源引用全部存在；`board_guidance_panels_v3.png` 已作为当前 Fig. 4 资源保留。当前页面共有 10 个 `<video>` 元素（Hero、Overview 和 8 个任务视频）。
- `ffprobe` 复核：Hero 为 12 s/1280x720/H.264/24 fps，Overview 为 45 s/1920x1080/H.264/30 fps/faststart；八个任务视频的左右时长分别严格匹配。
- 额外记录媒体元数据例外：七个任务文件为 24 fps，`chip_viz.mp4` 与其 `_raw` 源保留 3947/250（约 15.79 fps）的原始 cadence，但与 `chip_real.mp4` 时长一致，网页同步逻辑按媒体时间轴工作，不依赖相同帧率。
- 重新生成后的成片、海报和构建脚本仍只存在本地工作树；本轮没有 commit、push 或删除历史副本。

### 6.9 Hero Fast Start 元数据修正

- 复核二进制 atom 位置时发现，脚本最后对 Hero 使用 `-c copy` 会把中间文件的 `+faststart` 状态丢掉，导致最终 `foretac_hero_loop.mp4` 的 `moov` 位于文件尾。
- 已在 `tools/build_v3_media.sh` 的最终复制步骤加入 `-movflags +faststart`，并重新生成 Hero 与海报。
- 复核结果：Hero 和 Overview 的 `moov` 均位于 `mdat` 之前；两者仍分别为 12 s/24 fps 和 45 s/30 fps。
- Overview 使用浏览器原生 `loop`，仍保留原生 controls 和进度条拖动，且不接入任务双视频同步状态机。
- README 已区分普通本地 HTTP 预览与真正的 Range/206 验证，避免把 Python simple server 的完整文件传输误当成部署端分段传输能力。

### 6.10 公开文案复核

- 将网页和 README 中的内部版本措辞 `v3-consistent` 改为面向读者的中性表述；Overview 说明明确指向论文已报告的 SR/CSR 结果。
- 将证据条的无障碍标签从 `Verified evidence` 改为 `Headline results`，避免在实验事实表尚未冻结置信区间和统计检验前作出过强的验证承诺。

## 2026-09-24 Hero 四宫格等尺寸修正（本地）

### 问题定位

- 用户复核发现宽屏 Hero 中上排黑板/花瓶看起来占据更大区域，而下排刷卡/夹薯片只露出一部分。
- 对 1920x1080 截图和 CSS 逐项检查后确认，问题不是四宫格成片的 tile 尺寸：原始成片为四个 640x360 象限；真正原因是 `.hero-video` 使用 `object-fit: cover` 与 `object-position: center top`。在 1920 宽屏中，视频被放大到 1920x1080 后从顶部对齐，超出 Hero 高度的部分全部从底部裁掉，因此下排被截断。
- 同时发现上排曾使用“缩小前景 + 模糊背景填充”的 filter，上排清晰内容高度只有约 322px，和下排的 360px 视觉尺度不一致。

### 处理方案

- `tools/build_v3_media.sh` 将黑板和花瓶源视频去掉 76px 标签条及两侧边缘，裁成 1144x644 的 16:9 视野，再统一缩放为 640x360；刷卡和薯片使用同样的 640x360 输出尺寸。
- 移除上排专用的模糊背景/前景叠加逻辑，避免上排清晰内容与下排产生不同的视觉比例。
- `static/css/style.css` 将桌面 Hero 的 `object-position` 改为 `center center`，使 cover 裁切在上下对称分配；移动端继续使用完整的 `contain` 视频带。

### 验证

- 重新生成 `foretac_hero_loop.mp4` 和 poster；Hero 仍为 1280x720、12s、H.264、24fps，`moov` 位于 `mdat` 之前。
- Chrome 截图复核 1920x1080、1440x900 和 390x844：四个象限的可视高度一致，宽屏下排不再只露出一部分，页面无水平溢出。
- `bash -n tools/build_v3_media.sh`、内联 JavaScript 语法检查和 `git diff --check` 均通过。
- 本次仅修改本地网页工作区，尚未 commit 或 push。

## 2026-09-24 Hero 全宽填充与顶部导航字号调整（本地）

### 问题与方案

- `contain` 方案已经保证四个物体完整，但 1920px 等超宽屏会在前景视频两侧留下留白。
- 采用同源双层视频：背景层用 `cover`、模糊和低透明度铺满 Hero，前景层继续用 `contain` 保留完整四宫格。前景视频的 `contain` 留白设为透明，避免遮住背景层。
- 对照 8124，8125 原导航为 13px/500，视频背景上辨识度偏低；调整为 14px/600，保留当前简洁间距而不照搬 8124 的排版。

### 排查与修复

- 第一次截图中超宽屏两侧仍接近纯色。检查后确认前景 `.hero-video` 的 `background: var(--navy)` 覆盖了背景视频；将 `min-width: 1600px` 和移动端前景背景改为 `transparent` 后，模糊背景正常透出。
- Hero 脚本现在同步两层视频的播放、暂停、循环和时间位置；点击仅绑定前景层，背景层设为 `aria-hidden` 和 `tabindex=-1`。

### 验证

- `git diff --check` 通过。
- 内联 JavaScript 通过 `new Function(...)` 语法检查。
- Chrome headless 截图：`/tmp/foretac-final-dual2-1920.png`、`/tmp/foretac-final-dual2-1440.png`、`/tmp/foretac-final-dual2-390.png` 均生成成功。
- 1920×1080：四个前景物体完整可见，两侧由同源动态模糊视频填充；1440×900：保持原有全宽构图；390×844：移动端导航折叠，标题、按钮和视频没有重叠。
- 本地 HTTP 服务 `http://10.169.12.108:8125/` 当前仅用于预览；本次未执行 commit 或 push。

## 2026-09-24 Hero 宽屏完整显示与顶部内容重心修正（本地）

### 追加问题

- 继续观察 1920px 宽屏时，黑板/花瓶的擦拭区域仍贴近 Hero 上边缘，右下角薯片场景也容易被浏览器裁切；仅将 `object-position` 置中只能让裁切对称，不能保证四格内容完整显示。
- 进一步抽查发现：在 1920x1080 视口中 Hero 高度上限为 820px，`object-fit: cover` 会把 1280x720 四宫格放大到 1920x1080，并从上下各裁掉约 87 个源像素。

### 修正

- 对黑板和花瓶源视频改用 `crop=996:560:142:76`：保留顶部动作区域、去除顶部标签和更多底部空白，再统一缩放到 640x360；下方刷卡和薯片仍为 640x360，四格尺寸不变。
- 在 `min-width: 1600px` 下将 Hero 视频改为 `object-fit: contain`，以深色背景承载两侧留白，确保四个 640x360 象限完整显示；1600px 以下保留原有满幅 cover 布局，移动端继续使用 contain。
- 重新生成 Hero 视频和 poster；Overview 视频同时由构建脚本重新生成，内容和编码参数保持不变。

### 验证

- Chrome 截图复核 1920x1080、1440x900 和 390x844：黑板、花瓶、刷卡、薯片四个矩形均完整可见；宽屏下右下角不再被截断，顶部擦拭器/接触区域位于各自 tile 内部。
- Hero 仍为 1280x720、12s、H.264、24fps；Hero 与 Overview 的 `moov` 均位于 `mdat` 之前。
- 局域网 8125 服务返回的 `index.html` 与本地 SHA256 一致；本地资源引用、内联 JavaScript、`bash -n tools/build_v3_media.sh` 和 `git diff --check` 均通过。
- 本次仅修改本地网页工作区，尚未 commit 或 push。
