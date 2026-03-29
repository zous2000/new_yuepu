package com.yuepu.practice

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.yuepu.practice.ui.navigation.YuepuNavHost
import com.yuepu.practice.ui.theme.YuepuTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            YuepuTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    YuepuNavHost()
                }
            }
        }
    }
}
