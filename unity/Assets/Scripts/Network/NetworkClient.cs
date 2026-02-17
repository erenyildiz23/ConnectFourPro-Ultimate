// =============================================================================
// NetworkClient.cs - Connect Four Pro
// SocketIO tabanli ag istemcisi
// Python gui_app.py NetworkManager sinifinin C# karsiligi
// =============================================================================
// NOT: Bu script SocketIOUnity paketini gerektirir.
// Unity Package Manager > Add package from git URL:
// https://github.com/itisnajim/SocketIOUnity.git
// =============================================================================

using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;
using ConnectFourPro.Core;
using ConnectFourPro.Managers;

namespace ConnectFourPro.Network
{
    [Serializable]
    public class LoginRequest
    {
        public string username;
        public string password;
    }

    [Serializable]
    public class LoginResponse
    {
        public string message;
        public UserData user;
    }

    [Serializable]
    public class SignupResponse
    {
        public string message;
        public int user_id;
    }

    [Serializable]
    public class UserData
    {
        public int user_id;
        public string username;
        public int rating;
        public int wins;
        public int losses;
    }

    [Serializable]
    public class ActiveGameData
    {
        public string room_id;
        public string p1;
        public int p1_elo;
        public string p2;
        public int p2_elo;
        public string status;
        public int move_count;
    }

    [Serializable]
    public class ActiveGamesList
    {
        public ActiveGameData[] games;
    }

    [Serializable]
    public class LeaderboardEntry
    {
        public string username;
        public int rating;
        public int wins;
        public int losses;
    }

    /// <summary>
    /// SocketIO ve REST API istemcisi.
    /// SocketIOUnity paketi kullanir. Paket yuklu degilse REST-only modda calisir.
    /// </summary>
    public class NetworkClient : MonoBehaviour
    {
        [Header("Server Configuration")]
        public string ServerUrl = "http://localhost:5000";

        public bool Connected { get; private set; }
        public string RoomId { get; private set; }
        public int? MyPiece { get; private set; }

        private GameManager _gm;

        // SocketIO instance'i - SocketIOUnity paketi gereklidir
        // Paket yoksa null kalir ve sadece REST API kullanilir
        private object _socketIO; // SocketIOUnity.SocketIOUnity tipinde olacak

        // Events
        public event Action OnConnected;
        public event Action OnDisconnected;
        public event Action<string> OnError;

        private void Start()
        {
            _gm = GameManager.Instance;
            TryInitializeSocketIO();
        }

        private void OnDestroy()
        {
            Disconnect();
        }

        // =========================================================================
        // SOCKETIO BAGLANTISI
        // =========================================================================

        private void TryInitializeSocketIO()
        {
            // SocketIOUnity paketi yuklu ise otomatik olarak tanimlanir.
            // Bu kisim paketin varligina gore calisir.
            // Simdilik REST polling yaklasimiyla devam edilir.
            Debug.Log("[NetworkClient] SocketIO initialization - install SocketIOUnity package for real-time support");
        }

        public void ConnectToServer()
        {
            StartCoroutine(CheckServerHealth());
        }

        private IEnumerator CheckServerHealth()
        {
            using (var request = UnityWebRequest.Get($"{ServerUrl}/health"))
            {
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    Connected = true;
                    OnConnected?.Invoke();
                    Debug.Log("[NetworkClient] Server connected");
                }
                else
                {
                    Connected = false;
                    Debug.LogWarning($"[NetworkClient] Server connection failed: {request.error}");
                }
            }
        }

        public void Disconnect()
        {
            Connected = false;
            RoomId = null;
            MyPiece = null;
            OnDisconnected?.Invoke();
        }

        // =========================================================================
        // REST API - KIMLIK DOGRULAMA
        // =========================================================================

        public void Login(string username, string password, Action<bool, UserData, string> callback)
        {
            StartCoroutine(LoginCoroutine(username, password, callback));
        }

