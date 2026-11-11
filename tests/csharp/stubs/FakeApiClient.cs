// Gercek Net/ApiClient.cs (UnityWebRequest + coroutine) yerine Runtime test
// assembly'sine derlenen sahte: ayni genel yuzey, ama istek gondermez; cagrilari
// kaydeder ve yaniti test verir. Gercek ApiClient'a uye eklenince burasi da guncellenir
// (AppController yeni uyeyi kullanirsa derleme kirilir).
using System;
using System.Collections.Generic;
using UnityEngine;

namespace ConnectFourPro.Net
{
    public sealed class ApiClient
    {
        public sealed class Call
        {
            /// <summary>Cagrilan metodun adi: Login, Signup, ActiveGames, ...</summary>
            public string Method;
            public string Username;
            public string Password;
            public bool Answered;
            private Action<ApiResponse> _done;

            internal Call(string method, string username, string password, Action<ApiResponse> done)
            {
                Method = method;
                Username = username;
                Password = password;
                _done = done;
            }

            /// <summary>Yaniti teslim eder; status 0 = baglanti kurulamadi.</summary>
            public void Respond(long status, string body = null)
            {
                if (Answered)
                    throw new InvalidOperationException(Method + " zaten yanitlandi");
                Answered = true;
                _done?.Invoke(new ApiResponse { Status = status, Body = body });
            }
        }

        public readonly List<Call> Calls = new List<Call>();

        public string BaseUrl { get; }

        public ApiClient(MonoBehaviour host, string baseUrl)
        {
            BaseUrl = baseUrl.TrimEnd('/');
        }

        public void Login(string username, string password, Action<ApiResponse> done) =>
            Calls.Add(new Call(nameof(Login), username, password, done));

        public void Signup(string username, string password, Action<ApiResponse> done) =>
            Calls.Add(new Call(nameof(Signup), username, password, done));

        public void ActiveGames(Action<ApiResponse> done) => Calls.Add(new Call(nameof(ActiveGames), null, null, done));
        public void Leaderboard(Action<ApiResponse> done) => Calls.Add(new Call(nameof(Leaderboard), null, null, done));
        public void User(string username, Action<ApiResponse> done) => Calls.Add(new Call(nameof(User), username, null, done));
        public void History(string username, Action<ApiResponse> done) => Calls.Add(new Call(nameof(History), username, null, done));
        public void Health(Action<ApiResponse> done) => Calls.Add(new Call(nameof(Health), null, null, done));
    }
}
