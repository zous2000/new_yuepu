package com.yuepu.practice.data.prefs

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.yuepu.practice.BuildConfig
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "yuepu_prefs")

@Singleton
class UserPreferencesRepository @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val baseUrlKey = stringPreferencesKey("base_url")
    private val tokenOverrideKey = stringPreferencesKey("app_token_override")

    val baseUrl: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[baseUrlKey]?.takeIf { it.isNotBlank() } ?: BuildConfig.DEFAULT_BASE_URL.trimEnd('/')
    }

    val appTokenOverride: Flow<String?> = context.dataStore.data.map { prefs ->
        prefs[tokenOverrideKey]?.takeIf { it.isNotBlank() }
    }

    fun effectiveAppToken(overrideValue: String?): String =
        overrideValue?.takeIf { it.isNotBlank() } ?: BuildConfig.DEFAULT_APP_TOKEN

    suspend fun setBaseUrl(value: String) {
        context.dataStore.edit { it[baseUrlKey] = value.trimEnd('/') }
    }

    suspend fun setAppTokenOverride(value: String?) {
        context.dataStore.edit { prefs ->
            if (value.isNullOrBlank()) {
                prefs.remove(tokenOverrideKey)
            } else {
                prefs[tokenOverrideKey] = value.trim()
            }
        }
    }
}
