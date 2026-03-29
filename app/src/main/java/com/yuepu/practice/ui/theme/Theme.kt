package com.yuepu.practice.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightScheme = lightColorScheme(
    primary = PrimaryBlue,
    background = LightBackground,
    surface = Color.White,
)

private val DarkScheme = darkColorScheme(
    primary = PrimaryBlue,
    background = DarkBackground,
    surface = Color(0xFF1E1E1E),
)

@Composable
fun YuepuTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    MaterialTheme(
        colorScheme = if (dark) DarkScheme else LightScheme,
        typography = Typography,
        content = content,
    )
}
