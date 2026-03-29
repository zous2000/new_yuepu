package com.yuepu.practice.practice

import android.content.Context
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.PlaybackParameters
import androidx.media3.exoplayer.ExoPlayer
import com.yuepu.practice.data.ScoreRepository
import com.yuepu.practice.data.model.Measure
import com.yuepu.practice.data.model.ScoreData
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import javax.inject.Inject
import kotlin.math.pow
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

sealed interface AbLoopState {
    data object Inactive : AbLoopState
    data class PointASet(val startTimeMs: Long) : AbLoopState
    data class Active(val startTimeMs: Long, val endTimeMs: Long) : AbLoopState
}

data class PracticeUiState(
    val isLoading: Boolean = true,
    val loadError: String? = null,
    val score: ScoreData? = null,
    val imageAbsolutePath: String? = null,
    val audioAbsolutePath: String? = null,
    val isPlaying: Boolean = false,
    val positionMs: Long = 0L,
    val durationMs: Long = 0L,
    val playbackSpeed: Float = 1f,
    val pitchOffset: Int = 0,
    val abLoop: AbLoopState = AbLoopState.Inactive,
    val abSetupMode: Boolean = false,
    val controlsVisible: Boolean = true,
    val naturalImageWidth: Float = 0f,
    val naturalImageHeight: Float = 0f,
) {
    val currentMeasure: Measure?
        get() {
            val s = score ?: return null
            val t = positionMs
            return s.measures.firstOrNull { t >= it.startTimeMs && t < it.endTimeMs }
        }
}

@HiltViewModel
class PracticeViewModel @Inject constructor(
    @ApplicationContext context: Context,
    savedStateHandle: SavedStateHandle,
    private val repository: ScoreRepository,
) : ViewModel() {

    private val songKey: String = savedStateHandle.get<String>("songKey")
        ?: error("songKey required")

    private val appContext = context.applicationContext
    private val player: ExoPlayer = ExoPlayer.Builder(appContext).build()

    private val _state = MutableStateFlow(PracticeUiState())
    val state: StateFlow<PracticeUiState> = _state.asStateFlow()

    private var tickJob: Job? = null

    init {
        player.addListener(
            object : Player.Listener {
                override fun onIsPlayingChanged(isPlaying: Boolean) {
                    _state.update { it.copy(isPlaying = isPlaying) }
                    if (isPlaying) startTicking() else stopTicking()
                }

                override fun onPlaybackStateChanged(playbackState: Int) {
                    if (playbackState == Player.STATE_READY) {
                        val d = player.duration.coerceAtLeast(0L)
                        _state.update { it.copy(durationMs = d) }
                    }
                }
            },
        )

        viewModelScope.launch {
            val dir = repository.localScoreDir(songKey)
            val dataFile = File(dir, "data.json")
            if (!dataFile.isFile()) {
                _state.update { it.copy(isLoading = false, loadError = "本地曲谱不存在") }
                return@launch
            }
            val score = repository.readLocalScore(songKey)
            if (score == null) {
                _state.update { it.copy(isLoading = false, loadError = "无法解析 data.json") }
                return@launch
            }
            val img = File(dir, score.imageFile)
            val aud = File(dir, score.audioFile)
            if (!img.isFile() || !aud.isFile()) {
                _state.update { it.copy(isLoading = false, loadError = "缺少图片或音频文件") }
                return@launch
            }
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeFile(img.absolutePath, bounds)
            val iw = bounds.outWidth.toFloat().coerceAtLeast(1f)
            val ih = bounds.outHeight.toFloat().coerceAtLeast(1f)
            player.setMediaItem(MediaItem.fromUri(Uri.fromFile(aud)))
            player.prepare()
            applyPlaybackParameters()
            _state.update {
                it.copy(
                    isLoading = false,
                    score = score,
                    imageAbsolutePath = img.absolutePath,
                    audioAbsolutePath = aud.absolutePath,
                    naturalImageWidth = iw,
                    naturalImageHeight = ih,
                )
            }
        }
    }

    private fun applyPlaybackParameters() {
        val s = _state.value.playbackSpeed
        val po = _state.value.pitchOffset
        val pitchMul = 2.0.pow(po / 12.0).toFloat()
        player.playbackParameters = PlaybackParameters(s, pitchMul)
    }

    fun setSpeed(speed: Float) {
        _state.update { it.copy(playbackSpeed = speed.coerceIn(0.5f, 2f)) }
        applyPlaybackParameters()
    }

    fun setPitchOffset(offset: Int) {
        _state.update { it.copy(pitchOffset = offset.coerceIn(-12, 12)) }
        applyPlaybackParameters()
    }

    fun togglePlayPause() {
        if (player.isPlaying) player.pause() else player.play()
    }

    fun seekTo(ms: Long) {
        val d = _state.value.durationMs
        val t = ms.coerceIn(0L, if (d > 0) d else ms.coerceAtLeast(0L))
        player.seekTo(t)
        _state.update { it.copy(positionMs = t) }
    }

    fun seekToMeasureStart(measure: Measure) {
        player.seekTo(measure.startTimeMs)
        if (!player.isPlaying) player.play()
        _state.update { it.copy(positionMs = measure.startTimeMs) }
    }

    fun setControlsVisible(visible: Boolean) {
        _state.update { it.copy(controlsVisible = visible) }
    }

    fun toggleAbSetupMode() {
        _state.update { s ->
            val next = !s.abSetupMode
            if (!next) {
                s.copy(abSetupMode = false, abLoop = AbLoopState.Inactive)
            } else {
                s.copy(abSetupMode = true, abLoop = AbLoopState.Inactive)
            }
        }
    }

    fun setAbPointA() {
        val m = _state.value.currentMeasure ?: return
        _state.update { it.copy(abLoop = AbLoopState.PointASet(m.startTimeMs)) }
    }

    fun setAbPointB() {
        val s = _state.value
        val a = s.abLoop as? AbLoopState.PointASet ?: return
        val m = s.currentMeasure ?: return
        _state.update {
            it.copy(
                abLoop = AbLoopState.Active(a.startTimeMs, m.endTimeMs),
                abSetupMode = false,
            )
        }
    }

    fun clearAbLoop() {
        _state.update { it.copy(abLoop = AbLoopState.Inactive, abSetupMode = false) }
    }

    private fun startTicking() {
        if (tickJob?.isActive == true) return
        tickJob = viewModelScope.launch {
            while (isActive) {
                delay(50)
                val p = player.currentPosition
                _state.update { st ->
                    val ab = st.abLoop
                    if (ab is AbLoopState.Active && p >= ab.endTimeMs) {
                        player.seekTo(ab.startTimeMs)
                        st.copy(positionMs = ab.startTimeMs)
                    } else {
                        st.copy(positionMs = p)
                    }
                }
            }
        }
    }

    private fun stopTicking() {
        tickJob?.cancel()
        tickJob = null
        _state.update { it.copy(positionMs = player.currentPosition) }
    }

    override fun onCleared() {
        super.onCleared()
        tickJob?.cancel()
        player.release()
    }
}
