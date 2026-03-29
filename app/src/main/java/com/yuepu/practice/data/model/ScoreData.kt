package com.yuepu.practice.data.model

import kotlinx.serialization.Serializable

@Serializable
data class ScoreData(
    val songId: String,
    val title: String,
    val imageFile: String,
    val audioFile: String,
    val measures: List<Measure> = emptyList(),
)

@Serializable
data class Measure(
    val id: Int,
    val startTimeMs: Long,
    val endTimeMs: Long,
    val rect: RectData,
)

@Serializable
data class RectData(
    val x: Float,
    val y: Float,
    val w: Float,
    val h: Float,
)

fun Measure.containsImagePoint(x: Float, y: Float): Boolean =
    x >= rect.x && x <= rect.x + rect.w && y >= rect.y && y <= rect.y + rect.h
