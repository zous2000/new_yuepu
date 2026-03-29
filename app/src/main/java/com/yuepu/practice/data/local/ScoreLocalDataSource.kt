package com.yuepu.practice.data.local

import android.content.Context
import com.yuepu.practice.data.model.ScoreData
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json

@Singleton
class ScoreLocalDataSource @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val json = Json { ignoreUnknownKeys = true; isLenient = true }

    private fun scoresRoot(): File = File(context.filesDir, "scores").apply { mkdirs() }

    fun scoreDir(storageKey: String): File = File(scoresRoot(), storageKey)

    suspend fun listDownloadedMeta(): List<Pair<String, Long>> = withContext(Dispatchers.IO) {
        val root = scoresRoot()
        if (!root.isDirectory) return@withContext emptyList()
        root.listFiles().orEmpty()
            .filter { it.isDirectory && File(it, "data.json").isFile() }
            .map { dir ->
                val m = File(dir, "data.json").lastModified()
                dir.name to m
            }
    }

    suspend fun readScore(storageKey: String): ScoreData? = withContext(Dispatchers.IO) {
        val f = File(scoreDir(storageKey), "data.json")
        if (!f.isFile()) return@withContext null
        runCatching {
            json.decodeFromString<ScoreData>(f.readText())
        }.getOrNull()
    }

    suspend fun deleteScore(storageKey: String) = withContext(Dispatchers.IO) {
        scoreDir(storageKey).deleteRecursively()
    }

    suspend fun writeScorePackage(
        storageKey: String,
        dataJsonBytes: ByteArray,
        imageBytes: ByteArray,
        imageFileName: String,
        audioBytes: ByteArray,
        audioFileName: String,
    ) = withContext(Dispatchers.IO) {
        val dir = scoreDir(storageKey)
        dir.deleteRecursively()
        dir.mkdirs()
        File(dir, "data.json").writeBytes(dataJsonBytes)
        File(dir, imageFileName).writeBytes(imageBytes)
        File(dir, audioFileName).writeBytes(audioBytes)
    }
}
