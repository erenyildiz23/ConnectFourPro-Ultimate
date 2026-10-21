// =============================================================================
// ApiClient.cs - Connect Four Pro Ultimate
// REST API istemcisi (UnityWebRequest; WebGL'de tarayicinin fetch'i kullanilir)
// =============================================================================

using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace ConnectFourPro.Net
{
    public sealed class ApiResponse
    {
        /// <summary>HTTP durum kodu; baglanti kurulamadiysa 0.</summary>
        public long Status;
        public string Body;
        public bool NetworkError => Status == 0;
        public bool Ok => Status >= 200 && Status < 300;

        public object ParseBody()
        {
            try
            {
                return string.IsNullOrEmpty(Body) ? null : Json.Parse(Body);
            }
            catch (JsonException)
            {
                return null;
            }
        }

        public JsonObject BodyObject => JsonObject.From(ParseBody());
    }

    public sealed class ApiClient
    {
        private const int TimeoutSeconds = 5;
        private readonly MonoBehaviour _host;

        public string BaseUrl { get; }

        public ApiClient(MonoBehaviour host, string baseUrl)
        {
            _host = host;
            BaseUrl = baseUrl.TrimEnd('/');
        }

        public void Login(string username, string password, Action<ApiResponse> done) =>
            Post("/login", Credentials(username, password), done);

        public void Signup(string username, string password, Action<ApiResponse> done) =>
            Post("/signup", Credentials(username, password), done);

        public void ActiveGames(Action<ApiResponse> done) => Get("/active_games", done);
        public void Leaderboard(Action<ApiResponse> done) => Get("/leaderboard", done);
        public void User(string username, Action<ApiResponse> done) => Get("/user/" + Escape(username), done);
        public void History(string username, Action<ApiResponse> done) => Get("/user/" + Escape(username) + "/games", done);
        public void Health(Action<ApiResponse> done) => Get("/health", done);

        private static string Escape(string s) => UnityWebRequest.EscapeURL(s ?? "").Replace("+", "%20");

        private static string Credentials(string username, string password) =>
            Json.Serialize(new Dictionary<string, object> { ["username"] = username, ["password"] = password });

        private void Get(string path, Action<ApiResponse> done)
        {
            var request = UnityWebRequest.Get(BaseUrl + path);
            _host.StartCoroutine(Send(request, done));
        }

        private void Post(string path, string json, Action<ApiResponse> done)
        {
            var request = new UnityWebRequest(BaseUrl + path, UnityWebRequest.kHttpVerbPOST)
            {
                uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json)),
                downloadHandler = new DownloadHandlerBuffer(),
            };
            request.SetRequestHeader("Content-Type", "application/json");
            _host.StartCoroutine(Send(request, done));
        }

        private static IEnumerator Send(UnityWebRequest request, Action<ApiResponse> done)
        {
            using (request)
            {
                request.timeout = TimeoutSeconds;
                yield return request.SendWebRequest();
                var response = new ApiResponse
                {
                    Status = request.result == UnityWebRequest.Result.ConnectionError ? 0 : request.responseCode,
                    Body = request.downloadHandler?.text,
                };
                if (response.NetworkError)
                    Debug.LogWarning($"[ApiClient] {request.url}: {request.error}");
                try
                {
                    done?.Invoke(response);
                }
                catch (Exception e)
                {
                    Debug.LogException(e);
                }
            }
        }
    }
}
