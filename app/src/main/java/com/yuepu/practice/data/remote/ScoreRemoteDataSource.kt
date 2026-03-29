package com.yuepu.practice.data.remote

import com.yuepu.practice.data.model.ScoreListResponse
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request

@Singleton
class ScoreRemoteDataSource @Inject constructor(
    private val client: OkHttpClient,
) {
    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
    }

    fun resolveUrl(baseUrl: String, pathOrUrl: String): String {
        val p = pathOrUrl.trim()
        if (p.startsWith("http://") || p.startsWith("https://")) return p
        val base = baseUrl.trimEnd('/')
        return base + (if (p.startsWith("/")) p else "/$p")
    }

    suspend fun fetchManifest(baseUrl: String, token: String): Result<ScoreListResponse> = withContext(Dispatchers.IO) {
        runCatching {
            val url = resolveUrl(baseUrl, "/api/scores")
            val req = Request.Builder()
                .url(url)
                .header("Authorization", "Bearer $token")
                .get()
                .build()
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) error("HTTP ${resp.code}")
                val body = resp.body?.string().orEmpty()
                json.decodeFromString<ScoreListResponse>(body)
            }
        }
    }

    suspend fun downloadBytes(baseUrl: String, token: String, pathOrUrl: String): ByteArray =
        withContext(Dispatchers.IO) {
            val url = resolveUrl(baseUrl, pathOrUrl)
            val req = Request.Builder()
                .url(url)
                .header("Authorization", "Bearer $token")
                .get()
                .build()
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) error("HTTP ${resp.code} for $url")
                resp.body?.bytes() ?: error("empty body")
            }
        }
}
