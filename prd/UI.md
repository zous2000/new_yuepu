# 钢琴练习辅助软件 (Android) - UI/UX 设计文档

## 1. 全局设计原则与系统要求 (Global Principles)
*   **UI 框架**: 全面使用 **Jetpack Compose** 和 **Material Design 3 (MD3)** 规范。
*   **沉浸式体验**: 练习界面需支持全屏 (Edge-to-Edge)，隐藏系统状态栏和导航栏，最大化可视区域。
*   **防误触与大尺寸**: 考虑到练琴场景，所有可点击元素 (IconButton, Slider, Button) 的触控区域 (Touch Target) 至少为 `48.dp`。
*   **屏幕常亮**: 进入练习界面后，需通过 `WindowInsetsController` 或 `FLAG_KEEP_SCREEN_ON` 保持屏幕常亮。

## 2. 主题规范 (Theme & Styling)
请在 `Theme.kt` 和 `Color.kt` 中统一定义以下变量，**禁止在 UI 代码中硬编码**：

*   **主色调 (Primary)**: `#1976D2` (科技蓝，用于 FAB、激活状态的图标、进度条)。
*   **高亮色 (Highlight)**: `#66FFC107` (40% 透明度的琥珀色/黄色，专用于谱面小节的高亮遮罩 `Canvas` 绘制)。
*   **A-B 循环背景色 (Loop Background)**: `#1A2196F3` (10% 透明度的蓝色，用于标记 A 到 B 的循环区间)。
*   **背景色 (Background)**: 
    *   浅色模式 (Light): `#F5F5F5` (浅灰，降低纯白刺眼感)。
    *   深色模式 (Dark): `#121212` (深灰黑)。
*   **排版 (Typography)**: 使用 MD3 默认字体。曲目标题使用 `MaterialTheme.typography.titleLarge` (粗体)，时间进度数字使用等宽字体 (Monospace) 以防宽度跳动。

## 3. 核心界面布局 (Screen Layouts)

### 3.1 首页：曲库管理 (LibraryScreen.kt)
*   **根布局**: `Scaffold`
*   **TopAppBar**:
    *   Title: "我的乐谱" (居左或居中)。
    *   Actions: 设置图标 `Icons.Default.Settings`（内含**服务器 Base URL**、可选 **App Token 调试覆盖**；生产 Token 建议仅 BuildConfig 注入不在 UI 暴露。若保留离线 ZIP 导入，可放在设置二级入口）。
*   **主体内容**: `LazyColumn`（支持下拉刷新 `PullToRefresh` 以**从服务器同步曲目列表**）
    *   列表项 (`ListItem` 或自定义 `Card`): 封面/图标、主标题、副标题（如「已下载 / 待下载」、本地保存时间或服务器 `updatedAt`）。
    *   **未下载**：点击进入可先展示详情或直接进入**下载进度**，完成后进入练习；或提供行内「下载」按钮。
    *   **已下载**：点击进入 `PracticeScreen`。
    *   侧滑删除: `SwipeToDismiss` 删除**本机已下载副本**（不删服务器资源）。
    *   空状态: 无本地曲目且无缓存列表时，提示「下拉从服务器同步」或「请在设置中配置服务器地址」。
*   **FAB (FloatingActionButton)**:
    *   位置: 右下角。
    *   图标: `Icons.Default.Sync` 或 `CloudDownload`（与 Material Icons 可用集合对齐）。
    *   功能: **立即从服务器拉取曲目列表并刷新 UI**（与下拉刷新二选一或并存）。

### 3.2 核心页：练习主界面 (PracticeScreen.kt)
*   **根布局**: `Box` (用于 Z 轴层级堆叠)。
*   **底层 (Layer 0): 乐谱渲染区**
    *   占满全屏 (`modifier.fillMaxSize()`)。
    *   使用 `Image` 加载简谱图片。
    *   **手势交互**: 结合 `Modifier.graphicsLayer` 和 `Modifier.pointerInput` (或 `transformable`) 实现双指缩放 (Zoom)、单指拖拽平移 (Pan)。
    *   **高亮绘制**: 在图片上方叠加一个 `Canvas`，根据当前播放时间，读取 JSON 坐标，使用 `drawRoundRect` 绘制半透明的高亮框。
*   **顶层 (Layer 1): 悬浮控制层 (Controls)**
    *   **顶部控制栏 (Top Control Bar)**: 
        *   半透明渐变背景 (`Brush.verticalGradient`)。
        *   包含: 返回键 `Icons.Default.ArrowBack`，曲目标题，**`Icons.Default.Repeat`：进入/退出「A-B 设点模式」**（非直接开关循环；设点完成后再进入循环播放），以及 **「展开/固定控制栏」** 类按钮（当底栏隐藏时用于重新显示；具体图标可用 `Icons.Default.MoreVert` 或与底栏联动的菜单）。
    *   **底部控制面板 (Bottom Control Panel)**:
        *   悬浮在底部的圆角 `Card`，具有一定的阴影 (`elevation`)。
        *   **第一行**: 当前时间 `Text` + 进度条 `Slider` + 总时长 `Text`。
        *   **第二行**: 
            *   左侧: 速度调节 (Speed) 按钮 (点击弹出 `0.5x - 2.0x` 选择器)。
            *   中间: 巨大的播放/暂停按钮 (使用 `FloatingActionButton` 样式，图标为 `PlayArrow` / `Pause`)。
            *   右侧: 音调调节 (Pitch) 按钮 (点击弹出 `-12 到 +12` 微调器)。

## 4. 交互与动效 (Interactions & Animations)
*   **单击谱面**: **仅**用于切换 **播放/暂停**（与 PRD 一致），**不得**用单击谱面切换控制栏显隐。
*   **控制栏显隐**: 使用 `AnimatedVisibility` (结合 `fadeIn` 和 `fadeOut`) 平滑显示或隐藏顶部与底部控制栏；触发方式限定为：**顶栏上的显隐/菜单按钮**、可选的**屏幕边缘窄条热区**（例如底缘上滑显示底栏）、以及下文 **自动隐藏**。**双击**仍保留给「小节跳转」，避免与单击抢手势。
*   **双击跳转**: 双击乐谱区域，计算点击坐标落在哪一个小节的 `Rect` 内，触发音频 `seekTo`，高亮框瞬间跳转。
*   **高亮框平滑移动**: 当音乐播放进入下一小节时，高亮框的 `Rect` 坐标变化应使用 `animateRectAsState` (或分别对 x, y, width, height 使用 `animateFloatAsState`)，持续时间设为 `150ms`，实现平滑滑动的视觉效果。
*   **自动隐藏**: 如果音频正在播放，且用户 3 秒内无触摸操作，自动触发控制栏的隐藏动效。

## 5. 给 Cursor 的开发指令 (Implementation Directives)
1.  **请严格按照上述 MD3 规范和 Compose 组件建议生成代码。**
2.  优先实现 `PracticeScreen` 的 UI 骨架，使用 Mock 数据（假图片和假 JSON 坐标）来测试双指缩放和 Canvas 绘制逻辑；`LibraryScreen` 需覆盖服务器同步、下载态与本地已下载列表（可先 Mock 列表接口）。
3.  状态管理请使用 `ViewModel` 和 `StateFlow`，将 UI 状态 (如播放进度、缩放比例、控制栏显隐状态、曲库同步与下载进度) 与 UI 视图分离。