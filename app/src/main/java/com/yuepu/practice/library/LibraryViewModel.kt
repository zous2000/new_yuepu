package com.yuepu.practice.library

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yuepu.practice.data.ScoreRepository
import com.yuepu.practice.data.model.ScoreListItemDto
import com.yuepu.practice.data.model.storageKeyFromFiles
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class LibraryRow(
    val storageKey: String,
    val title: String,
    val songId: String,
    val updatedAt: Long,
    val downloaded: Boolean,
    val downloading: Boolean,
)

data class LibraryUiState(
    val rows: List<LibraryRow> = emptyList(),
    val isRefreshing: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class LibraryViewModel @Inject constructor(
    private val repository: ScoreRepository,
) : ViewModel() {

    private val _ui = MutableStateFlow(LibraryUiState())
    val ui: StateFlow<LibraryUiState> = _ui.asStateFlow()

    private val downloadingKeys = MutableStateFlow<Set<String>>(emptySet())
    private var lastRemote: List<ScoreListItemDto> = emptyList()

    init {
        viewModelScope.launch { rebuild() }
    }

    private suspend fun rebuild() {
        val local = repository.listLocalKeys()
        val down = downloadingKeys.value
        if (lastRemote.isEmpty()) {
            _ui.update { s ->
                s.copy(
                    rows = local.map { k ->
                        LibraryRow(
                            storageKey = k,
                            title = k,
                            songId = k,
                            updatedAt = 0L,
                            downloaded = true,
                            downloading = false,
                        )
                    },
                )
            }
        } else {
            _ui.update { s ->
                s.copy(
                    rows = lastRemote.map { dto ->
                        val key = storageKeyFromFiles(dto.files)
                        dto.toRow(downloaded = key in local, downloading = key in down)
                    },
                )
            }
        }
    }

    private fun ScoreListItemDto.toRow(downloaded: Boolean, downloading: Boolean): LibraryRow {
        val key = storageKeyFromFiles(files)
        return LibraryRow(
            storageKey = key,
            title = title,
            songId = songId,
            updatedAt = updatedAt,
            downloaded = downloaded,
            downloading = downloading,
        )
    }

    fun refreshFromServer() {
        viewModelScope.launch {
            _ui.update { it.copy(isRefreshing = true, error = null) }
            val result = repository.fetchRemoteList()
            result.fold(
                onSuccess = { list ->
                    lastRemote = list
                    rebuild()
                    _ui.update { it.copy(isRefreshing = false, error = null) }
                },
                onFailure = { e ->
                    _ui.update {
                        it.copy(isRefreshing = false, error = e.message ?: "同步失败")
                    }
                },
            )
        }
    }

    fun download(storageKey: String) {
        val dto = lastRemote.firstOrNull { storageKeyFromFiles(it.files) == storageKey } ?: return
        viewModelScope.launch {
            downloadingKeys.update { it + storageKey }
            rebuild()
            runCatching { repository.downloadItem(dto) }
                .onFailure { e ->
                    _ui.update { it.copy(error = e.message ?: "下载失败") }
                }
            downloadingKeys.update { it - storageKey }
            rebuild()
        }
    }

    fun deleteLocal(storageKey: String) {
        viewModelScope.launch {
            repository.deleteLocal(storageKey)
            rebuild()
        }
    }

    fun consumeError() {
        _ui.update { it.copy(error = null) }
    }
}
