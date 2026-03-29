package com.yuepu.practice.data

import com.yuepu.practice.data.local.ScoreLocalDataSource
import com.yuepu.practice.data.model.ScoreData
import com.yuepu.practice.data.model.ScoreListItemDto
import com.yuepu.practice.data.model.storageKeyFromFiles
import com.yuepu.practice.data.prefs.UserPreferencesRepository
import com.yuepu.practice.data.remote.ScoreRemoteDataSource
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.first
import kotlinx.serialization.json.Json

@Singleton
class ScoreRepository @Inject constructor(
    private val remote: ScoreRemoteDataSource,
    private val local: ScoreLocalDataSource,
    private val prefs: UserPreferencesRepository,
) {
    private val json = Json { ignoreUnknownKeys = true; isLenient = true }

    suspend fun effectiveToken(): String {
        val override = prefs.appTokenOverride.first()
        return prefs.effectiveAppToken(override)
    }

    suspend fun fetchRemoteList(): Result<List<ScoreListItemDto>> {
        val base = prefs.baseUrl.first()
        val token = effectiveToken()
        return remote.fetchManifest(base, token).map { it.scores }
    }

    suspend fun downloadItem(item: ScoreListItemDto) {
        val base = prefs.baseUrl.first()
        val token = effectiveToken()
        val key = storageKeyFromFiles(item.files)
        val dataBytes = remote.downloadBytes(base, token, item.files.data)
        val parsed = json.decodeFromString<ScoreData>(dataBytes.decodeToString())
        val imgBytes = remote.downloadBytes(base, token, item.files.image)
        val audBytes = remote.downloadBytes(base, token, item.files.audio)
        local.writeScorePackage(
            storageKey = key,
            dataJsonBytes = dataBytes,
            imageBytes = imgBytes,
            imageFileName = parsed.imageFile,
            audioBytes = audBytes,
            audioFileName = parsed.audioFile,
        )
    }

    suspend fun deleteLocal(storageKey: String) {
        local.deleteScore(storageKey)
    }

    suspend fun readLocalScore(storageKey: String): ScoreData? = local.readScore(storageKey)

    suspend fun listLocalKeys(): Set<String> =
        local.listDownloadedMeta().map { it.first }.toSet()

    fun localScoreDir(storageKey: String) = local.scoreDir(storageKey)
}
