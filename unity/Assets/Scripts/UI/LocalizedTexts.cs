// =============================================================================
// LocalizedTexts.cs - Connect Four Pro Ultimate
// Sabit yazilarin dil degisince yeniden yazilmasi
// =============================================================================
//
// UIKit.Text her yaziyi Loc.T ile cevirerek yazar ve kaynak (Turkce) metni burada
// kaydeder. Dil degisince, yazisi o zamandan beri degismemis ogeler yeni dilde
// yeniden yazilir. Her karede Refresh ile yazilan dinamik yazilar zaten Loc.T
// kullandigi icin kendiliginden gecer; onlarin ustune yazilmaz (metin degismis).

using System.Collections.Generic;
using ConnectFourPro.Game;
using UnityEngine;
using UnityEngine.UI;

namespace ConnectFourPro.UI
{
    public static class LocalizedTexts
    {
        private sealed class Entry
        {
            public Text Text;
            public string Source;
            public string Shown;
        }

        private const int MinPruneLimit = 256;
        private static readonly List<Entry> Entries = new List<Entry>();
        private static int _limit = MinPruneLimit;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        private static void ResetState()
        {
            Loc.Changed -= Apply;
            Loc.Changed += Apply;
            Entries.Clear();
            _limit = MinPruneLimit;
        }

        /// <summary>Yaziyi secili dilde yazar ve kaynak metni kaydeder.</summary>
        public static void Set(Text t, string source)
        {
            source = source ?? "";
            t.text = Loc.T(source);
            if (source.Length == 0)
                return;
            if (Entries.Count > _limit)
            {
                Entries.RemoveAll(e => e.Text == null);
                _limit = Mathf.Max(MinPruneLimit, Entries.Count * 2);
            }
            Entries.Add(new Entry { Text = t, Source = source, Shown = t.text });
        }

        private static void Apply(Lang lang)
        {
            Entries.RemoveAll(e => e.Text == null);
            foreach (var e in Entries)
            {
                if (e.Text.text != e.Shown)
                    continue;   // yazi sonradan degisti (dinamik): dokunma
                e.Text.text = Loc.T(e.Source);
                e.Shown = e.Text.text;
            }
        }
    }
}
