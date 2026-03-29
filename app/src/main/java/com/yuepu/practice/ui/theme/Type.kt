package com.yuepu.practice.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

private val base = Typography()

val Typography = base.copy(
    titleLarge = base.titleLarge.copy(fontWeight = FontWeight.Bold),
    bodyMedium = base.bodyMedium.copy(
        fontFamily = FontFamily.Monospace,
        fontSize = 14.sp,
    ),
)
