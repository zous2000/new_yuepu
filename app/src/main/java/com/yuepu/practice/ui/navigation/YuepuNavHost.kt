package com.yuepu.practice.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.yuepu.practice.library.LibraryScreen
import com.yuepu.practice.practice.PracticeScreen
import com.yuepu.practice.settings.SettingsScreen

object Routes {
    const val Library = "library"
    const val Settings = "settings"
    const val Practice = "practice/{songKey}"
    fun practice(songKey: String) = "practice/${android.net.Uri.encode(songKey)}"
}

@Composable
fun YuepuNavHost(modifier: Modifier = Modifier) {
    val nav = rememberNavController()
    NavHost(
        navController = nav,
        startDestination = Routes.Library,
        modifier = modifier,
    ) {
        composable(Routes.Library) {
            LibraryScreen(
                onOpenSettings = { nav.navigate(Routes.Settings) },
                onOpenScore = { key -> nav.navigate(Routes.practice(key)) },
            )
        }
        composable(Routes.Settings) {
            SettingsScreen(onBack = { nav.popBackStack() })
        }
        composable(
            route = Routes.Practice,
            arguments = listOf(navArgument("songKey") { type = NavType.StringType }),
        ) {
            PracticeScreen(onBack = { nav.popBackStack() })
        }
    }
}
