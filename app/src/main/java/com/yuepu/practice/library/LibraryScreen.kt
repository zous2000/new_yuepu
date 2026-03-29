package com.yuepu.practice.library

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LibraryScreen(
    onOpenSettings: () -> Unit,
    onOpenScore: (String) -> Unit,
    vm: LibraryViewModel = hiltViewModel(),
) {
    val ui by vm.ui.collectAsState()
    val snackbar = remember { SnackbarHostState() }
    val pullState = rememberPullToRefreshState()

    LaunchedEffect(ui.error) {
        val e = ui.error ?: return@LaunchedEffect
        snackbar.showSnackbar(e)
        vm.consumeError()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("我的乐谱") },
                actions = {
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "设置")
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { vm.refreshFromServer() }) {
                Icon(Icons.Default.Sync, contentDescription = "同步")
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        PullToRefreshBox(
            isRefreshing = ui.isRefreshing,
            onRefresh = { vm.refreshFromServer() },
            state = pullState,
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            if (ui.rows.isEmpty() && !ui.isRefreshing) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text("下拉同步或点击右下角按钮从服务器获取曲目")
                        Text(
                            "请先在设置中配置服务器地址",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(ui.rows, key = { it.storageKey }) { row ->
                        SwipeRow(
                            row = row,
                            onDismiss = { vm.deleteLocal(row.storageKey) },
                        ) {
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        if (row.downloaded) onOpenScore(row.storageKey)
                                        else vm.download(row.storageKey)
                                    },
                            ) {
                                ListItem(
                                    headlineContent = { Text(row.title) },
                                    supportingContent = {
                                        val status = when {
                                            row.downloading -> "下载中…"
                                            row.downloaded -> "已下载，点击进入练习"
                                            else -> "点击下载"
                                        }
                                        Text(status)
                                    },
                                    trailingContent = {
                                        if (row.downloading) {
                                            CircularProgressIndicator(
                                                modifier = Modifier.padding(8.dp),
                                                strokeWidth = 2.dp,
                                            )
                                        } else if (!row.downloaded) {
                                            TextButton(onClick = { vm.download(row.storageKey) }) {
                                                Text("下载")
                                            }
                                        }
                                    },
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SwipeRow(
    row: LibraryRow,
    onDismiss: () -> Unit,
    content: @Composable () -> Unit,
) {
    if (!row.downloaded) {
        content()
        return
    }
    val dismissState = rememberSwipeToDismissBoxState(
        confirmValueChange = { v ->
            if (v == SwipeToDismissBoxValue.EndToStart) {
                onDismiss()
                true
            } else {
                false
            }
        },
    )
    SwipeToDismissBox(
        state = dismissState,
        enableDismissFromStartToEnd = false,
        backgroundContent = {
            Box(
                Modifier
                    .fillMaxSize()
                    .padding(horizontal = 16.dp),
                contentAlignment = Alignment.CenterEnd,
            ) {
                Text("删除本地", color = MaterialTheme.colorScheme.error)
            }
        },
        content = { content() },
    )
}
