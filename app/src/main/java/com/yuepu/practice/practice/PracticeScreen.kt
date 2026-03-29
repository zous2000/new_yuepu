package com.yuepu.practice.practice

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.view.WindowManager
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Repeat
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import coil.compose.AsyncImage
import com.yuepu.practice.ui.theme.HighlightAmber
import java.io.File
import kotlin.math.max
import kotlin.math.min
import kotlinx.coroutines.delay

private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PracticeScreen(
    onBack: () -> Unit,
    vm: PracticeViewModel = hiltViewModel(),
) {
    val st by vm.state.collectAsState()
    val latestScore by rememberUpdatedState(st.score)
    val context = LocalContext.current

    DisposableEffect(Unit) {
        val window = context.findActivity()?.window
        window?.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        onDispose {
            window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    LaunchedEffect(st.controlsVisible, st.isPlaying) {
        if (st.controlsVisible && st.isPlaying) {
            delay(3000)
            vm.setControlsVisible(false)
        }
    }

    var speedDialog by remember { mutableStateOf(false) }
    var pitchDialog by remember { mutableStateOf(false) }

    if (st.isLoading) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text("加载中…")
        }
        return
    }
    if (st.loadError != null) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(st.loadError!!)
                TextButton(onClick = onBack) { Text("返回") }
            }
        }
        return
    }

    val path = st.imageAbsolutePath ?: return
    val iw = st.naturalImageWidth
    val ih = st.naturalImageHeight

    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val density = LocalDensity.current
            val W = with(density) { maxWidth.toPx() }
            val H = with(density) { maxHeight.toPx() }
            val fit = if (iw > 0f && ih > 0f) min(W / iw, H / ih) else 1f

            var zoom by remember { mutableFloatStateOf(1f) }
            var pan by remember { mutableStateOf(Offset.Zero) }
            val tf = rememberTransformableState { zc, pc, _ ->
                zoom = (zoom * zc).coerceIn(0.5f, 5f)
                pan += pc
            }

            val dispW = max(1f, iw * fit * zoom)
            val dispH = max(1f, ih * fit * zoom)
            val left = (W - dispW) / 2f + pan.x
            val top = (H - dispH) / 2f + pan.y

            fun screenToImage(off: Offset): Pair<Float, Float> {
                val ix = (off.x - left) / dispW * iw
                val iy = (off.y - top) / dispH * ih
                return ix to iy
            }

            AsyncImage(
                model = File(path),
                contentDescription = null,
                contentScale = ContentScale.FillBounds,
                modifier = Modifier
                    .offsetDp(left, top, density)
                    .size(with(density) { dispW.toDp() }, with(density) { dispH.toDp() })
                    .transformable(tf),
            )

            val m = st.currentMeasure
            val dlTarget = if (m != null) left + m.rect.x / iw * dispW else 0f
            val dtTarget = if (m != null) top + m.rect.y / ih * dispH else 0f
            val dwTarget = if (m != null) m.rect.w / iw * dispW else 0f
            val dhTarget = if (m != null) m.rect.h / ih * dispH else 0f

            val dl by animateFloatAsState(dlTarget, tween(150), label = "dl")
            val dt by animateFloatAsState(dtTarget, tween(150), label = "dt")
            val dw by animateFloatAsState(dwTarget, tween(150), label = "dw")
            val dh by animateFloatAsState(dhTarget, tween(150), label = "dh")

            Canvas(Modifier.fillMaxSize()) {
                if (m != null && dw > 1f && dh > 1f) {
                    drawRoundRect(
                        color = HighlightAmber,
                        topLeft = Offset(dl, dt),
                        size = Size(dw, dh),
                        cornerRadius = CornerRadius(12f, 12f),
                    )
                }
                when (val ab = st.abLoop) {
                    is AbLoopState.Active -> {
                        val sMeasures = st.score?.measures ?: emptyList()
                        val a = sMeasures.firstOrNull { it.startTimeMs == ab.startTimeMs }
                        val b = sMeasures.firstOrNull { it.endTimeMs == ab.endTimeMs }
                        if (a != null && b != null) {
                            val al = left + min(a.rect.x, b.rect.x) / iw * dispW
                            val at = top + min(a.rect.y, b.rect.y) / ih * dispH
                            val ar = left + max(a.rect.x + a.rect.w, b.rect.x + b.rect.w) / iw * dispW
                            val abt = top + max(a.rect.y + a.rect.h, b.rect.y + b.rect.h) / ih * dispH
                            drawRoundRect(
                                color = Color(0x1A2196F3),
                                topLeft = Offset(al, at),
                                size = Size(max(1f, ar - al), max(1f, abt - at)),
                                cornerRadius = CornerRadius(8f, 8f),
                            )
                        }
                    }
                    else -> {}
                }
            }

            Box(
                Modifier
                    .fillMaxSize()
                    .pointerInput(iw, ih, dispW, dispH, left, top, latestScore) {
                        detectTapGestures(
                            onTap = { vm.togglePlayPause() },
                            onDoubleTap = { off ->
                                val s = latestScore ?: return@detectTapGestures
                                val (ix, iy) = screenToImage(off)
                                val hit = s.measures.firstOrNull { measure ->
                                    ix >= measure.rect.x && ix <= measure.rect.x + measure.rect.w &&
                                        iy >= measure.rect.y && iy <= measure.rect.y + measure.rect.h
                                }
                                if (hit != null) vm.seekToMeasureStart(hit)
                            },
                        )
                    },
            )
        }

        if (st.controlsVisible) {
            Box(
                Modifier
                    .fillMaxWidth()
                    .align(Alignment.TopCenter)
                    .statusBarsPadding()
                    .background(
                        Brush.verticalGradient(
                            listOf(Color.Black.copy(alpha = 0.55f), Color.Transparent),
                        ),
                    )
                    .padding(top = 8.dp, bottom = 16.dp, start = 4.dp, end = 4.dp),
            ) {
                Row(
                    Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "返回")
                    }
                    Text(
                        st.score?.title.orEmpty(),
                        style = MaterialTheme.typography.titleLarge,
                        color = Color.White,
                        modifier = Modifier.weight(1f),
                    )
                    IconButton(onClick = { vm.toggleAbSetupMode() }) {
                        Icon(Icons.Default.Repeat, contentDescription = "A-B 设点")
                    }
                    IconButton(onClick = { vm.setControlsVisible(true) }) {
                        Icon(Icons.Default.MoreVert, contentDescription = "菜单")
                    }
                }
                if (st.abSetupMode) {
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .padding(top = 48.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        TextButton(onClick = { vm.setAbPointA() }) { Text("设为 A", color = Color.White) }
                        TextButton(onClick = { vm.setAbPointB() }) { Text("设为 B", color = Color.White) }
                        TextButton(onClick = { vm.clearAbLoop() }) { Text("清除", color = Color.White) }
                    }
                }
            }
        }

        if (!st.controlsVisible) {
            IconButton(
                onClick = { vm.setControlsVisible(true) },
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .statusBarsPadding()
                    .padding(8.dp),
            ) {
                Icon(Icons.Default.MoreVert, contentDescription = "显示控制栏", tint = Color.White)
            }
        }

        if (st.controlsVisible) {
            Card(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .padding(12.dp),
                shape = RoundedCornerShape(16.dp),
                elevation = CardDefaults.cardElevation(8.dp),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Row(
                        Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(
                            formatMs(st.positionMs),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Slider(
                            value = if (st.durationMs > 0) st.positionMs.toFloat() / st.durationMs else 0f,
                            onValueChange = { f ->
                                val ms = (f * st.durationMs).toLong()
                                vm.seekTo(ms)
                            },
                            modifier = Modifier.weight(1f),
                        )
                        Text(
                            formatMs(st.durationMs),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        TextButton(onClick = { speedDialog = true }) {
                            Text("${"%.1f".format(st.playbackSpeed)}x")
                        }
                        FloatingActionButton(onClick = { vm.togglePlayPause() }) {
                            Icon(
                                if (st.isPlaying) Icons.Default.Pause else Icons.Default.PlayArrow,
                                contentDescription = "播放",
                            )
                        }
                        TextButton(onClick = { pitchDialog = true }) {
                            Text("${st.pitchOffset} st")
                        }
                    }
                }
            }
        }
    }

    if (speedDialog) {
        var local by remember { mutableFloatStateOf(st.playbackSpeed) }
        LaunchedEffect(speedDialog) {
            if (speedDialog) local = st.playbackSpeed
        }
        AlertDialog(
            onDismissRequest = { speedDialog = false },
            confirmButton = {
                TextButton(onClick = {
                    vm.setSpeed(local)
                    speedDialog = false
                }) { Text("确定") }
            },
            dismissButton = { TextButton(onClick = { speedDialog = false }) { Text("取消") } },
            title = { Text("速度") },
            text = {
                Column {
                    Slider(value = local, onValueChange = { local = it }, valueRange = 0.5f..2f)
                    Text("${"%.2f".format(local)}x")
                }
            },
        )
    }

    if (pitchDialog) {
        var local by remember { mutableIntStateOf(st.pitchOffset) }
        LaunchedEffect(pitchDialog) {
            if (pitchDialog) local = st.pitchOffset
        }
        AlertDialog(
            onDismissRequest = { pitchDialog = false },
            confirmButton = {
                TextButton(onClick = {
                    vm.setPitchOffset(local)
                    pitchDialog = false
                }) { Text("确定") }
            },
            dismissButton = { TextButton(onClick = { pitchDialog = false }) { Text("取消") } },
            title = { Text("音调（半音）") },
            text = {
                Column {
                    Slider(
                        value = local.toFloat(),
                        onValueChange = { local = it.toInt() },
                        valueRange = (-12f)..(12f),
                        steps = 23,
                    )
                    Text(local.toString())
                }
            },
        )
    }
}

private fun formatMs(ms: Long): String {
    val s = (ms.coerceAtLeast(0L)) / 1000
    val m = s / 60
    val r = s % 60
    return "%d:%02d".format(m, r)
}

@Composable
private fun Modifier.offsetDp(xPx: Float, yPx: Float, density: Density): Modifier =
    this.offset(with(density) { xPx.toDp() }, with(density) { yPx.toDp() })
