// UnityEngine sahtesi (yalnizca tests/csharp): Runtime kodunun kullandigi uyeler.
// Davranis taklit edilmez; zaman ve gunluk testlerden gorulur/ayarlanir.
using System.Collections.Generic;

namespace UnityEngine
{
    /// <summary>AppController bunu yalnizca ApiClient'a iletir; uyesi yoktur.</summary>
    public class MonoBehaviour
    {
    }

    public static class Debug
    {
        public static readonly List<string> Logs = new List<string>();
        public static readonly List<string> Warnings = new List<string>();

        public static void Log(object message) => Logs.Add(message?.ToString() ?? "Null");
        public static void LogWarning(object message) => Warnings.Add(message?.ToString() ?? "Null");
    }

    public static class Time
    {
        /// <summary>Unity'de salt okunur; burada testler ilerletir.</summary>
        public static float unscaledTime { get; set; }
    }

    public static class Random
    {
        private static System.Random _random = new System.Random(0);

        public static void InitState(int seed) => _random = new System.Random(seed);

        /// <summary>Unity'deki gibi: min dahil, max haric.</summary>
        public static int Range(int minInclusive, int maxExclusive) => _random.Next(minInclusive, maxExclusive);
    }

    /// <summary>Testler arasi sifirlama (Unity'de karsiligi yok).</summary>
    public static class UnityStubs
    {
        public static void Reset()
        {
            Debug.Logs.Clear();
            Debug.Warnings.Clear();
            Time.unscaledTime = 0f;
            Random.InitState(0);
        }
    }
}
