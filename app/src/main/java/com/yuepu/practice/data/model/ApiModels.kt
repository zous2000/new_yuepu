package com.yuepu.practice.data.model

import kotlinx.serialization.Serializable

@Serializable
data class ScoreListResponse(
    val scores: List<ScoreListItemDto> = emptyList(),
)

@Serializable
data class ScoreListItemDto(
    val songId: String,
    val title: String,
    val updatedAt: Long = 0L,
    val files: ScoreFilesDto,
)

@Serializable
data class ScoreFilesDto(
    val data: String,
    val image: String,
    val audio: String,
)

fun storageKeyFromFiles(files: ScoreFilesDto): String {
    val p = files.data.trim()
    val prefix = "/api/scores/"
    require(p.startsWith(prefix)) { "Unexpected data path: $p" }
    return p.removePrefix(prefix).substringBefore('/')
}
