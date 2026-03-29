package com.yuepu.practice.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yuepu.practice.data.prefs.UserPreferencesRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class SettingsUiState(
    val baseUrl: String = "",
    val tokenOverride: String = "",
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val prefs: UserPreferencesRepository,
) : ViewModel() {

    val ui: StateFlow<SettingsUiState> = combine(
        prefs.baseUrl,
        prefs.appTokenOverride,
    ) { base, token ->
        SettingsUiState(baseUrl = base, tokenOverride = token.orEmpty())
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), SettingsUiState())

    fun save(baseUrl: String, tokenOverride: String) {
        viewModelScope.launch {
            prefs.setBaseUrl(baseUrl)
            prefs.setAppTokenOverride(tokenOverride.ifBlank { null })
        }
    }
}
