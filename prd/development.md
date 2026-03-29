# 钢琴练习辅助软件 (Android) - 技术设计文档 (TDD)

## 1. 架构总览 (Architecture Overview)
本项目采用 **MVVM (Model-View-ViewModel)** 架构，结合 **单向数据流 (UDF - Unidirectional Data Flow)** 模式。
*   **UI Layer**: Jetpack Compose 构建，观察 ViewModel 暴露的 StateFlow。
*   **Domain/Logic Layer**: ViewModel 处理 UI 意图 (Intents)，管理音频播放器状态，计算坐标转换。
*   **Data Layer**: **HTTP 客户端**拉取服务器曲目清单与文件；**本地文件系统**缓存乐谱包；`kotlinx.serialization` 解析 JSON。

## 2. 核心技术栈 (Tech Stack)
*   **语言**: Kotlin
*   **UI**: Jetpack Compose (Material 3)
*   **音频引擎**: AndroidX Media3 (`androidx.media3:media3-exoplayer:1.2.+`)
*   **图片加载**: Coil (`io.coil-kt:coil-compose`)
*   **JSON 解析**: Kotlinx Serialization (`kotlinx-serialization-json`)
*   **异步处理**: Kotlin Coroutines & Flow
*   **网络**: OkHttp 或 Ktor Client（下载文件、请求列表 JSON）；生产环境建议 **HTTPS**。

## 3. 数据模型与存储设计 (Data Layer)

### 3.0 服务端与 App 交互（约定）
*   **Base URL**：由用户在设置中配置（或内置默认测试域名），例如 `https://example.com/api/`。
*   **App Token（固定）**：App 请求**曲目列表**与**下载乐谱文件**时必须在 HTTP 头携带，例如 `Authorization: Bearer <APP_TOKEN>` 或 `X-App-Token: <APP_TOKEN>`（实现时与服务端统一）。Token 值由服务端生成并配置到 App：**生产环境用 `BuildConfig` / 安全存储注入**；调试可在设置中覆盖（可选）。
*   **曲目列表**（示例形状，字段名实现时可微调）：
    ```json
    {
      "scores": [
        {
          "songId": "santao_che_01",
          "title": "三套车",
          "updatedAt": 1710000000000,
          "files": {
            "data": "/scores/santao_che_01/data.json",
            "image": "/scores/santao_che_01/sheet.jpg",
            "audio": "/scores/santao_che_01/audio.mp3"
          }
        }
      ]
    }
    ```
    App 将 `files.*` 与 Base URL 拼接后下载；若列表已带绝对 URL，则直接使用。**列表与每个文件下载请求均须带 App Token。**
*   **下载完成后**写入下方沙盒目录，保证与 `data.json` 内 `imageFile` / `audioFile` 文件名一致；**产品约定下发音频仅为 MP3**（管理端上传 MIDI 时由**服务端转码**后写入目录并更新/生成 `data.json`）。
*   **管理端鉴权**：与 App 分离；管理员使用**用户名 + 密码**登录后调用上传/发布等接口（Session Cookie 或 JWT，由 Phase 0 后端实现）。

### 3.1 目录结构 (Sandbox Storage)
自服务器下载或（可选）ZIP 解压后，统一落在 App 内部沙盒 `Context.filesDir/scores/`：
```text
filesDir/scores/
└── santao_che_01/              # songId 作为文件夹名
    ├── data.json               # 坐标与时间轴配置
    ├── sheet.jpg               # 简谱图片
    └── audio.mp3               # 音频文件
```

### 3.2 Repository 职责（建议）
*   `ScoreRemoteDataSource`：请求曲目列表、下载字节流到临时文件再移动到 `scores/{songId}/`。
*   `ScoreLocalDataSource`：枚举已下载的 `songId`、读取 `data.json`、删除目录。
*   `ScoreRepository`：合并远程列表与本地状态（已下载 / 需更新），供 `LibraryViewModel` 使用。

### 3.3 核心数据实体 (Data Classes)
```kotlin
@Serializable
data class ScoreData(
    val songId: String,
    val title: String,
    val imageFile: String,
    val audioFile: String,
    val measures: List<Measure>
)

@Serializable
data class Measure(
    val id: Int,
    val startTimeMs: Long,
    val endTimeMs: Long,
    val rect: RectData
)

@Serializable
data class RectData(val x: Float, val y: Float, val w: Float, val h: Float)
```

## 4. 状态管理设计 (State Management)

### 4.1 练习界面 UI 状态 (PracticeUiState)
ViewModel 需对外暴露一个统一的 `StateFlow<PracticeUiState>`：
```kotlin
data class PracticeUiState(
    val isLoading: Boolean = true,
    val scoreData: ScoreData? = null,
    val isPlaying: Boolean = false,
    val currentPositionMs: Long = 0L,
    val playbackSpeed: Float = 1.0f,
    val pitchOffset: Int = 0, // 半音阶，0 为原调；产品范围 -12..+12
    val abLoopState: ABLoopState = ABLoopState.Inactive,
    val controlsVisible: Boolean = true
)

sealed class ABLoopState {
    object Inactive : ABLoopState()
    data class PointASet(val startTimeMs: Long) : ABLoopState()
    data class Active(val startTimeMs: Long, val endTimeMs: Long) : ABLoopState()
}
```