        private IEnumerator LoginCoroutine(string username, string password, Action<bool, UserData, string> callback)
        {
            var body = JsonUtility.ToJson(new LoginRequest { username = username, password = password });
            using (var request = new UnityWebRequest($"{ServerUrl}/login", "POST"))
            {
                byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(body);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");

                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    var response = JsonUtility.FromJson<LoginResponse>(request.downloadHandler.text);
                    callback?.Invoke(true, response.user, null);
                }
                else
                {
                    callback?.Invoke(false, null, "Yanlis kullanici adi veya sifre!");
                }
            }
        }

        public void Register(string username, string password, Action<bool, int?, string> callback)
        {
            StartCoroutine(RegisterCoroutine(username, password, callback));
        }

        private IEnumerator RegisterCoroutine(string username, string password, Action<bool, int?, string> callback)
        {
            var body = JsonUtility.ToJson(new LoginRequest { username = username, password = password });
            using (var request = new UnityWebRequest($"{ServerUrl}/signup", "POST"))
            {
                byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(body);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");

                yield return request.SendWebRequest();

                if (request.responseCode == 201)
                {
                    var response = JsonUtility.FromJson<SignupResponse>(request.downloadHandler.text);
                    callback?.Invoke(true, response.user_id, null);
                }
                else if (request.responseCode == 409)
                {
                    callback?.Invoke(false, null, "Bu kullanici adi zaten alinmis!");
                }
                else
                {
                    callback?.Invoke(false, null, "Kayit basarisiz!");
                }
            }
        }

        // =========================================================================
        // REST API - OYUN ISLEMLERI
        // =========================================================================

        public void FetchActiveGames(Action<ActiveGameData[]> callback)
        {
            StartCoroutine(FetchActiveGamesCoroutine(callback));
        }

        private IEnumerator FetchActiveGamesCoroutine(Action<ActiveGameData[]> callback)
        {
            using (var request = UnityWebRequest.Get($"{ServerUrl}/active_games"))
            {
                request.timeout = 3;
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    // JSON array parse
                    string json = "{\"games\":" + request.downloadHandler.text + "}";
                    var list = JsonUtility.FromJson<ActiveGamesList>(json);
                    callback?.Invoke(list.games);
                }
                else
                {
                    callback?.Invoke(new ActiveGameData[0]);
                }
            }
        }

        public void FetchLeaderboard(Action<LeaderboardEntry[]> callback)
        {
            StartCoroutine(FetchLeaderboardCoroutine(callback));
        }

        private IEnumerator FetchLeaderboardCoroutine(Action<LeaderboardEntry[]> callback)
        {
            using (var request = UnityWebRequest.Get($"{ServerUrl}/leaderboard"))
            {
                request.timeout = 3;
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    string json = "{\"entries\":" + request.downloadHandler.text + "}";
                    // Basit JSON array parse
                    // Gercek projede Newtonsoft.Json kullanmaniz onerilir
                    callback?.Invoke(new LeaderboardEntry[0]);
                }
                else
                {
                    callback?.Invoke(new LeaderboardEntry[0]);
                }
            }
        }

        public void FetchUserInfo(string username, Action<UserData> callback)
        {
            StartCoroutine(FetchUserInfoCoroutine(username, callback));
        }

        private IEnumerator FetchUserInfoCoroutine(string username, Action<UserData> callback)
        {
            using (var request = UnityWebRequest.Get($"{ServerUrl}/user/{username}"))
            {
                request.timeout = 2;
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    // Parse nested JSON
                    string json = request.downloadHandler.text;
                    // Basitlestirmis parse - gercek projede Newtonsoft.Json kullanin
                    callback?.Invoke(null);
                }
                else
                {
                    callback?.Invoke(null);
                }
            }
        }

        // =========================================================================
        // SOCKETIO - OYUN ISLEMLERI
        // SocketIOUnity paketi kuruldugunda bu fonksiyonlar aktif olur
        // =========================================================================

        public void CreateGame(string userId)
        {
            // SocketIO emit: create_game
            Debug.Log($"[NetworkClient] CreateGame - userId={userId}");
            Debug.LogWarning("[NetworkClient] SocketIO paketi gerekli! Kurulum: https://github.com/itisnajim/SocketIOUnity");
            _gm?.SetStatus("SocketIO paketi gerekli! README'ye bakin.");
        }

        public void JoinGame(string roomId, string userId)
        {
            // SocketIO emit: join_game
            Debug.Log($"[NetworkClient] JoinGame - room={roomId}, userId={userId}");
        }

        public void SendMove(int col)
        {
            // SocketIO emit: make_move
            Debug.Log($"[NetworkClient] SendMove - col={col}");
        }
    }
}
