// =============================================================================
// PlayPolicies.cs - Connect Four Pro Ultimate
// Aramadan SONRA istemcide uygulanan politikalar (src/gui_app.py ile birebir):
//   * SlipPolicy: Kolay seviyesinin kasitli "hata"lari (fmix32, slip_move)
//   * MoveAnalysis: "isabet" icin esit en iyi hamleler kumesi (best_columns)
// AIEngine aramasi (hamle, skor, dugum sayilari) bu dosyadan etkilenmez.
// =============================================================================
//
// Altin vektorler: scripts/export_slip_vectors.py ve scripts/export_analysis_vectors.py
// (tests/csharp/vectors/slip_vectors.json, analysis_vectors.json).

using System;
using System.Collections.Generic;
using ConnectFourPro.Core;

namespace ConnectFourPro.AI
{
    /// <summary>
    /// Kolay seviyesinin hata politikasi. Tum islemler 32 bit isaretsiz (tasmada mod 2^32):
    ///   h1 = Fmix32(seed + ply * 0x9E3779B1)   (hata olup olmayacagi; ply = AI hamlesinden onceki hamle sayisi)
    ///   h2 = Fmix32(h1 + 0x9E3779B9)           (hangi sutun)
    /// Yalnizca derinlik 2'de, h1 % 1000 &lt; 400 ise hata yapilir; AI'nin hemen kazanan hamlesi
    /// varsa asla. Hata sutunu: gecerli sutunlar (artan) [h2 % adet].
    /// (seed, ply) saf fonksiyonu: geri alip ayni hamleyi oynamak hatayi yeniden zarlamaz.
    /// </summary>
    public static class SlipPolicy
    {
        public const uint PlyMultiplier = 0x9E3779B1u;
        public const uint ColumnSalt = 0x9E3779B9u;

        /// <summary>Derinlige gore binde hata olasiligi (Python SLIP_PERMILLE = {2: 400}).</summary>
        public static int Permille(int depth) => depth == 2 ? 400 : 0;

        /// <summary>Murmur3 son karistirici (avalans).</summary>
        public static uint Fmix32(uint h)
        {
            unchecked
            {
                h ^= h >> 16;
                h *= 0x85EBCA6Bu;
                h ^= h >> 13;
                h *= 0xC2B2AE35u;
                h ^= h >> 16;
                return h;
            }
        }

        /// <summary>Hata yapilacaksa sutun, yoksa -1. Pozisyon sirasi gelen (AI) tarafindan oynanir.</summary>
        public static int SlipMove(GameState game, int depth, uint seed)
        {
            int permille = Permille(depth);
            var valid = game.GetValidLocations();
            if (permille == 0 || game.GameOver || valid.Count == 0)
                return -1;
            uint h1 = Fmix32(unchecked(seed + (uint)game.MoveCount * PlyMultiplier));
            if (h1 % 1000u >= (uint)permille)
                return -1;
            int me = game.CurrentPlayer;
            foreach (int col in valid)
            {
                var trial = game.Clone();
                trial.MakeMove(col);
                if (trial.Winner == me)
                    return -1;     // kendi galibiyetini kacirmaz
            }
            return valid[(int)(Fmix32(unchecked(h1 + ColumnSalt)) % (uint)valid.Count)];
        }

        /// <summary>Aramanin sectigi sutuna politikayi uygular (arama sonucu yoksa dokunmaz).</summary>
        public static int Apply(GameState before, int depth, uint seed, int searched)
        {
            if (searched < 0)
                return searched;
            int slip = SlipMove(before, depth, seed);
            return slip >= 0 ? slip : searched;
        }
    }

    /// <summary>
    /// "Isabetli" sayilan sutunlar: derinlik-N aramasinin (kitapsiz) esit en iyi kok hamleleri
    /// ile (varsa) acilis kitabi hamlesinin birlesimi, artan sirada.
    /// </summary>
    public static class MoveAnalysis
    {
        /// <summary>Analiz motoru: kitap kapali (kitap hamlesi sonradan eklenir).</summary>
        public static AIEngine NewEngine(GameState game, int depth) =>
            new AIEngine(game.CurrentPlayer, depth, useOpeningBook: false);

        /// <summary>Senkron analiz (testler); iptal edilirse ya da tahta doluysa null.</summary>
        public static List<int> BestColumns(GameState game, int depth, Func<bool> cancel = null)
        {
            var engine = NewEngine(game, depth);
            var search = engine.BeginSearch(game, cancel);
            while (!search.Step())
            {
            }
            return FromSearch(game, engine, search);
        }

        /// <summary>Biten bir analiz aramasindan kume; iptal/sonucsuz aramada null.</summary>
        public static List<int> FromSearch(GameState game, AIEngine engine, AIEngine.Search search)
        {
            if (!search.Done || search.Cancelled || search.Result < 0)
                return null;
            var best = new List<int>();
            if (engine.LastDepthReached > 0 && engine.LastScore.HasValue)
            {
                foreach (var (col, value) in search.RootResults)
                    if (value == engine.LastScore.Value)
                        best.Add(col);
            }
            if (best.Count == 0)
            {
                // Arama atlandi (taktik kisayol): kazanan sutunlarin hepsi, yoksa zorunlu hamle
                int me = game.CurrentPlayer;
                foreach (int c in game.GetValidLocations())
                {
                    var trial = game.Clone();
                    trial.MakeMove(c);
                    if (trial.Winner == me)
                        best.Add(c);
                }
                if (best.Count == 0)
                    best.Add(search.Result);
            }
            int book = OpeningBook.Lookup(game.MoveHistory);
            if (book >= 0 && !best.Contains(book))
                best.Add(book);
            best.Sort();
            return best;
        }
    }
}