### 4.2 曲库列表 UI 状态 (LibraryUiState，建议)
*   `isRefreshing`、`remoteError`、`items: List<ScoreListItem>`，其中每项含 `songId`、`title`、`updatedAt`、`localState`（`NotDownloaded` / `Downloaded` / `Downloading(progress)` / `UpdateAvailable`）等，供 `LibraryScreen` 与下拉刷新、FAB 同步联动。

## 5. 核心引擎设计 (Core Engines)

### 5.1 音频与时间轴引擎 (Audio & Timeline Engine)
*   **实例管理**: 在 ViewModel 或专门的 `AudioPlayerManager` 中持有 `ExoPlayer` 实例。生命周期与 `PracticeScreen` 绑定（进入初始化，退出释放）。
*   **高频轮询**: 使用 Coroutine Flow 实现进度轮询，驱动 UI 上的光标移动。
    ```kotlin
    // 伪代码：每 50ms 轮询一次播放进度
    flow {
        while(currentCoroutineContext().isActive) {
            if (exoPlayer.isPlaying) {
                emit(exoPlayer.currentPosition)
            }
            delay(50)
        }
    }
    ```
*   **变调变速**: 使用 ExoPlayer 的 `PlaybackParameters`。
    ```kotlin
    val params = PlaybackParameters(speed, pitch)
    exoPlayer.playbackParameters = params
    ```

### 5.2 渲染与坐标系转换引擎 (Rendering & Matrix Math)
这是本项目的**最核心难点**。JSON 中记录的坐标是基于**图片原始像素**的，而屏幕上显示的图片经过了缩放和平移。必须进行坐标系转换。

*   **状态记录**: 在 Compose 中记录图片的缩放比例 (`scale`) 和平移偏移量 (`offsetX`, `offsetY`)。
    ```kotlin
    var scale by remember { mutableStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    ```
*   **正向转换 (JSON坐标 -> 屏幕坐标)**: 用于在 Canvas 上绘制高亮框。
    $$X_{screen} = X_{image} \times scale + offset_X$$
    $$Y_{screen} = Y_{image} \times scale + offset_Y$$
    $$Width_{screen} = Width_{image} \times scale$$
    $$Height_{screen} = Height_{image} \times scale$$
*   **逆向转换 (屏幕坐标 -> JSON坐标)**: 用于处理用户双击屏幕时，判断点击了哪个小节。
    $$X_{image} = \frac{X_{screen} - offset_X}{scale}$$
    $$Y_{image} = \frac{Y_{screen} - offset_Y}{scale}$$

## 6. 关键交互逻辑 (Interaction Logic)

### 6.1 A-B 循环逻辑
*   **UI**: 顶栏 `Repeat` 切换 **设点模式**；仅在 `ABLoopState.Active` 时，轮询中执行循环跳转。
在轮询进度的 Coroutine 中加入 A-B 循环检测：
```kotlin
if (abLoopState is ABLoopState.Active) {
    if (currentPositionMs >= abLoopState.endTimeMs) {
        exoPlayer.seekTo(abLoopState.startTimeMs)
    }
}
```

### 6.2 双击跳转逻辑 (Double Tap to Seek)
1. 拦截 Compose 的 `detectTapGestures(onDoubleTap = { offset -> ... })`。
2. 使用上述的**逆向转换公式**，将点击的屏幕 `offset` 转换为图片原始坐标 `(x, y)`。
3. 遍历 `ScoreData.measures`，判断 `(x, y)` 是否落在某个 `Measure.rect` 内部。
4. 如果命中 `Measure`，调用 `exoPlayer.seekTo(measure.startTimeMs)`，并 `exoPlayer.play()`。

## 7. 服务端实现建议（Phase 0，与 Android 解耦）
*   **形态**：Nginx 托管静态页（打点小工具 + 管理前端）+ 轻量后端（Node / Python Flask-FastAPI / Go 等）处理**管理员登录（用户名密码）、上传、MIDI→MP3 转码（FFmpeg）、列表 JSON、按路径读文件**。
*   **存储**：磁盘目录与 App 约定一致，例如 `scores/{songId}/data.json|sheet.xxx|audio.mp3`。
*   **安全**：**管理 API**：仅已登录管理员可访问。**App API**：校验请求头中的**固定 App Token**，与管理员凭证分离；Token 与服务端环境变量或配置文件一致。

## 8. 给 Cursor 的开发建议
*   **依赖注入**: 建议使用 Hilt 或简单的 ViewModel Factory 管理依赖。
*   **手势冲突**: 注意 `Modifier.transformable` (缩放平移) 和 `detectTapGestures` (单击/双击) 的手势冲突处理，建议使用底层 `awaitPointerEventScope` 精细控制，或使用成熟的 Compose Zoom 库 (如 `Telephoto`)。
*   **性能优化**: Canvas 绘制高亮框时，只绘制当前 `currentPositionMs` 所在的那个 `Measure`，避免遍历所有小节导致掉帧。